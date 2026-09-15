"""
Tests unitaires — logique de filtrage "débutant / sans expérience".

Couvre :
  - is_offre_exclue() : filtre dur dans merge_jobs.py
  - normalise()       : filtre experienceExige dans fetch_france_travail.py
  - score_pertinence(): pénalité "expérience souhaitée" dans merge_jobs.py
"""

import pytest
from scripts.merge_jobs import is_offre_exclue, score_pertinence, SEUIL_ANNEES_EXP
from scripts.fetch_france_travail import normalise as ft_normalise


# ── Helpers ───────────────────────────────────────────────────────────────────

def _offre(titre="Employé", description=""):
    """Construit une offre minimale pour les tests merge_jobs."""
    return {
        "titre": titre,
        "description": description,
        "date_publication": "2026-09-15",
        "source": "adzuna",
        "experience_exige": "",
    }


def _raw_ft(**kwargs):
    """Construit un dict brut France Travail minimal pour les tests normalise()."""
    base = {
        "id": "TEST001",
        "intitule": "Caissier",
        "entreprise": {"nom": "Supermarché Test"},
        "lieuTravail": {"codePostal": "34000"},
        "dateCreation": "2026-09-15",
        "typeContrat": "CDD",
        "dureeTravailLibelleConverti": "Temps partiel",
        "secteurActiviteLibelle": "Commerce",
        "description": "Poste de caissier temps partiel.",
        "origineOffre": {"urlOrigine": "https://example.com/offre/123"},
    }
    base.update(kwargs)
    return base


# ── Tests : filtre dur sur la durée d'expérience (regex années) ───────────────

class TestExperienceAnnees:

    def test_5ans_exclu(self):
        assert is_offre_exclue(_offre(description="5 ans d'expérience requis")) is True

    def test_3ans_exclu(self):
        assert is_offre_exclue(_offre(description="expérience de 3 ans minimum")) is True

    def test_2ans_exclu(self):
        """Seuil = 2 ans : exactement 2 ans doit être exclu."""
        assert is_offre_exclue(_offre(description="2 ans d'expérience souhaitée")) is True

    def test_1an_accepte(self):
        """1 an d'expérience reste accepté (seuil = 2 ans, décision validée)."""
        assert is_offre_exclue(_offre(description="1 an d'expérience appréciée")) is False

    def test_mois_accepte(self):
        """Les mentions en mois ne sont pas ciblées par le regex (comportement volontaire)."""
        assert is_offre_exclue(_offre(description="6 mois d'expérience appréciés")) is False

    def test_ans_minimum_exclu(self):
        assert is_offre_exclue(_offre(description="3 ans minimum requis")) is True

    def test_exp_dans_titre_exclu(self):
        assert is_offre_exclue(_offre(titre="Vendeur 3 ans d'expérience", description="")) is True

    def test_seuil_configurable(self):
        """Vérifie que le seuil est bien SEUIL_ANNEES_EXP = 2."""
        assert SEUIL_ANNEES_EXP == 2


# ── Tests : filtre dur sur les mots-clés de séniorité ────────────────────────

class TestKeywordsExclusion:

    def test_senior_exclu(self):
        assert is_offre_exclue(_offre(titre="Développeur senior")) is True

    def test_senoir_accent_exclu(self):
        assert is_offre_exclue(_offre(titre="Profil sénior recherché")) is True

    def test_confirme_exclu(self):
        assert is_offre_exclue(_offre(description="Profil confirmé exigé")) is True

    def test_experience_exigee_exclu(self):
        assert is_offre_exclue(_offre(description="Expérience exigée dans le domaine")) is True

    def test_experience_significative_exclu(self):
        assert is_offre_exclue(_offre(description="Expérience significative requise")) is True

    def test_profil_experimente_exclu(self):
        assert is_offre_exclue(_offre(description="Profil expérimenté souhaité")) is True

    def test_manager_exclu(self):
        assert is_offre_exclue(_offre(titre="Store Manager H/F")) is True

    def test_directeur_exclu(self):
        assert is_offre_exclue(_offre(titre="Directeur de restaurant")) is True

    def test_bac2_exclu(self):
        assert is_offre_exclue(_offre(description="Bac+2 minimum requis")) is True


# ── Tests : offres légitimes conservées ──────────────────────────────────────

class TestOffresAcceptees:

    def test_debutant_accepte(self):
        assert is_offre_exclue(_offre(description="Débutant accepté, formation assurée")) is False

    def test_sans_experience_accepte(self):
        assert is_offre_exclue(_offre(description="Sans expérience requise")) is False

    def test_premier_emploi_accepte(self):
        assert is_offre_exclue(_offre(description="Premier emploi bienvenu")) is False

    def test_offre_neutre_acceptee(self):
        assert is_offre_exclue(_offre(titre="Caissier temps partiel", description="Week-end et vacances")) is False

    def test_temps_partiel_accepte(self):
        assert is_offre_exclue(_offre(description="Poste à temps partiel, 15h/semaine")) is False


# ── Tests : normalise() France Travail — champ experienceExige ────────────────

class TestFranceTravailExperience:

    def test_experience_E_exclu(self):
        """experienceExige='E' sans libellé compatible → exclu."""
        raw = _raw_ft(experienceExige="E", experienceLibelle="5 ans d'expérience")
        assert ft_normalise(raw, "Montpellier") is None

    def test_experience_E_sans_libelle_exclu(self):
        """experienceExige='E' sans libellé du tout → exclu."""
        raw = _raw_ft(experienceExige="E")
        assert ft_normalise(raw, "Montpellier") is None

    def test_experience_E_libelle_debutant_accepte(self):
        """experienceExige='E' mais libellé dit 'débutant' → accepté."""
        raw = _raw_ft(experienceExige="E", experienceLibelle="Débutant accepté")
        result = ft_normalise(raw, "Montpellier")
        assert result is not None

    def test_experience_E_libelle_moins_un_an_accepte(self):
        """experienceExige='E' mais libellé dit 'moins d'un an' → accepté."""
        raw = _raw_ft(experienceExige="E", experienceLibelle="Moins d'un an")
        result = ft_normalise(raw, "Montpellier")
        assert result is not None

    def test_experience_D_accepte(self):
        """experienceExige='D' (débutant accepté) → toujours conservé."""
        raw = _raw_ft(experienceExige="D", experienceLibelle="Débutant accepté")
        result = ft_normalise(raw, "Montpellier")
        assert result is not None
        assert result["experience_exige"] == "D"

    def test_experience_S_accepte_avec_champ(self):
        """experienceExige='S' (souhaitée) → conservé, champ transmis pour pénalité."""
        raw = _raw_ft(experienceExige="S", experienceLibelle="Expérience souhaitée")
        result = ft_normalise(raw, "Montpellier")
        assert result is not None
        assert result["experience_exige"] == "S"

    def test_experience_vide_accepte(self):
        """Pas de champ experienceExige → conservé (bénéfice du doute)."""
        raw = _raw_ft()
        result = ft_normalise(raw, "Montpellier")
        assert result is not None
        assert result["experience_exige"] == ""


# ── Tests : score_pertinence — pénalité experienceExige='S' ──────────────────

class TestScorePertinence:

    def test_penalite_souhaitee(self):
        """Une offre avec experienceExige='S' a un score inférieur à la même sans signal."""
        base = _offre(titre="Serveur temps partiel", description="Poste saisonnier")
        offre_s = {**base, "experience_exige": "S"}
        offre_d = {**base, "experience_exige": "D"}
        assert score_pertinence(offre_s) < score_pertinence(offre_d)

    def test_boost_debutant_accepte(self):
        """Mention 'débutant accepté' augmente le score."""
        offre_boost = _offre(description="Débutant accepté, formation assurée")
        offre_neutre = _offre(description="Poste disponible immédiatement")
        assert score_pertinence(offre_boost) > score_pertinence(offre_neutre)


# ── Tests : validation URL ────────────────────────────────────────────────────

class TestUrlValidation:

    def test_url_https_conservee(self):
        raw = _raw_ft()
        result = ft_normalise(raw, "Montpellier")
        assert result["url"].startswith("https://")

    def test_url_javascript_rejetee(self):
        raw = _raw_ft(origineOffre={"urlOrigine": "javascript:alert(1)"})
        result = ft_normalise(raw, "Montpellier")
        assert result is not None
        assert result["url"] == ""

    def test_url_vide_rejetee(self):
        raw = _raw_ft(origineOffre={"urlOrigine": ""})
        result = ft_normalise(raw, "Montpellier")
        assert result is not None
        # Fallback vers l'URL candidat.francetravail.fr
        assert result["url"].startswith("https://candidat.francetravail.fr")


# ── Tests : autoescape Jinja2 — protection XSS ───────────────────────────────

class TestAutoescapeXSS:
    """
    Vérifie que le template index.html.j2 échappe correctement les données
    tiers (titres, descriptions d'offres) — protection contre les injections XSS.

    Note : autoescape=True (et non select_autoescape(["html"])) est requis car
    le template s'appelle "index.html.j2" (extension .j2) — select_autoescape
    se base sur l'extension et aurait désactivé silencieusement l'échappement.
    """

    def _render_with_payload(self, titre: str) -> str:
        from pathlib import Path
        from jinja2 import Environment, FileSystemLoader
        tmpl_dir = Path(__file__).parent.parent / "templates"
        env = Environment(loader=FileSystemLoader(str(tmpl_dir)), autoescape=True)
        template = env.get_template("index.html.j2")
        offre = {
            "titre": titre,
            "entreprise": "Test",
            "lieu": "Montpellier (34)",
            "date_publication": "2026-09-15",
            "type_contrat": "CDD",
            "type_contrat_label": "CDD",
            "duree_hebdo": "Temps partiel",
            "secteur": "",
            "description": "Description test.",
            "url": "https://example.com/offre/1",
            "source": "adzuna",
            "niveau_formation": "Non précisé",
            "experience_exige": "",
        }
        return template.render(offres=[offre], last_update="15/09/2026 à 08h00", total=1, annee=2026)

    def test_script_tag_echappe(self):
        """Un <script> dans le titre ne doit pas apparaître en clair dans le HTML."""
        html = self._render_with_payload('<script>alert(1)</script>')
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_attribut_data_titre_echappe(self):
        """Un guillemet cassant data-titre ne doit pas apparaître en clair."""
        html = self._render_with_payload('" onmouseover="alert(2)')
        assert 'onmouseover="alert' not in html
