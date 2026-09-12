"""
Récupère les offres depuis l'API Adzuna (source complémentaire).
Documentation : https://developer.adzuna.com/
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/{page}"

VILLES = ["Montpellier", "Pérols", "Lattes"]

# Fake credentials pour développement local
FAKE_APP_ID  = "FAKE_APP_ID_REPLACE_ME"
FAKE_APP_KEY = "FAKE_APP_KEY_REPLACE_ME"

# Mots-clés pour cibler les jobs étudiants
KEYWORDS = "job étudiant temps partiel extra saisonnier week-end"


def fetch_page(app_id: str, app_key: str, ville: str, page: int = 1) -> list[dict]:
    """Récupère une page de résultats Adzuna."""
    try:
        resp = requests.get(
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
    # Exclure les offres qui mentionnent explicitement un diplôme élevé
    desc = (raw.get("description") or "").lower()
    titre = (raw.get("title") or "").lower()
    for exclu in ["bac+2", "bac+3", "bac+4", "bac+5", "master", "licence", "ingénieur"]:
        if exclu in desc or exclu in titre:
            return None

    location = raw.get("location", {})
    area = location.get("area", [])
    lieu = area[-1] if area else "Montpellier"

    return {
        "id":               raw.get("id", ""),
        "titre":            (raw.get("title") or "").title(),
        "entreprise":       raw.get("company", {}).get("display_name", "Entreprise non précisée"),
        "lieu":             f"{lieu} (34)",
        "date_publication": (raw.get("created") or "")[:10],
        "type_contrat":     "CDD",
        "duree_hebdo":      "Temps partiel",
        "secteur":          raw.get("category", {}).get("label", ""),
        "description":      (raw.get("description") or "")[:300].strip(),
        "url":              raw.get("redirect_url", ""),
        "source":           "adzuna",
        "niveau_formation": "Non précisé",
    }


def fetch() -> list[dict]:
    """Point d'entrée principal."""
    app_id  = os.getenv("ADZUNA_APP_ID",  FAKE_APP_ID)
    app_key = os.getenv("ADZUNA_APP_KEY", FAKE_APP_KEY)

    if "FAKE" in app_id:
        logger.warning("[Adzuna] Clé API absente — source ignorée.")
        return []

    offres = []
    for ville in VILLES:
        raws = fetch_page(app_id, app_key, ville)
        for raw in raws:
            job = normalise(raw)
            if job:
                offres.append(job)
        logger.info(f"[Adzuna] {ville} → {len(raws)} offres brutes")

    logger.info(f"[Adzuna] Total après filtrage : {len(offres)} offres")
    return offres
