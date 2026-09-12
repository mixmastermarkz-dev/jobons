"""
Récupère les offres d'emploi étudiant depuis l'API France Travail (ex Pôle Emploi).
Documentation : https://francetravail.io/data/api/offres-emploi
"""

import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Codes INSEE des communes cibles
COMMUNES = {
    "Montpellier": "34172",
    "Pérols":      "34249",
    "Lattes":      "34129",
}

# Types de contrats adaptés aux étudiants
TYPES_CONTRAT = ["CDD", "MIS", "SAI"]  # CDD, Intérim, Saisonnier

# Niveaux de formation acceptés (max Bac)
# NV5 = CAP/BEP, NV4 = Bac — on exclut NV3 (Bac+2) et au-dessus
NIVEAUX_OK = {"NV5", "NV4", ""}  # "" = non précisé = accepté

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# --- Fake credentials pour développement local ---
FAKE_CLIENT_ID     = "FAKE_CLIENT_ID_REPLACE_ME"
FAKE_CLIENT_SECRET = "FAKE_CLIENT_SECRET_REPLACE_ME"


def get_token(client_id: str, client_secret: str) -> str | None:
    """Obtient un token OAuth2 France Travail."""
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        logger.warning(f"[FranceTravail] Impossible d'obtenir le token : {e}")
        return None


def search_offres(token: str, commune_code: str, type_contrat: str) -> list[dict]:
    """Lance une recherche d'offres pour une commune et un type de contrat."""
    params = {
        "commune":       commune_code,
        "typeContrat":   type_contrat,
        "tempsPlein":    "false",          # Temps partiel uniquement
        "dureeHebdoTravailMax": 20,        # Max 20h/semaine
        "range":         "0-49",           # 50 résultats max par appel
    }
    try:
        resp = requests.get(
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
        logger.warning(f"[FranceTravail] Erreur recherche commune={commune_code} contrat={type_contrat} : {e}")
        return []


def normalise(raw: dict, commune_name: str) -> dict:
    """Normalise une offre brute France Travail vers le format commun."""
    formation = raw.get("formations", [{}])[0] if raw.get("formations") else {}
    niveau_raw = formation.get("niveauLibelle", "")
    # Exclure si le niveau requis est > Bac
    if niveau_raw and not any(n in niveau_raw.lower() for n in ["sans", "cap", "bep", "bac", "pas de diplôme"]):
        return None  # Niveau trop élevé → on écarte

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
        "url":              raw.get("origineOffre", {}).get("urlOrigine") or
                            f"https://candidat.francetravail.fr/offres/recherche/detail/{raw.get('id','')}",
        "source":           "france_travail",
        "niveau_formation": niveau_raw or "Non précisé",
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

    offres = []
    for commune_name, commune_code in COMMUNES.items():
        for type_contrat in TYPES_CONTRAT:
            raws = search_offres(token, commune_code, type_contrat)
            for raw in raws:
                job = normalise(raw, commune_name)
                if job:
                    offres.append(job)
            logger.info(f"[FranceTravail] {commune_name} / {type_contrat} → {len(raws)} offres brutes")

    logger.info(f"[FranceTravail] Total après filtrage : {len(offres)} offres")
    return offres
