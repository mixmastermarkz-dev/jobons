# JobOns — Jobs étudiants Montpellier

Site statique mis à jour chaque jour automatiquement via GitHub Actions.
Agrège les offres CDD / Intérim / Saisonnier à Montpellier, Lattes et Pérols,
filtrées pour les étudiants (max 20h/sem, sans diplôme requis).

---

## Démarrage rapide (local)

```bash
# 1. Cloner le repo
git clone https://github.com/TON_USERNAME/jobons.git
cd jobons

# 2. Installer les dépendances Python
pip install -r requirements.txt

# 3. Copier .env.example et remplir les clés API
cp .env.example .env
# Editer .env avec tes clés

# 4. Lancer le pipeline
python scripts/fetch_jobs.py

# 5. Ouvrir index.html dans un navigateur
```

---

## Obtenir les clés API

### France Travail (source principale)

1. Aller sur https://francetravail.io
2. Créer un compte développeur
3. Créer une application → noter `client_id` et `client_secret`
4. Activer le scope `api_offresdemploiv2`

### Adzuna (source complémentaire)

1. Aller sur https://developer.adzuna.com/
2. Créer un compte gratuit → noter `app_id` et `app_key`

---

## Déploiement sur GitHub + GitHub Pages

### 1. Créer le repo GitHub

```bash
gh repo create jobons --public --source=. --push
```

### 2. Ajouter les secrets

Dans GitHub → Settings → Secrets → Actions, ajouter :

| Nom                           | Valeur                  |
|-------------------------------|-------------------------|
| `FRANCE_TRAVAIL_CLIENT_ID`    | ton client_id           |
| `FRANCE_TRAVAIL_CLIENT_SECRET`| ton client_secret       |
| `ADZUNA_APP_ID`               | ton app_id              |
| `ADZUNA_APP_KEY`              | ton app_key             |

### 3. Activer GitHub Pages

GitHub → Settings → Pages → Source : **Deploy from a branch** → branche `main` → dossier `/ (root)`

Le site sera disponible à : `https://TON_USERNAME.github.io/jobons/`

### 4. Activer le workflow (premier lancement)

GitHub → Actions → "Mise à jour quotidienne des offres" → Run workflow

---

## Structure du projet

```
jobons/
├── .github/workflows/
│   └── daily-fetch.yml     # Cron 6h UTC + déploiement
├── scripts/
│   ├── fetch_jobs.py        # Orchestrateur principal
│   ├── fetch_france_travail.py
│   ├── fetch_adzuna.py
│   ├── fetch_rss.py         # Jobijoba, HelloWork (RSS)
│   ├── merge_jobs.py        # Fusion + déduplication
│   └── generate_site.py     # Rendu Jinja2
├── templates/
│   └── index.html.j2
├── static/
│   ├── style.css
│   └── app.js               # Filtrage côté client
├── data/
│   ├── offres.json          # État courant
│   └── history/             # Archives YYYY-MM-DD.json
├── index.html               # Généré automatiquement
├── .env.example
└── requirements.txt
```

---

## Contraintes légales

- Seules les APIs officielles (France Travail, Adzuna) et les flux RSS autorisés sont utilisés.
- Indeed, LinkedIn et Leboncoin sont **exclus** (CGU l'interdisent).
- User-Agent identifiable pour toute requête HTTP.
- Aucune clé API en clair dans le code — utiliser `.env` en local, secrets GitHub en production.
