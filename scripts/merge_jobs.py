"""
Fusionne les offres de toutes les sources, déduplique et trie par pertinence.
Clé de déduplication : hash(titre_normalisé + entreprise_normalisée + lieu_normalisé).

─── Filtrage "débutant / sans expérience" ──────────────────────────────────────
Ce module applique un FILTRE DUR (hard filter) sur l'expérience, en deux niveaux :

1. Présence d'un mot-clé de séniorité ou de diplôme élevé dans le titre/description
   → exclusion immédiate (KEYWORDS_EXCLUSION)

2. Mention explicite d'une durée d'expérience ≥ SEUIL_ANNEES_EXP ans
   Regex ciblé : "X an(s) d'expérience", "expérience de X ans", "X ans minimum"
   → exclusion si X ≥ 2 (seuil configurable via SEUIL_ANNEES_EXP)
   IMPORTANT : les mentions en mois (ex. "6 mois d'expérience") ne sont PAS ciblées
   par ce regex — comportement volontaire pour ne pas exclure des offres légitimes
   de courte durée. Toute modification de ce comportement doit être documentée ici.

Fiabilité par source :
- France Travail : signal structuré `experienceExige` traité EN AMONT dans
  fetch_france_travail.py (fiable — champ API dédié). Ce filtre textuel constitue
  une double protection.
- Adzuna / RSS : filtrage UNIQUEMENT textuel / heuristique (pas de champ structuré).
  Préférer la sur-exclusion à la sous-exclusion pour ces sources.
"""

import re
import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Mots-clés BOOST — augmentent le score de pertinence ──────────────────────
KEYWORDS_BOOST = [
    "étudiant", "student", "job étudiant", "extra", "saisonnier",
    "week-end", "weekend", "temps partiel", "mi-temps", "appoint",
    "vacances", "été", "job d'été", "babysitter", "animateur",
    "caissier", "serveur", "livreur", "hôte",
    # Mentions positives explicites pour profils débutants
    "débutant accepté", "débutants acceptés", "sans expérience requise",
    "sans expérience", "premier emploi", "formation assurée",
    "ouvert aux étudiants", "profil junior", "junior bienvenu",
]

# ── Mots-clés d'EXCLUSION DURE — présence → offre écartée (pas juste pénalisée)
# Anciens KEYWORDS_PENALITE promus en filtre dur.
KEYWORDS_EXCLUSION = [
    # Séniorité / profil expérimenté
    "senior", "sénior", "confirmé", "expérimenté",
    "expérience exigée", "expérience significative",
    "profil expérimenté", "autonome sur le poste",
    # Postes de management / encadrement
    "manager", "directeur", "responsable", "chef de projet", "cadre",
    # Diplôme élevé (filet de sécurité — déjà filtré source par source)
    "bac+2", "bac+3", "bac+4", "bac+5", "master", "ingénieur", "licence",
]

# ── Regex durée d'expérience en années ───────────────────────────────────────
# Ne cible PAS les mois — voir docstring module.
_EXP_ANNEES_RE = re.compile(
    r"(\d+)\s*an[s]?\s+d.{0,10}expérience"
    r"|expérience\s+de\s+(\d+)\s*an[s]?"
    r"|(\d+)\s*an[s]?\s+(?:mini(?:mum)?|requi\w*)",
    re.IGNORECASE,
)

# Seuil d'exclusion en années (décision validée : 2 ans)
SEUIL_ANNEES_EXP = 2

LABELS_CONTRAT = {
    "CDD": "CDD",
    "MIS": "Intérim",
    "SAI": "Saisonnier",
    "CDI": "CDI",
    "APP": "Alternance",   # Apprentissage et Professionnalisation (La Bonne Alternance)
    "":   "Non précisé",
}


def _annees_experience_max(text: str) -> int:
    """Retourne le plus grand nombre d'années d'expérience trouvé dans text, ou 0."""
    max_val = 0
    for m in _EXP_ANNEES_RE.finditer(text):
        val = next((int(g) for g in m.groups() if g is not None), 0)
        max_val = max(max_val, val)
    return max_val


def is_offre_exclue(offre: dict) -> bool:
    """
    Filtre dur d'exclusion "débutant / sans expérience".
    Retourne True si l'offre doit être écartée.

    Vérifie deux critères indépendants sur titre + description :
      1. Présence d'un mot-clé de séniorité/diplôme élevé (KEYWORDS_EXCLUSION)
      2. Mention explicite d'une durée d'expérience ≥ SEUIL_ANNEES_EXP ans
    """
    text = f"{offre.get('titre', '')} {offre.get('description', '')}".lower()

    for kw in KEYWORDS_EXCLUSION:
        if kw in text:
            return True

    if _annees_experience_max(text) >= SEUIL_ANNEES_EXP:
        return True

    return False


def normalise_key(titre: str, entreprise: str, lieu: str) -> str:
    """Génère la clé de déduplication."""
    raw = re.sub(r"[^a-z0-9]", "", f"{titre}{entreprise}{lieu}".lower())
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def score_pertinence(offre: dict) -> int:
    """
    Score de pertinence pour classer les offres (plus haut = plus pertinent).
    N'est appelé que sur des offres ayant déjà passé is_offre_exclue().
    """
    text = f"{offre.get('titre', '')} {offre.get('description', '')}".lower()
    score = 0

    for kw in KEYWORDS_BOOST:
        if kw in text:
            score += 2

    # Pénalité douce si expérience souhaitée (signal structuré France Travail uniquement)
    # "Souhaitée" ≠ "Exigée" : l'offre reste accessible à un débutant motivé.
    if offre.get("experience_exige") == "S":
        score -= 2

    # Bonus récence
    try:
        days_old = (datetime.today() - datetime.fromisoformat(offre["date_publication"])).days
        if days_old <= 3:
            score += 3
        elif days_old <= 7:
            score += 1
    except Exception:
        pass

    return score


def label_contrat(code: str) -> str:
    return LABELS_CONTRAT.get(code, code)


def merge(sources: list[list[dict]]) -> list[dict]:
    """
    Fusionne plusieurs listes d'offres, applique le filtre dur d'exclusion,
    déduplique et retourne la liste triée par score décroissant puis date descendante.
    """
    seen: dict[str, dict] = {}
    exclus = 0

    for source_list in sources:
        for offre in source_list:
            if is_offre_exclue(offre):
                exclus += 1
                continue

            key = normalise_key(
                offre.get("titre", ""),
                offre.get("entreprise", ""),
                offre.get("lieu", ""),
            )
            if key not in seen:
                offre["type_contrat_label"] = label_contrat(offre.get("type_contrat", ""))
                offre["_score"] = score_pertinence(offre)
                seen[key] = offre
            else:
                # Garder la source la plus fiable (france_travail > alternance/adzuna > rss)
                priority = {"france_travail": 3, "alternance": 2, "adzuna": 2}
                current_prio  = priority.get(seen[key]["source"], 1)
                incoming_prio = priority.get(offre["source"],     1)
                if incoming_prio > current_prio:
                    offre["type_contrat_label"] = label_contrat(offre.get("type_contrat", ""))
                    offre["_score"] = score_pertinence(offre)
                    seen[key] = offre

    offres = list(seen.values())

    def sort_key(o):
        date_str = o.get("date_publication") or "1970-01-01"
        try:
            date_val = datetime.fromisoformat(date_str)
        except Exception:
            date_val = datetime(1970, 1, 1)
        return (o["_score"], date_val)

    offres.sort(key=sort_key, reverse=True)

    for o in offres:
        o.pop("_score", None)

    logger.info(
        f"[Merge] {len(offres)} offres conservées, {exclus} exclues par le filtre débutant."
    )
    return offres
