"""
Génère index.html depuis le template Jinja2 et les données offres.json.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "offres.json"
TMPL_DIR  = ROOT / "templates"
OUT_FILE  = ROOT / "index.html"


def generate():
    if not DATA_FILE.exists():
        logger.error(f"Fichier {DATA_FILE} introuvable — génération annulée.")
        return

    with open(DATA_FILE, encoding="utf-8") as f:
        payload = json.load(f)

    offres         = payload.get("offres", [])
    last_update    = payload.get("last_update", datetime.today().strftime("%d/%m/%Y à %Hh%M"))
    total          = len(offres)

    env      = Environment(
        loader=FileSystemLoader(str(TMPL_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    html     = template.render(
        offres=offres,
        last_update=last_update,
        total=total,
        annee=datetime.today().year,
    )

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"[Generate] {OUT_FILE} généré avec {total} offres.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate()
