"""
Fusionne les offres de toutes les sources, déduplique et trie par pertinence.
Clé de déduplication : hash(titre_normalisé + entreprise_normalisée + lieu_normalisé).
"""

import re
import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Mots-clés qui augmentent le score de pertinence "job étudiant"
KEYWORDS_BOOST = [
    "étudiant", "student", "job étudiant", "extra", "saisonnier",
    "week-end", "weekend", "temps partiel", "mi-temps", "appoint",
    "vacances", "été", "job d'été", "babysitter", "animateur",
    "caissier", "serveur", "livreur", "hôte",
]

# Mots qui pénalisent (poste trop senior ou diplôme requis)
KEYWORDS_PENALITE = [
    "manager", "directeur", "responsable", "chef de projet",
    "bac+2", "bac+3", "bac+4", "bac+5", "master", "ingénieur", "licence",
    "5 ans d'expérience", "10 ans", "cadre",
]

LABELS_CONTRAT = {
    "CDD":  "CDD",
    "MIS":  "Intérim",
    "SAI":  "Saisonnier",
    "CDI":  "CDI",
    "":     "Non précisé",
}


def normalise_key(titre: str, entreprise: str, lieu: str) -> str:
    """Génère la clé de déduplication."""
    raw = re.sub(r"[^a-z0-9]", "", f"{titre}{entreprise}{lieu}".lower())
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def score_pertinence(offre: dict) -> int:
    """Score de pertinence pour classer les offres (plus haut = plus pertinent)."""
    text = f"{offre.get('titre','')} {offre.get('description','')}".lower()
    score = 0
    for kw in KEYWORDS_BOOST:
        if kw in text:
            score += 2
    for kw in KEYWORDS_PENALITE:
        if kw in text:
            score -= 3
    # Bonus si date récente
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
    Fusionne plusieurs listes d'offres, déduplique, filtre les non-pertinentes
    et retourne la liste triée par score décroissant puis date descendante.
    """
    seen: dict[str, dict] = {}

    for source_list in sources:
        for offre in source_list:
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
                # Garder la source la plus fiable (france_travail > adzuna > rss)
                priority = {"france_travail": 3, "adzuna": 2}
                current_prio  = priority.get(seen[key]["source"], 1)
                incoming_prio = priority.get(offre["source"],     1)
                if incoming_prio > current_prio:
                    offre["type_contrat_label"] = label_contrat(offre.get("type_contrat", ""))
                    offre["_score"] = score_pertinence(offre)
                    seen[key] = offre

    offres = list(seen.values())

    # Trier : score décroissant, puis date décroissante
    def sort_key(o):
        date_str = o.get("date_publication") or "1970-01-01"
        try:
            date_val = datetime.fromisoformat(date_str)
        except Exception:
            date_val = datetime(1970, 1, 1)
        return (o["_score"], date_val)

    offres.sort(key=sort_key, reverse=True)

    # Supprimer le champ interne avant export
    for o in offres:
        o.pop("_score", None)

    logger.info(f"[Merge] {len(offres)} offres uniques après déduplication.")
    return offres
