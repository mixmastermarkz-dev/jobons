"""
Test isolé — demande de token France Travail uniquement.
Usage : python scripts/test_token_ft.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=%2Fpartenaire"
)

client_id     = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "")
client_secret = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "")

if not client_id or not client_secret:
    print("ERREUR : FRANCE_TRAVAIL_CLIENT_ID ou CLIENT_SECRET manquant dans .env")
    sys.exit(1)

print(f"Client ID  : {client_id[:20]}...")
print(f"Endpoint   : {TOKEN_URL}")
print(f"Scope      : api_offresdemploiv2 o2dsoffre")
print()

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

print(f"HTTP status : {resp.status_code}")
print(f"Réponse     : {resp.text[:600]}")

if resp.status_code == 200:
    token = resp.json().get("access_token", "")
    print(f"\nToken OK : {token[:40]}...")

    # Test rapide de l'endpoint de recherche
    SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    r2 = requests.get(
        SEARCH_URL,
        params={"commune": "34172", "typeContrat": "CDD", "range": "0-2"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    print(f"\nSearch HTTP : {r2.status_code}")
    if r2.status_code in (200, 206):
        resultats = r2.json().get("resultats", [])
        print(f"Offres reçues : {len(resultats)}")
        for o in resultats:
            print(f"  - {o.get('intitule', '')} | {o.get('entreprise', {}).get('nom', '')}")
    else:
        print(f"Search error : {r2.text[:400]}")
else:
    print("\nEchec authentification — vérifier :")
    print("  1. Les credentials dans .env")
    print("  2. Que l'app est souscrite à l'API 'Offres d'emploi v2' sur francetravail.io")
