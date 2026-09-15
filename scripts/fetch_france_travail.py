"""
Récupère les offres d'emploi étudiant depuis l'API France Travail (ex Pôle Emploi).
Documentation : https://francetravail.io/data/api/offres-emploi

─── Filtrage expérience ────────────────────────────────────────────────────────
Ce module exploite le champ structuré `experienceExige` de l'API (source fiable) :
  "D" = débutant accepté  → toujours conservé
  "S" = souhaitée         → conservé, pénalité de score dans merge_jobs.py
  "E" = exigée            → exclu, SAUF si experienceLibelle indique un seuil
                            compatible (< 2 ans, débutant, etc.)
  ""  = non précisé       → conservé (bénéfice du doute)

Ce signal structuré est plus fiable que le filtrage textuel appliqué sur Adzuna/RSS
dans merge_jobs.py. Les deux filtres sont complémentaires et indépendants.
"""

import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Codes INSEE des communes cibles
COMMUNES = {
    "Montpellier": "34172",
    "Pérols":      "34249",
    "Lattes":      "34129",
}

# Types de contrats adaptés aux étudiants
TYPES_CONTRAT = ["CDD", "MIS", "SAI"]  # CDD, Intérim, Saisonnier

TOKEN_URL  = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

FAKE_CLIENT_ID     = "FAKE_CLIENT_ID_REPLACE_ME"
FAKE_CLIENT_SECRET = "FAKE_CLIENT_SECRET_REPLACE_ME"

# Mots dans experienceLibelle indiquant un seuil compatible avec un profil débutant
_LIBELLES_EXP_COMPAT = [
    "débutant", "moins d'un an", "moins de 1 an", "inférieur à 1 an",
    "< 1 an", "junior", "6 mois",
]


def _make_session() -> requests.Session:
    """Session HTTP avec retry automatique (backoff exponentiel)."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def get_token(client_id: str, client_secret: str) -> str | None:
    """Obtient un token OAuth2 France Travail."""
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     client_id,
                "client_secret": client_secret,
                "scope":         "api_offresdemploiv2 o2dsoffre",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if not resp.ok:
            # Limité à 200 chars pour éviter de logger accidentellement des credentials
            logger.warning(
                f"[FranceTravail] Échec token — HTTP {resp.status_code} : {resp.text[:200]}"
            )
            return None
        return resp.json()["access_token"]
    except Exception as e:
        logger.warning(f"[FranceTravail] Impossible d'obtenir le token : {e}")
        return None


def search_offres(session: requests.Session, token: str, commune_code: str, type_contrat: str) -> list[dict]:
    """Lance une recherche d'offres pour une commune et un type de contrat."""
    params = {
        "commune":              commune_code,
        "typeContrat":          type_contrat,
        "tempsPlein":           "false",
        "dureeHebdoTravailMax": 20,
        "range":                "0-49",
    }
    try:
        resp = session.get(
            SEARCH_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        return resp.json().get("resultats", [])
    except Exception as e:
        logger.warning(
            f"[FranceTravail] Erreur recherche commune={commune_code} contrat={type_contrat} : {e}"
        )
        return []


def _exp_exige_compatible(exp_libelle: str) -> bool:
    """
    Retourne True si experienceLibelle indique un seuil d'expérience compatible
    avec un profil débutant (< 2 ans ou mention explicite "débutant").
    Utilisé uniquement quand experienceExige == "E".
    """
    libelle_lower = exp_libelle.lower()
    return any(m in libelle_lower for m in _LIBELLES_EXP_COMPAT)


def normalise(raw: dict, commune_name: str) -> dict | None:
    """
    Normalise une offre brute France Travail vers le format commun.
    Retourne None si l'offre doit être exclue (niveau trop élevé ou expérience exigée).
    """
    # ── Filtre diplôme ────────────────────────────────────────────────────────
    formation  = raw.get("formations", [{}])[0] if raw.get("formations") else {}
    niveau_raw = formation.get("niveauLibelle", "")
    if niveau_raw and not any(
        n in niveau_raw.lower() for n in ["sans", "cap", "bep", "bac", "pas de diplôme"]
    ):
        return None

    # ── Filtre expérience (signal structuré API) ──────────────────────────────
    exp_exige   = raw.get("experienceExige", "")          # "D" / "S" / "E" / ""
    exp_libelle = (raw.get("experienceLibelle") or "")

    if exp_exige == "E" and not _exp_exige_compatible(exp_libelle):
        return None  # Expérience exigée sans seuil compatible → écarté

    # ── Validation URL ────────────────────────────────────────────────────────
    url_raw = (
        raw.get("origineOffre", {}).get("urlOrigine")
        or f"https://candidat.francetravail.fr/offres/recherche/detail/{raw.get('id', '')}"
    )
    url = url_raw if url_raw.startswith(("https://", "http://")) else ""

    return {
        "id":               raw.get("id", ""),
        "titre":            raw.get("intitule", "").title(),
        "entreprise":       raw.get("entreprise", {}).get("nom", "Entreprise non précisée"),
        "lieu":             f"{commune_name} ({raw.get('lieuTravail', {}).get('codePostal', '34')})",
        "date_publication": raw.get("dateCreation", "")[:10],
        "type_contrat":     raw.get("typeContrat", "CDD"),
        "duree_hebdo":      raw.get("dureeTravailLibelleConverti", "Temps partiel"),
        "secteur":          raw.get("secteurActiviteLibelle", ""),
        "description":      (raw.get("description") or "")[:300].strip(),
        "url":              url,
        "source":           "france_travail",
        "niveau_formation": niveau_raw or "Non précisé",
        # Signal structuré transmis à merge_jobs.py pour la pénalité de score ("S")
        "experience_exige": exp_exige,
    }


def fetch() -> list[dict]:
    """Point d'entrée principal — retourne la liste normalisée des offres."""
    client_id     = os.getenv("FRANCE_TRAVAIL_CLIENT_ID",     FAKE_CLIENT_ID)
    client_secret = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", FAKE_CLIENT_SECRET)

    if "FAKE" in client_id:
        logger.warning("[FranceTravail] Clé API absente — source ignorée.")
        return []

    token = get_token(client_id, client_secret)
    if not token:
        return []

    session = _make_session()
    offres  = []

    for commune_name, commune_code in COMMUNES.items():
        for type_contrat in TYPES_CONTRAT:
            raws = search_offres(session, token, commune_code, type_contrat)
            for raw in raws:
                job = normalise(raw, commune_name)
                if job:
                    offres.append(job)
            logger.info(
                f"[FranceTravail] {commune_name} / {type_contrat} → {len(raws)} offres brutes"
            )

    logger.info(f"[FranceTravail] Total après filtrage : {len(offres)} offres")
    return offres
