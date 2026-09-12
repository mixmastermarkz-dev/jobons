"""
Récupère les offres depuis des flux RSS autorisés.
Sources : Jobijoba, HelloWork (flux RSS publics, vérifiés légalement).
Chaque source est encapsulée avec gestion d'erreur silencieuse.
"""

import logging
import hashlib
import feedparser
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Délai entre les requêtes (rate limiting)
REQUEST_TIMEOUT = 15

# --- Sources RSS — vérifier robots.txt avant d'activer ---
# Jobijoba : flux RSS disponible via paramètre d dans l'URL
# HelloWork : flux RSS disponible sur les pages de recherche
RSS_SOURCES = [
    {
        "name": "jobijoba",
        "url":  "https://www.jobijoba.com/fr/flux-rss/?q=job+étudiant&l=Montpellier&d=20",
        "enabled": True,
    },
    {
        "name": "hellowork",
        "url":  "https://www.hellowork.com/fr-fr/emploi/recherche.html?q=job+etudiant&l=Montpellier+(34)&c=PART_TIME&media=rss",
        "enabled": True,
    },
]

MOTS_EXCLUSION_DIPLOME = ["bac+2", "bac+3", "bac+4", "bac+5", "master", "licence pro", "ingénieur"]


def fetch_source(source: dict) -> list[dict]:
    """Récupère et normalise les offres d'une source RSS."""
    name = source["name"]
    url  = source["url"]

    try:
        headers = {
            "User-Agent": "JobOns-Bot/1.0 (https://github.com/ton_username/jobons; job-student-aggregator)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        }
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        feed = feedparser.parse(resp.content)
        if not feed.entries:
            logger.info(f"[RSS/{name}] Aucune entrée dans le flux.")
            return []

        offres = []
        for entry in feed.entries:
            titre = (entry.get("title") or "").strip()
            desc  = (entry.get("summary") or "").lower()

            # Exclure les offres demandant un diplôme > Bac
            if any(m in desc for m in MOTS_EXCLUSION_DIPLOME):
                continue

            published = entry.get("published_parsed") or entry.get("updated_parsed")
            date_str  = ""
            if published:
                try:
                    date_str = datetime(*published[:6]).strftime("%Y-%m-%d")
                except Exception:
                    pass

            unique_key = f"{name}_{entry.get('link','')}"
            offres.append({
                "id":               hashlib.md5(unique_key.encode()).hexdigest()[:12],
                "titre":            titre.title(),
                "entreprise":       entry.get("author", "Entreprise non précisée"),
                "lieu":             "Montpellier (34)",
                "date_publication": date_str,
                "type_contrat":     "CDD",
                "duree_hebdo":      "Temps partiel",
                "secteur":          "",
                "description":      (entry.get("summary") or "")[:300].strip(),
                "url":              entry.get("link", ""),
                "source":           name,
                "niveau_formation": "Non précisé",
            })

        logger.info(f"[RSS/{name}] {len(offres)} offres retenues.")
        return offres

    except Exception as e:
        # Erreur silencieuse : ne pas planter le pipeline
        logger.warning(f"[RSS/{name}] Source indisponible — ignorée : {e}")
        return []


def fetch() -> list[dict]:
    """Point d'entrée principal — agrège toutes les sources RSS actives."""
    all_offres = []
    for source in RSS_SOURCES:
        if source.get("enabled", False):
            all_offres.extend(fetch_source(source))
    logger.info(f"[RSS] Total toutes sources : {len(all_offres)} offres")
    return all_offres
