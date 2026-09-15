"""
Récupère les offres depuis l'API Adzuna (source complémentaire).
Documentation : https://developer.adzuna.com/

─── Type de contrat ────────────────────────────────────────────────────────────
Adzuna ne fournit pas de champ structuré fiable pour distinguer CDD / Intérim /
Saisonnier. On infère le type à partir des champs `contract_type`, `contract_time`,
du titre et de la description. En l'absence de signal clair, on retombe sur "CDD".

─── Filtrage expérience ────────────────────────────────────────────────────────
Adzuna n'expose pas de champ `experienceExige` structuré. Le filtrage dur sur
l'expérience est donc uniquement textuel / heuristique et appliqué dans
merge_jobs.py (is_offre_exclue). Le champ `experience_exige` est toujours "".
"""

import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/{page}"

VILLES = ["Montpellier", "Pérols", "Lattes"]

FAKE_APP_ID  = "FAKE_APP_ID_REPLACE_ME"
FAKE_APP_KEY = "FAKE_APP_KEY_REPLACE_ME"

KEYWORDS = "job étudiant temps partiel extra saisonnier week-end"


def _make_session() -> requests.Session:
    """Session HTTP avec retry automatique (backoff exponentiel)."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _detect_type_contrat(raw: dict) -> str:
    """
    Infère le type de contrat depuis les champs Adzuna disponibles.
    Priorité : champs structurés (contract_type, contract_time) > mots-clés textuels.
    Fallback : "CDD" si aucun signal.
    """
    contract_type = (raw.get("contract_type") or "").lower()
    contract_time = (raw.get("contract_time") or "").lower()
    titre = (raw.get("title") or "").lower()
    desc  = (raw.get("description") or "").lower()
    texte = f"{contract_type} {contract_time} {titre} {desc}"

    if any(kw in texte for kw in ["intérim", "interim", "travail temporaire", "agence d'intérim", "mission intérim"]):
        return "MIS"
    if any(kw in texte for kw in ["saisonnier", "job d'été", "job ete", "job été", "saison "]):
        return "SAI"
    return "CDD"


def fetch_page(session: requests.Session, app_id: str, app_key: str, ville: str, page: int = 1) -> list[dict]:
    """Récupère une page de résultats Adzuna."""
    try:
        resp = session.get(
            SEARCH_URL.format(page=page),
            params={
                "app_id":           app_id,
                "app_key":          app_key,
                "where":            ville,
                "what_or":          KEYWORDS,
                "results_per_page": 50,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        logger.warning(f"[Adzuna] Erreur ville={ville} page={page} : {e}")
        return []


def normalise(raw: dict) -> dict | None:
    """Normalise une offre brute Adzuna vers le format commun."""
    desc  = (raw.get("description") or "").lower()
    titre = (raw.get("title") or "").lower()

    # Exclure les offres mentionnant un diplôme élevé
    for exclu in ["bac+2", "bac+3", "bac+4", "bac+5", "master", "licence", "ingénieur"]:
        if exclu in desc or exclu in titre:
            return None

    location = raw.get("location", {})
    area = location.get("area", [])
    lieu = area[-1] if area else "Montpellier"

    # Validation URL — refuser les schémas dangereux (ex. javascript:)
    url_raw = raw.get("redirect_url", "")
    url = url_raw if url_raw.startswith(("https://", "http://")) else ""

    return {
        "id":               raw.get("id", ""),
        "titre":            (raw.get("title") or "").title(),
        "entreprise":       raw.get("company", {}).get("display_name", "Entreprise non précisée"),
        "lieu":             f"{lieu} (34)",
        "date_publication": (raw.get("created") or "")[:10],
        "type_contrat":     _detect_type_contrat(raw),
        "duree_hebdo":      "Temps partiel",
        "secteur":          raw.get("category", {}).get("label", ""),
        "description":      (raw.get("description") or "")[:300].strip(),
        "url":              url,
        "source":           "adzuna",
        "niveau_formation": "Non précisé",
        # Pas de champ structuré experienceExige chez Adzuna — filtrage textuel dans merge_jobs.py
        "experience_exige": "",
    }


def fetch() -> list[dict]:
    """Point d'entrée principal."""
    app_id  = os.getenv("ADZUNA_APP_ID",  FAKE_APP_ID)
    app_key = os.getenv("ADZUNA_APP_KEY", FAKE_APP_KEY)

    if "FAKE" in app_id:
        logger.warning("[Adzuna] Clé API absente — source ignorée.")
        return []

    session = _make_session()
    offres  = []

    for ville in VILLES:
        raws = fetch_page(session, app_id, app_key, ville)
        for raw in raws:
            job = normalise(raw)
            if job:
                offres.append(job)
        logger.info(f"[Adzuna] {ville} → {len(raws)} offres brutes")

    logger.info(f"[Adzuna] Total après filtrage : {len(offres)} offres")
    return offres
