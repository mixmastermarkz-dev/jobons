/**
 * JobOns — Filtrage côté client
 * Lit les data-* des cartes pour filtrer sans rechargement de page.
 */

(function () {
  "use strict";

  const grid      = document.getElementById("jobs-grid");
  const noResults = document.getElementById("no-results");
  const countEl   = document.getElementById("count-display");
  const searchEl  = document.getElementById("search-input");
  const clearBtn  = document.getElementById("search-clear");
  const contratEl = document.getElementById("filter-contrat");
  const secteurEl = document.getElementById("filter-secteur");
  const villeEl   = document.getElementById("filter-ville");
  const sourceEl  = document.getElementById("filter-source");
  const resetBtn    = document.getElementById("filter-reset");
  const refreshBtn  = document.getElementById("filter-refresh");

  const cards = Array.from(grid ? grid.querySelectorAll(".job-card") : []);

  // ── Remplir dynamiquement le filtre Secteur ──────────────────
  // Limite aux secteurs présents dans au moins 2 offres, triés par fréquence
  // décroissante puis par ordre alphabétique, maximum 20 options.
  const secteurCount = {};
  cards.forEach(c => {
    const s = c.dataset.secteur;
    if (s) secteurCount[s] = (secteurCount[s] || 0) + 1;
  });
  const secteurs = Object.entries(secteurCount)
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "fr"))
    .slice(0, 20)
    .map(([s]) => s);

  secteurs.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    secteurEl.appendChild(opt);
  });

  // ── Filtrage principal ────────────────────────────────────────
  function normalise(str) {
    return (str || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function applyFilters() {
    const query   = normalise(searchEl.value);
    const contrat = contratEl.value;
    const secteur = secteurEl.value;
    const ville   = normalise(villeEl.value);
    const source  = sourceEl.value;

    let visible = 0;

    cards.forEach(card => {
      const matchSearch =
        !query ||
        normalise(card.dataset.titre).includes(query) ||
        normalise(card.dataset.entreprise).includes(query) ||
        normalise(card.dataset.description).includes(query);

      const matchContrat =
        !contrat || card.dataset.contrat === contrat;

      const matchSecteur =
        !secteur || card.dataset.secteur === secteur;

      const matchVille =
        !ville || normalise(card.dataset.lieu).includes(ville);

      const matchSource =
        !source || card.dataset.source === source;

      const show = matchSearch && matchContrat && matchSecteur && matchVille && matchSource;
      card.style.display = show ? "" : "none";
      if (show) visible++;
    });

    // Mettre à jour le compteur
    if (countEl) countEl.textContent = visible;

    // Afficher/masquer l'état vide
    if (noResults) noResults.hidden = visible > 0;

    // Bouton clear dans la barre de recherche
    if (clearBtn) clearBtn.hidden = !searchEl.value;
  }

  // ── Événements ───────────────────────────────────────────────
  searchEl?.addEventListener("input", applyFilters);
  contratEl?.addEventListener("change", applyFilters);
  secteurEl?.addEventListener("change", applyFilters);
  villeEl?.addEventListener("change", applyFilters);
  sourceEl?.addEventListener("change", applyFilters);

  clearBtn?.addEventListener("click", () => {
    searchEl.value = "";
    clearBtn.hidden = true;
    applyFilters();
    searchEl.focus();
  });

  resetBtn?.addEventListener("click", () => {
    searchEl.value = "";
    contratEl.value = "";
    secteurEl.value = "";
    villeEl.value = "";
    sourceEl.value = "";
    clearBtn.hidden = true;
    applyFilters();
  });

  refreshBtn?.addEventListener("click", () => {
    const icon = refreshBtn.querySelector(".icon-sm");
    refreshBtn.classList.add("spinning");
    refreshBtn.disabled = true;
    fetch("data/offres.json?t=" + Date.now())
      .then(r => r.json())
      .then(() => location.reload())
      .catch(() => location.reload())
      .finally(() => {
        refreshBtn.classList.remove("spinning");
        refreshBtn.disabled = false;
      });
  });

  // Init
  applyFilters();
})();
