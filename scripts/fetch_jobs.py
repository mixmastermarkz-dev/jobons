"""
Script principal — orchestration du pipeline quotidien :
1. Récupère les offres de chaque source
2. Fusionne et déduplique
3. Sauvegarde data/offres.json + archive historique
4. Génère index.html
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ajout du dossier parent au path pour imports relatifs
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import fetch_france_travail, fetch_adzuna, fetch_rss
from scripts.merge_jobs import merge
from scripts.generate_site import generate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

ROOT         = Path(__file__).parent.parent
DATA_DIR     = ROOT / "data"
HISTORY_DIR  = DATA_DIR / "history"
OFFRES_FILE  = DATA_DIR / "offres.json"


def run():
    logger.info("=== Démarrage du pipeline JobOns ===")

    DATA_DIR.mkdir(exist_ok=True)
    HISTORY_DIR.mkdir(exist_ok=True)

    # 1. Récupération des offres depuis chaque source
    sources = []

    logger.info("Récupération France Travail…")
    try:
        ft = fetch_france_travail.fetch()
        sources.append(ft)
        logger.info(f"  → {len(ft)} offres France Travail")
    except Exception as e:
        logger.warning(f"France Travail échoué : {e}")
        sources.append([])

    logger.info("Récupération Adzuna…")
    try:
        az = fetch_adzuna.fetch()
        sources.append(az)
        logger.info(f"  → {len(az)} offres Adzuna")
    except Exception as e:
        logger.warning(f"Adzuna échoué : {e}")
        sources.append([])

    logger.info("Récupération flux RSS…")
    try:
        rss = fetch_rss.fetch()
        sources.append(rss)
        logger.info(f"  → {len(rss)} offres RSS")
    except Exception as e:
        logger.warning(f"RSS échoué : {e}")
        sources.append([])

    # 2. Fusion et déduplication
    offres = merge(sources)

    # 3. Sauvegarde
    today      = datetime.today().strftime("%Y-%m-%d")
    now_label  = datetime.today().strftime("%d/%m/%Y à %Hh%M")

    payload = {
        "last_update": now_label,
        "total":       len(offres),
        "offres":      offres,
    }

    with open(OFFRES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ data/offres.json mis à jour ({len(offres)} offres)")

    archive_file = HISTORY_DIR / f"{today}.json"
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ Archive {archive_file.name} créée")

    # 4. Génération du site
    generate()
    logger.info("✓ index.html régénéré")
    logger.info(f"=== Pipeline terminé — {len(offres)} offres publiées ===")


if __name__ == "__main__":
    run()
