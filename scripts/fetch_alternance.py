"""
Récupère les offres d'alternance depuis l'API Apprentissage — La Bonne Alternance.
Documentation : https://api.apprentissage.beta.gouv.fr/fr/explorer
Utilisation non commerciale uniquement (licence etalab-2.0).

─── Périmètre ──────────────────────────────────────────────────────────────────
Contrats : Apprentissage + Professionnalisation (type_contrat = "APP")
Zone     : rayon 30 km autour de Montpellier, département 34
Diplômes : niveau 3 (CAP/BEP) et niveau 4 (Bac) — deux requêtes séparées
           (l'API n'accepte qu'un niveau par appel)

─── Filtrage expérience ────────────────────────────────────────────────────────
L'alternance s'adresse par définition aux débutants (formation en entreprise).
Pas de champ structuré experienceExige — le filtre textuel de merge_jobs.py
s'applique en filet de sécurité.
"""

import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL   = "https://api.apprentissage.beta.gouv.fr/api"
SEARCH_URL = f"{BASE_URL}/job/v1/search"

# Centre de recherche : Montpellier
LATITUDE   = 43.6047
LONGITUDE  = 3.8737
RADIUS_KM  = 30

# Niveaux de diplôme ciblés (deux appels séparés — contrainte de l'API)
# "3" = CAP/BEP (niveau 3 européen), "4" = Bac (niveau 4 européen)
TARGET_DIPLOMA_LEVELS = ["3", "4"]

FAKE_API_KEY = "FAKE_APPRENTISSAGE_API_KEY_REPLACE_ME"


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def search_offres(session: requests.Session, api_key: str, diploma_level: str) -> list[dict]:
    """Recherche les offres d'alternance pour un niveau de diplôme donné."""
    try:
        resp = session.get(
            SEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "latitude":             LATITUDE,
                "longitude":            LONGITUDE,
                "radius":               RADIUS_KM,
                "target_diploma_level": diploma_level,
                "departements":         ["34"],
            },
            timeout=25,
        )
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        return resp.json().get("jobs", [])
    except Exception as e:
        logger.warning(f"[Alternance] Erreur niveau={diploma_level} : {e}")
        return []


def normalise(raw: dict) -> dict | None:
    """Normalise une offre brute LBA vers le format commun."""
    offer     = raw.get("offer", {})
    workplace = raw.get("workplace", {})
    apply_    = raw.get("apply", {})
    contract  = raw.get("contract", {})
    identifier = raw.get("identifier", {})

    # Ignorer les offres déjà pourvues ou annulées
    if offer.get("status") in ("Filled", "Cancelled"):
        return None

    titre = (offer.get("title") or "").strip()
    if not titre:
        return None

    # Entreprise : nom commercial en priorité, sinon raison sociale
    entreprise = (
        workplace.get("name")
        or workplace.get("legal_name")
        or "Entreprise non précisée"
    )

    # Lieu : adresse de l'entreprise, tronquée à 60 caractères
    location = workplace.get("location", {})
    lieu = (location.get("address") or "Montpellier (34)")[:60].strip()

    # Date de publication
    date_raw       = (offer.get("publication") or {}).get("creation") or ""
    date_publication = date_raw[:10] if date_raw else ""

    # Niveau de diplôme ciblé
    target_diploma   = offer.get("target_diploma") or {}
    niveau_formation = target_diploma.get("label") or "Non précisé"

    # Description
    description = (offer.get("description") or "")[:300].strip()

    # URL candidature — validation schéma
    url_raw = (apply_.get("url") or "").strip()
    url = url_raw if url_raw.startswith(("https://", "http://")) else ""

    # Identifiant unique
    job_id = str(identifier.get("partner_job_id") or identifier.get("id") or "")

    # Secteur (code NAF libellé)
    naf    = (workplace.get("domain") or {}).get("naf") or {}
    secteur = naf.get("label") or ""

    return {
        "id":               job_id,
        "titre":            titre.title(),
        "entreprise":       entreprise,
        "lieu":             lieu,
        "date_publication": date_publication,
        "type_contrat":     "APP",   # Apprentissage ou Professionnalisation → label "Alternance"
        "duree_hebdo":      "Alternance",
        "secteur":          secteur,
        "description":      description,
        "url":              url,
        "source":           "alternance",
        "niveau_formation": niveau_formation,
        # Alternance = profil débutant par définition ; filtre textuel dans merge_jobs en filet
        "experience_exige": "",
    }


def fetch() -> list[dict]:
    """Point d'entrée principal — retourne la liste normalisée des offres d'alternance."""
    api_key = os.getenv("APPRENTISSAGE_API_KEY", FAKE_API_KEY)

    if "FAKE" in api_key:
        logger.warning("[Alternance] Clé API absente — source ignorée.")
        return []

    session  = _make_session()
    offres   = []
    seen_ids: set[str] = set()

    for level in TARGET_DIPLOMA_LEVELS:
        raws = search_offres(session, api_key, level)
        for raw in raws:
            job = normalise(raw)
            if job and job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                offres.append(job)
        logger.info(f"[Alternance] Niveau {level} → {len(raws)} offres brutes")

    logger.info(f"[Alternance] Total après filtrage : {len(offres)} offres")
    return offres
