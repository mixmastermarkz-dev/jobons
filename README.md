# JobOns — Jobs étudiants Montpellier

Site statique mis à jour chaque jour automatiquement via GitHub Actions.
Agrège les offres CDD / Intérim / Saisonnier à Montpellier, Lattes et Pérols,
filtrées pour les étudiants (max 20h/sem, sans qualification requise).

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

## Lancer les tests

```bash
pytest tests/
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

## Déploiement sur GitHub

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
| `FTP_HOST`                    | serveur FTP OVH         |
| `FTP_USERNAME`                | identifiant FTP         |
| `FTP_PASSWORD`                | mot de passe FTP        |

### 3. Activer le workflow (premier lancement)

GitHub → Actions → "Mise à jour quotidienne des offres" → Run workflow

---

## Structure du projet

```
jobons/
├── .github/workflows/
│   └── daily-fetch.yml     # Cron 6h UTC + gitleaks + déploiement FTP
├── scripts/
│   ├── fetch_jobs.py        # Orchestrateur principal
│   ├── fetch_france_travail.py
│   ├── fetch_adzuna.py
│   ├── fetch_rss.py         # Sources RSS (désactivées — voir état ci-dessous)
│   ├── merge_jobs.py        # Fusion + déduplication + filtre débutant
│   └── generate_site.py     # Rendu Jinja2 (autoescape activé)
├── templates/
│   └── index.html.j2
├── static/
│   ├── style.css
│   └── app.js               # Filtrage côté client
├── tests/
│   └── test_filtrage.py     # Tests unitaires logique de filtrage
├── data/
│   ├── offres.json          # État courant
│   └── history/             # Archives YYYY-MM-DD.json (rétention 90 jours)
├── index.html               # Généré automatiquement
├── .gitleaks.toml           # Configuration scan secrets CI
├── .env.example
└── requirements.txt
```

---

## Logique de filtrage "débutant / sans expérience"

### Critères d'inclusion (toutes sources)

- Type de contrat : CDD, Intérim (MIS), Saisonnier (SAI)
- Durée hebdomadaire : max 20h/semaine
- Localisation : Montpellier, Lattes, Pérols

### Filtre diplôme

Offres exigeant Bac+2 ou plus exclues au niveau de chaque source.

### Filtre expérience — deux niveaux indépendants

**Niveau 1 — Signal structuré (France Travail uniquement)**

L'API France Travail expose le champ `experienceExige` :

| Valeur | Signification         | Comportement                                               |
|--------|-----------------------|------------------------------------------------------------|
| `D`    | Débutant accepté      | Conservé sans condition                                    |
| `S`    | Souhaitée             | Conservé, pénalité de score (offre moins prioritaire)      |
| `E`    | Exigée                | Exclu, **sauf** si `experienceLibelle` indique < 2 ans     |
| `""`   | Non précisé           | Conservé (bénéfice du doute)                               |

**Niveau 2 — Filtre textuel / heuristique (toutes sources)**

Appliqué dans `merge_jobs.py` sur titre + description :

- **Exclusion dure** si présence d'un mot-clé de séniorité : `senior`, `sénior`,
  `confirmé`, `expérimenté`, `expérience exigée`, `expérience significative`,
  `profil expérimenté`, `autonome sur le poste`, `manager`, `directeur`,
  `responsable`, `chef de projet`, `cadre`
- **Exclusion dure** si mention d'une durée d'expérience ≥ **2 ans** via regex
  (`"X an(s) d'expérience"`, `"expérience de X ans"`, `"X ans minimum"`)
- Les mentions en **mois** (ex. "6 mois d'expérience") ne sont **pas** ciblées
  par le regex — comportement volontaire documenté

**Fiabilité par source :**

| Source        | Filtre expérience | Fiabilité                              |
|---------------|-------------------|----------------------------------------|
| France Travail| Structuré + texte | Élevée (champ API dédié)               |
| Adzuna        | Textuel seulement | Heuristique (pas de champ structuré)   |
| RSS           | Textuel seulement | Heuristique (pas de champ structuré)   |

---

## Sources de données

| Source        | Type  | État       | Notes                                      |
|---------------|-------|------------|--------------------------------------------|
| France Travail| API   | ✅ Actif   | OAuth2, champ expérience structuré         |
| Adzuna        | API   | ✅ Actif   | REST, type contrat inféré                  |
| Jobijoba      | RSS   | ❌ Inactif | HTTP 404 — flux supprimé (rachat Indeed)   |
| HelloWork     | RSS   | ❌ Inactif | RSS supprimé (retourne du HTML)            |

Les sources RSS désactivées sont conservées dans le code pour traçabilité et
pourront être remplacées dans une itération future.

Sources exclues par CGU : **Indeed**, **LinkedIn**, **Leboncoin**.

---

## Contraintes légales

- Seules les APIs officielles (France Travail, Adzuna) et les flux RSS autorisés sont utilisés.
- Indeed, LinkedIn et Leboncoin sont **exclus** (CGU l'interdisent).
- User-Agent identifiable pour toute requête HTTP.
- Aucune clé API en clair dans le code — utiliser `.env` en local, secrets GitHub en production.
