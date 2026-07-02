"""Interface web minimale (Lot 12, REQ-007 côté UI).

Une page unique servie par le même FastAPI : coller un texte, choisir le
mode, voir le résumé des détections, télécharger, ré-identifier.

Séparation démo / sérieux (REQ-007, 02-AI-SPEC §5) :
- en mode sérieux, la réponse expose types, positions, scores et comptes,
  JAMAIS les valeurs détectées ni le vault ;
- le mode démo (bandeau distinct, données synthétiques attendues) montre
  les correspondances, mais refuse de s'activer si le mode sérieux a déjà
  des dossiers actifs dans l'instance, et un dossier utilisé en démo ne
  peut plus servir en mode sérieux.
"""

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .journal import Journal
from .juge import JugeLLM, executer_passe
from .pseudonymiseur import MOTIF_PLACEHOLDER, Pseudonymiseur


class RequetePseudonymisationUI(BaseModel):
    texte: str
    dossier_id: str
    mode: Literal["serieux", "demo"] = "serieux"


class RequeteReidentificationUI(BaseModel):
    texte: str
    dossier_id: str


def creer_routeur_ui(
    pseudonymiseur: Pseudonymiseur,
    journal: Journal,
    juge: JugeLLM | None = None,
) -> APIRouter:
    routeur = APIRouter()
    vault = pseudonymiseur.vault

    @routeur.get("/", response_class=HTMLResponse)
    def accueil() -> str:
        return PAGE_HTML

    @routeur.post("/ui/pseudonymiser")
    def ui_pseudonymiser(requete: RequetePseudonymisationUI) -> dict[str, Any]:
        if requete.mode == "demo":
            if vault.un_dossier_serieux_existe():
                raise HTTPException(
                    status_code=409,
                    detail="Le mode démonstration refuse de s'activer : le mode "
                    "sérieux a déjà des dossiers actifs dans cette instance "
                    "(séparation REQ-007). Utiliser une instance dédiée à la démo.",
                )
            vault.marquer_dossier(requete.dossier_id, "demo")
        else:
            if vault.mode_dossier(requete.dossier_id) == "demo":
                raise HTTPException(
                    status_code=409,
                    detail="Ce dossier a été utilisé en mode démonstration : il ne "
                    "peut plus servir en mode sérieux (séparation REQ-007).",
                )
            vault.marquer_dossier(requete.dossier_id, "serieux")

        requete_id = str(uuid.uuid4())
        resultat = pseudonymiseur.pseudonymiser(requete.texte, dossier_id=requete.dossier_id)
        # Passe juge (C3, REQ-014) sur le texte déjà pseudonymisé, renvoyée
        # en positions dans ce même texte (Q3 : le client extrait lui-même,
        # aucun segment en clair en mode sérieux ; le mode démo, valeurs
        # assumées visibles, reçoit segment et justification). Les candidats
        # partent en revue, jamais en remplacement.
        bloc_juge = executer_passe(
            juge,
            resultat.texte,
            texte_reference=resultat.texte,
            journal=journal,
            requete_id=requete_id,
            dossier_id=requete.dossier_id,
            avec_details=requete.mode == "demo",
        )
        # Journal en métadonnées seules (REQ-003), corrélé à l'éventuel
        # échec du juge par le même requete_id.
        journal.enregistrer(
            requete_id=requete_id,
            dossier_id=requete.dossier_id,
            backend="ui",
            modele="",
            statut="pseudonymisation_ui",
            entites_par_type=resultat.comptes_par_type,
            taille_approx=len(requete.texte),
            juge_statut=(
                None
                if juge is None
                else ("erreur" if "erreur_type" in bloc_juge else "ok")
            ),
            candidats_juge=(
                len(bloc_juge["candidats"])
                if juge is not None and "erreur_type" not in bloc_juge
                else None
            ),
        )
        detections: list[dict[str, Any]] = []
        for remplacement in resultat.remplacements:
            entite = remplacement.entite
            detection: dict[str, Any] = {
                "type": entite.type,
                "debut": entite.debut,
                "fin": entite.fin,
                "score": entite.score,
            }
            if requete.mode == "demo":
                detection["valeur"] = entite.valeur
                detection["placeholder"] = remplacement.placeholder
            detections.append(detection)
        return {
            "mode": requete.mode,
            "texte": resultat.texte,
            "comptes_par_type": resultat.comptes_par_type,
            "detections": detections,
            "ambiguites_coreference": resultat.ambiguites,
            "juge": bloc_juge,
        }

    @routeur.post("/ui/reidentifier")
    def ui_reidentifier(requete: RequeteReidentificationUI) -> dict[str, str]:
        # La ré-identification touche le vault : chaque appel est journalisé
        # (métadonnées seules, REQ-003). Le sas v1 n'a pas d'authentification :
        # son périmètre est la zone de confiance (voir QUESTIONS.md, Q2).
        journal.enregistrer(
            requete_id=str(uuid.uuid4()),
            dossier_id=requete.dossier_id,
            backend="ui",
            modele="",
            statut="reidentification_ui",
            entites_par_type={
                "placeholders_dans_le_texte": len(MOTIF_PLACEHOLDER.findall(requete.texte))
            },
            taille_approx=len(requete.texte),
        )
        return {
            "texte": pseudonymiseur.reidentifier(
                requete.texte, dossier_id=requete.dossier_id
            )
        }

    return routeur


PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sas Confiance IA : sas de pseudonymisation avant IA</title>
<style>
  /* Palette Comptoir des Signaux (https://www.comptoirdessignaux.com) :
     bleu à-plat principal, jaune or de mise en valeur, bleu du texte. */
  :root { --encre: #182C49; --fond: #f5f4f0; --accent: #1F519B;
          --or: #FDC949; --demo: #a4520a; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Georgia, "Times New Roman", serif;
         background: var(--fond); color: var(--encre); }
  header { padding: 1.2rem 2rem; border-bottom: 3px solid var(--accent); }
  header h1 { margin: 0; font-size: 1.4rem; }
  header p { margin: .2rem 0 0; color: #555; font-size: .95rem; }
  main { max-width: 60rem; margin: 0 auto; padding: 1.5rem 2rem; }
  label { display: block; font-weight: bold; margin: .8rem 0 .3rem; }
  textarea { width: 100%; min-height: 10rem; padding: .7rem;
             font: .95rem/1.4 "DejaVu Sans Mono", monospace;
             border: 1px solid #b9b4a8; border-radius: 4px; background: #fff; }
  input, select { padding: .45rem .6rem; border: 1px solid #b9b4a8;
                  border-radius: 4px; font-size: .95rem; background: #fff; }
  .ligne { display: flex; gap: 1rem; flex-wrap: wrap; align-items: end; }
  button { padding: .55rem 1.1rem; border: none; border-radius: 4px;
           background: var(--accent); color: #fff; font-size: .95rem;
           cursor: pointer; }
  button.secondaire { background: var(--encre); }
  button:disabled { opacity: .5; cursor: default; }
  #bandeau-demo { display: none; margin: 1rem 0 0; padding: .6rem 1rem;
                  background: var(--demo); color: #fff; border-radius: 4px;
                  font-weight: bold; }
  .demo-actif #bandeau-demo { display: block; }
  #erreur { display: none; margin-top: 1rem; padding: .6rem 1rem;
            background: #8c1c13; color: #fff; border-radius: 4px; }
  section.resultat { display: none; margin-top: 1.5rem; }
  table { border-collapse: collapse; margin-top: .5rem; }
  th, td { border: 1px solid #c9c4b8; padding: .35rem .7rem; text-align: left;
           font-size: .9rem; }
  th { background: var(--or); }
  footer { padding: 1rem 2rem 2rem; color: #666; font-size: .85rem;
           max-width: 60rem; margin: 0 auto; }
</style>
</head>
<body>
<header>
  <h1>Sas Confiance IA</h1>
  <p>Sas de pseudonymisation avant IA : les valeurs sensibles restent en zone
     de confiance. Aucun détecteur n'atteint 100 % de rappel : relisez avant
     d'envoyer à un modèle.</p>
</header>
<main>
  <div id="bandeau-demo">MODE DÉMONSTRATION : valeurs visibles, à réserver aux
    données synthétiques. Ne jamais y coller de vraies données.</div>

  <label for="texte">1. Texte à pseudonymiser</label>
  <textarea id="texte"
    placeholder="Collez ici le texte contenant des données personnelles."></textarea>

  <div class="ligne">
    <div>
      <label for="dossier">Dossier</label>
      <input id="dossier" value="dossier-001">
    </div>
    <div>
      <label for="mode">Mode</label>
      <select id="mode">
        <option value="serieux" selected>Sérieux (aucune valeur affichée)</option>
        <option value="demo">Démonstration (valeurs visibles)</option>
      </select>
    </div>
    <button id="pseudonymiser">Pseudonymiser</button>
    <button id="reidentifier" class="secondaire" disabled>Ré-identifier une réponse</button>
    <button id="exemple" class="secondaire">Charger un exemple (mode démo)</button>
  </div>

  <div id="erreur"></div>

  <section class="resultat" id="resultat">
    <label for="sortie">2. Texte pseudonymisé (à copier vers votre IA)</label>
    <textarea id="sortie" readonly></textarea>
    <div class="ligne">
      <button id="copier" class="secondaire">Copier</button>
      <button id="telecharger" class="secondaire">Télécharger</button>
    </div>
    <div id="synthese"></div>
  </section>

  <section class="resultat" id="zone-reidentification">
    <label for="reponse-ia">3. Réponse de l'IA à ré-identifier</label>
    <textarea id="reponse-ia"
      placeholder="Collez ici la réponse contenant des placeholders."></textarea>
    <label for="texte-final">Texte ré-identifié (zone de confiance)</label>
    <textarea id="texte-final" readonly></textarea>
  </section>
</main>
<footer>
  Le vault de correspondance ne quitte jamais cette instance. La
  pseudonymisation assiste le responsable de traitement : elle ne remplace ni
  DPO, ni AIPD, ni registre. Un commun numérique porté par
  <a href="https://www.comptoirdessignaux.com">Comptoir des Signaux</a>.
</footer>
<script>
const el = (id) => document.getElementById(id);

// Tout contenu inséré via innerHTML passe par l'échappement (parade XSS).
function echapper(texte) {
  const div = document.createElement("div");
  div.textContent = String(texte);
  return div.innerHTML;
}

// Dossier non devinable par défaut : un identifiant prévisible facilite la
// ré-identification par un tiers de la zone de confiance.
el("dossier").value = "dossier-" + crypto.randomUUID().slice(0, 13);

el("mode").addEventListener("change", () => {
  document.body.classList.toggle("demo-actif", el("mode").value === "demo");
});

// Exemple d'atelier : données entièrement synthétiques à clés valides
// (NIR, SIRET Luhn, IBAN). Il bascule TOUJOURS en mode démonstration.
const EXEMPLE_DEMO = `Madame Camille Durand, née le 12 mai 1985 à Poitiers, \
numéro de sécurité sociale 2 85 05 78 006 084 41, sollicite une aide de la \
commune. Contact : camille.durand@exemple.fr ou 06 12 34 56 78. Son \
employeur, la boulangerie Aux Blés d'Or (SIRET 845 124 789 00007), verse \
son salaire sur le compte FR76 3000 6000 0112 3456 7890 189.`;

el("exemple").addEventListener("click", () => {
  el("texte").value = EXEMPLE_DEMO;
  el("mode").value = "demo";
  el("mode").dispatchEvent(new Event("change"));
});

function montrerErreur(message) {
  el("erreur").textContent = message;
  el("erreur").style.display = message ? "block" : "none";
}

async function appeler(chemin, corps) {
  const reponse = await fetch(chemin, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  const donnees = await reponse.json();
  if (!reponse.ok) throw new Error(donnees.detail || "Erreur inattendue.");
  return donnees;
}

el("pseudonymiser").addEventListener("click", async () => {
  montrerErreur("");
  try {
    const donnees = await appeler("/ui/pseudonymiser", {
      texte: el("texte").value,
      dossier_id: el("dossier").value,
      mode: el("mode").value,
    });
    el("sortie").value = donnees.texte;
    el("resultat").style.display = "block";
    el("zone-reidentification").style.display = "block";
    el("reidentifier").disabled = false;
    afficherSynthese(donnees);
  } catch (erreur) { montrerErreur(erreur.message); }
});

function afficherSynthese(donnees) {
  const lignes = Object.entries(donnees.comptes_par_type)
    .map(([type, compte]) => `<tr><td>${echapper(type)}</td><td>${echapper(compte)}</td></tr>`)
    .join("");
  let html = `<table><tr><th>Type détecté</th><th>Compte</th></tr>${lignes}</table>`;
  if (donnees.ambiguites_coreference.length) {
    html += `<p>Rattachements à vérifier (homonymes possibles) :
      ${donnees.ambiguites_coreference.map(echapper).join(", ")}</p>`;
  }
  if (donnees.juge && donnees.juge.actif && donnees.juge.candidats.length) {
    // Le serveur ne renvoie que des positions (Q3) : le segment s'extrait
    // ici, depuis le texte pseudonymisé que la page possède déjà.
    const candidats = donnees.juge.candidats
      .map((c) => {
        const segment = c.segment !== undefined
          ? c.segment : donnees.texte.slice(c.debut, c.fin);
        const justification = c.justification !== undefined
          ? echapper(c.justification) : "(mode démo pour la justification)";
        return `<tr><td>${echapper(segment)}</td><td>${echapper(c.type_candidat)}</td>
          <td>${justification}</td><td>${c.score.toFixed(2)}</td></tr>`;
      })
      .join("");
    html += `<h3>Identifiants indirects à revoir (juge LLM local)</h3>
      <p>Signalés pour relecture humaine : le sas ne les a PAS remplacés.</p>
      <table><tr><th>Segment</th><th>Type</th><th>Justification</th><th>Score</th></tr>
      ${candidats}</table>`;
  }
  if (donnees.juge && donnees.juge.candidats_non_localises) {
    html += `<p>${echapper(donnees.juge.candidats_non_localises)} signalement(s) du juge
      non localisables dans le texte : écartés (parade F7).</p>`;
  }
  if (donnees.juge && donnees.juge.erreur_type) {
    html += `<p>Le juge LLM a échoué (${echapper(donnees.juge.erreur_type)}) :
      couverture C1+C2 seule pour cet appel.</p>`;
  }
  if (donnees.mode === "demo") {
    const details = donnees.detections
      .map((d) => `<tr><td>${echapper(d.placeholder)}</td><td>${echapper(d.type)}</td>
        <td>${echapper(d.valeur)}</td><td>${d.score.toFixed(2)}</td></tr>`)
      .join("");
    html += `<table><tr><th>Placeholder</th><th>Type</th><th>Valeur (démo)</th>
      <th>Score</th></tr>${details}</table>`;
  }
  el("synthese").innerHTML = html;
}

el("reidentifier").addEventListener("click", async () => {
  montrerErreur("");
  try {
    const donnees = await appeler("/ui/reidentifier", {
      texte: el("reponse-ia").value,
      dossier_id: el("dossier").value,
    });
    el("texte-final").value = donnees.texte;
  } catch (erreur) { montrerErreur(erreur.message); }
});

el("copier").addEventListener("click", () =>
  navigator.clipboard.writeText(el("sortie").value));

el("telecharger").addEventListener("click", () => {
  const blob = new Blob([el("sortie").value], { type: "text/plain" });
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(blob);
  lien.download = `pseudonymise-${el("dossier").value}.txt`;
  lien.click();
  URL.revokeObjectURL(lien.href);
});
</script>
</body>
</html>
"""
