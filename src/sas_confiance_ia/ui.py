"""Interface web minimale (Lot 12, REQ-007 côté UI).

Une page unique servie par le même FastAPI : coller un texte, choisir le
mode, voir le résumé des détections, télécharger, ré-identifier. L'atelier
se lit en deux colonnes (aller : original puis pseudonymisé ; retour :
réponse de l'IA puis ré-identifié), à la manière du viewport d'amo-presidio.

Séparation démo / sérieux (REQ-007, 02-AI-SPEC §5) :
- en mode sérieux, la réponse expose types, positions, scores et comptes,
  JAMAIS les valeurs détectées ni le vault ;
- le mode démo (bandeau distinct, données synthétiques attendues) montre
  les correspondances, mais refuse de s'activer si le mode sérieux a déjà
  des dossiers actifs dans l'instance, et un dossier utilisé en démo ne
  peut plus servir en mode sérieux.
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .fichiers import (
    ErreurFichier,
    FormatNonSupporte,
    extraire_texte,
    pseudonymiser_docx,
)
from .journal import Journal
from .juge import JugeLLM, executer_passe
from .politique import valider_actions
from .pseudonymiseur import MOTIF_PLACEHOLDER, Pseudonymiseur


class RequetePseudonymisationUI(BaseModel):
    texte: str
    dossier_id: str
    mode: Literal["serieux", "demo"] = "serieux"
    # Politique de remplacement du dossier (Lot 14, cadrage §9.5) : définie à
    # la première requête qui la porte, elle vit ensuite dans le vault.
    politiques: dict[str, str] | None = None
    # Surrogates réalistes (REQ-012) : option par dossier, placeholder sinon.
    surrogates: bool | None = None


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

    @routeur.get("/fichiers", response_class=HTMLResponse)
    def page_fichiers() -> str:
        return PAGE_FICHIERS_HTML

    def _verifier_mode(dossier_id: str, mode: str) -> None:
        """Séparation démo / sérieux (REQ-007), commune à tous les chemins UI."""
        if mode == "demo":
            if vault.un_dossier_serieux_existe():
                raise HTTPException(
                    status_code=409,
                    detail="Le mode démonstration refuse de s'activer : le mode "
                    "sérieux a déjà des dossiers actifs dans cette instance "
                    "(séparation REQ-007). Utiliser une instance dédiée à la démo.",
                )
            vault.marquer_dossier(dossier_id, "demo")
        else:
            if vault.mode_dossier(dossier_id) == "demo":
                raise HTTPException(
                    status_code=409,
                    detail="Ce dossier a été utilisé en mode démonstration : il ne "
                    "peut plus servir en mode sérieux (séparation REQ-007).",
                )
            vault.marquer_dossier(dossier_id, "serieux")

    def _pseudonymisation_ui(
        texte: str, dossier_id: str, mode: str, statut: str
    ) -> dict[str, Any]:
        """Pseudonymisation + passe juge + journal + détections (Q3).

        En mode sérieux, la réponse expose types, positions, scores et
        comptes, jamais les valeurs détectées ni le vault.
        """
        requete_id = str(uuid.uuid4())
        resultat = pseudonymiseur.pseudonymiser(texte, dossier_id=dossier_id)
        # Passe juge (C3, REQ-014) sur le texte déjà pseudonymisé, renvoyée
        # en positions dans ce même texte (Q3) ; segment et justification en
        # mode démonstration seulement. Candidats en revue, jamais remplacés.
        bloc_juge = executer_passe(
            juge,
            resultat.texte,
            texte_reference=resultat.texte,
            journal=journal,
            requete_id=requete_id,
            dossier_id=dossier_id,
            avec_details=mode == "demo",
        )
        # Journal en métadonnées seules (REQ-003), corrélé à l'éventuel
        # échec du juge par le même requete_id.
        journal.enregistrer(
            requete_id=requete_id,
            dossier_id=dossier_id,
            backend="ui",
            modele="",
            statut=statut,
            entites_par_type=resultat.comptes_par_type,
            taille_approx=len(texte),
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
            if mode == "demo":
                detection["valeur"] = entite.valeur
                detection["placeholder"] = remplacement.placeholder
                if remplacement.surrogate is not None:
                    detection["surrogate"] = remplacement.surrogate
            detections.append(detection)
        return {
            "mode": mode,
            "texte": resultat.texte,
            "comptes_par_type": resultat.comptes_par_type,
            "detections": detections,
            "ambiguites_coreference": resultat.ambiguites,
            # Placeholders masqués par une politique « revue » (Lot 14) : à
            # faire relire par un humain, jamais de valeur.
            "entites_en_revue": resultat.en_revue,
            "juge": bloc_juge,
        }

    @routeur.post("/ui/pseudonymiser")
    def ui_pseudonymiser(requete: RequetePseudonymisationUI) -> dict[str, Any]:
        _verifier_mode(requete.dossier_id, requete.mode)

        if requete.politiques is not None or requete.surrogates is not None:
            if requete.politiques is not None:
                try:
                    valider_actions(requete.politiques)
                except ValueError as erreur:
                    # Une politique fautive ne dégrade jamais la couverture
                    # en silence : requête refusée, rien n'est stocké.
                    raise HTTPException(status_code=422, detail=str(erreur)) from erreur
            # Chaque champ absent garde sa valeur déjà stockée : la requête
            # ne redéfinit que ce qu'elle porte.
            existante = vault.politique_dossier(requete.dossier_id) or {}
            vault.definir_politique(
                requete.dossier_id,
                {
                    "actions": (
                        requete.politiques
                        if requete.politiques is not None
                        else existante.get("actions", {})
                    ),
                    "surrogates": (
                        requete.surrogates
                        if requete.surrogates is not None
                        else existante.get("surrogates", False)
                    ),
                },
            )

        return _pseudonymisation_ui(
            requete.texte, requete.dossier_id, requete.mode, "pseudonymisation_ui"
        )

    @routeur.post("/ui/fichier")
    async def ui_fichier(
        fichier: Annotated[UploadFile, File()],
        dossier_id: Annotated[str, Form()],
        mode: Annotated[Literal["serieux", "demo"], Form()] = "serieux",
    ) -> dict[str, Any]:
        octets = await fichier.read()
        nom = fichier.filename or ""
        try:
            texte = extraire_texte(nom, octets)
        except FormatNonSupporte as erreur:
            raise HTTPException(status_code=415, detail=str(erreur)) from erreur
        except ErreurFichier as erreur:
            # PDF scanné ou fichier corrompu : refus explicite, le dossier
            # n'est pas marqué pour un dépôt qui n'a rien produit.
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        _verifier_mode(dossier_id, mode)
        reponse = _pseudonymisation_ui(texte, dossier_id, mode, "pseudonymisation_fichier_ui")
        # Q3 : le texte extrait revient au navigateur, c'est le document de
        # l'utilisateur ; le nom du fichier revient aussi mais n'entre
        # JAMAIS au journal (REQ-003 : il peut contenir un nom de personne).
        return {"nom": nom, "texte_origine": texte, **reponse}

    @routeur.post("/ui/fichier/export-docx")
    async def ui_fichier_export_docx(
        fichier: Annotated[UploadFile, File()],
        dossier_id: Annotated[str, Form()],
        mode: Annotated[Literal["serieux", "demo"], Form()] = "serieux",
    ) -> Response:
        nom = fichier.filename or ""
        if not nom.lower().endswith(".docx"):
            raise HTTPException(
                status_code=415,
                detail="l'export reconstruit ne concerne que les fichiers .docx ; "
                "pour un texte brut, le téléchargement se fait côté navigateur",
            )
        octets = await fichier.read()
        _verifier_mode(dossier_id, mode)
        try:
            exporte, comptes = pseudonymiser_docx(
                octets,
                lambda texte: pseudonymiseur.pseudonymiser(texte, dossier_id=dossier_id),
            )
        except ErreurFichier as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        journal.enregistrer(
            requete_id=str(uuid.uuid4()),
            dossier_id=dossier_id,
            backend="ui",
            modele="",
            statut="export_docx_ui",
            entites_par_type=comptes,
            taille_approx=len(octets),
        )
        return Response(
            content=exporte,
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            # Nom neutre : le nom d'origine peut porter un nom de personne,
            # la page renomme le téléchargement côté client si besoin.
            headers={"Content-Disposition": 'attachment; filename="pseudonymise.docx"'},
        )

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


STYLE_COMMUN = """<style>
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
  header nav { margin-top: .4rem; font-size: .95rem; }
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
</style>"""

PAGE_HTML = (
    """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sas Confiance IA : sas de pseudonymisation avant IA</title>
"""
    + STYLE_COMMUN
    + """
<style>
  /* Atelier en deux colonnes (à la manière du viewport d'amo-presidio) :
     l'aller à gauche (1. original, 2. pseudonymisé), le retour à droite
     (3. réponse de l'IA, 4. ré-identifié). Les quatre panneaux sont
     visibles d'emblée : le parcours se comprend d'un coup d'œil. */
  main, footer { max-width: 100rem; }
  .atelier { display: grid; grid-template-columns: 1fr 1fr; gap: 0 2.5rem;
             margin-top: .5rem; align-items: start; }
  .colonne { min-width: 0; }
  .colonne h2 { margin: 1rem 0 0; font-size: 1.05rem; color: var(--accent);
                border-bottom: 2px solid var(--or); padding-bottom: .25rem; }
  @media (max-width: 70rem) { .atelier { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>Sas Confiance IA</h1>
  <p>Sas de pseudonymisation avant IA : les valeurs sensibles restent en zone
     de confiance. Aucun détecteur n'atteint 100 % de rappel : relisez avant
     d'envoyer à un modèle.</p>
  <nav><a href="/fichiers">Fichiers : déposer un document (.txt, .md, .docx, .pdf)</a></nav>
</header>
<main>
  <div id="bandeau-demo">MODE DÉMONSTRATION : valeurs visibles, à réserver aux
    données synthétiques. Ne jamais y coller de vraies données.</div>

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
    <div>
      <label for="dates">Dates procédurales</label>
      <select id="dates">
        <option value="conserver" selected>Conserver (défaut)</option>
        <option value="revue">Masquer et faire relire</option>
        <option value="pseudonymiser">Pseudonymiser</option>
      </select>
    </div>
    <div>
      <label for="surrogates">Noms factices</label>
      <select id="surrogates">
        <option value="non" selected>Placeholders [PERSONNE_001] (défaut)</option>
        <option value="oui">Surrogates réalistes (intégrité réduite)</option>
      </select>
    </div>
    <button id="exemple" class="secondaire">Charger un exemple (mode démo)</button>
  </div>

  <div id="erreur"></div>

  <div class="atelier">
    <div class="colonne">
      <h2>Aller : protéger avant l'envoi à l'IA</h2>
      <section>
        <label for="texte">1. Texte à pseudonymiser</label>
        <textarea id="texte"
          placeholder="Collez ici le texte contenant des données personnelles."></textarea>
        <div class="ligne">
          <button id="pseudonymiser">Pseudonymiser</button>
        </div>
      </section>
      <section>
        <label for="sortie">2. Texte pseudonymisé (à copier vers votre IA)</label>
        <textarea id="sortie" readonly placeholder="Le texte protégé apparaîtra ici :
seuls des pseudonymes partent vers l'IA."></textarea>
        <div class="ligne">
          <button id="copier" class="secondaire">Copier</button>
          <button id="telecharger" class="secondaire">Télécharger</button>
        </div>
      </section>
    </div>
    <div class="colonne">
      <h2>Retour : ré-identifier en zone de confiance</h2>
      <section>
        <label for="reponse-ia">3. Réponse de l'IA à ré-identifier</label>
        <textarea id="reponse-ia"
          placeholder="Collez ici la réponse contenant des placeholders."></textarea>
        <div class="ligne">
          <button id="reidentifier" class="secondaire" disabled
            title="Pseudonymisez d'abord un texte dans ce dossier.">Ré-identifier</button>
        </div>
      </section>
      <section>
        <label for="texte-final">4. Texte ré-identifié (zone de confiance)</label>
        <textarea id="texte-final" readonly placeholder="La réponse redevient lisible ici,
sans quitter votre zone de confiance."></textarea>
      </section>
    </div>
  </div>

  <div id="synthese"></div>
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
      // Politique du dossier (Lot 14) : la date de naissance reste masquée
      // par défaut, les dates procédurales suivent ce choix (REQ-008) ; les
      // surrogates réalistes sont un choix par dossier (REQ-012, Q5).
      politiques: { DATE_PROCEDURALE: el("dates").value },
      surrogates: el("surrogates").value === "oui",
    });
    el("sortie").value = donnees.texte;
    el("reidentifier").disabled = false;
    el("reidentifier").title = "";
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
  if (donnees.entites_en_revue && donnees.entites_en_revue.length) {
    html += `<p>Masqués par prudence, à faire relire (politique « revue ») :
      ${donnees.entites_en_revue.map(echapper).join(", ")}</p>`;
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
)

PAGE_FICHIERS_HTML = (
    """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sas Confiance IA : fichiers</title>
"""
    + STYLE_COMMUN
    + """
<style>
  #zone-depot { margin-top: 1rem; padding: 2rem; border: 2px dashed var(--accent);
                border-radius: 6px; text-align: center; background: #fff;
                cursor: pointer; }
  #zone-depot.survol { background: #eef3fb; border-style: solid; }
  #nom-fichier { font-weight: bold; }
  .pastille { display: inline-block; margin: .2rem .3rem 0 0; padding: .2rem .6rem;
              background: var(--or); border-radius: 999px; font-size: .85rem; }
  .cote-a-cote { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
                 margin-top: .5rem; }
  .panneau { background: #fff; border: 1px solid #b9b4a8; border-radius: 4px;
             padding: .7rem; font: .9rem/1.5 "DejaVu Sans Mono", monospace;
             white-space: pre-wrap; overflow-x: auto; max-height: 28rem;
             overflow-y: auto; }
  .panneau mark { background: var(--or); border-radius: 2px; }
  @media (max-width: 50rem) { .cote-a-cote { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>Sas Confiance IA : fichiers</h1>
  <p>Déposer un document (.txt, .md, .csv, .docx, .pdf textuel) : le texte est
     extrait puis pseudonymisé. Les PDF scannés sont refusés (pas d'OCR).
     Aucun détecteur n'atteint 100 % de rappel : relisez avant d'envoyer.</p>
  <nav><a href="/">Texte : coller et pseudonymiser</a></nav>
</header>
<main>
  <div id="bandeau-demo">MODE DÉMONSTRATION : valeurs visibles, à réserver aux
    données synthétiques. Ne jamais y coller de vraies données.</div>

  <div id="zone-depot">Glisser-déposer un fichier ici, ou cliquer pour choisir.
    <div id="nom-fichier">Aucun fichier choisi.</div>
    <input type="file" id="selecteur" accept=".txt,.md,.csv,.docx,.pdf" hidden>
  </div>

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
    <button id="pseudonymiser" disabled>Pseudonymiser le fichier</button>
  </div>

  <div id="erreur"></div>

  <section class="resultat" id="resultat">
    <div id="pastilles"></div>
    <div class="cote-a-cote">
      <div>
        <label>Document d'origine (entités surlignées)</label>
        <div id="origine" class="panneau"></div>
      </div>
      <div>
        <label>Texte pseudonymisé (à copier vers votre IA)</label>
        <div id="pseudo" class="panneau"></div>
      </div>
    </div>
    <div class="ligne" style="margin-top: 1rem;">
      <button id="export-txt" class="secondaire">Télécharger le .txt pseudonymisé</button>
      <button id="export-docx" class="secondaire" disabled>Télécharger le .docx
        pseudonymisé</button>
    </div>
    <div id="synthese"></div>
  </section>
</main>
<footer>
  Le document déposé est traité dans cette instance et n'en sort que
  pseudonymisé. Le surlignage se calcule dans votre navigateur à partir des
  positions : en mode sérieux, le serveur ne renvoie jamais les valeurs
  détectées. Un commun numérique porté par
  <a href="https://www.comptoirdessignaux.com">Comptoir des Signaux</a>.
</footer>
<script>
const el = (id) => document.getElementById(id);
let fichierCourant = null;
let corpsCourant = null;

function echapper(texte) {
  const div = document.createElement("div");
  div.textContent = String(texte);
  return div.innerHTML;
}

el("dossier").value = "dossier-" + crypto.randomUUID().slice(0, 13);

el("mode").addEventListener("change", () => {
  document.body.classList.toggle("demo-actif", el("mode").value === "demo");
});

function montrerErreur(message) {
  el("erreur").textContent = message;
  el("erreur").style.display = message ? "block" : "none";
}

const zone = el("zone-depot");
zone.addEventListener("click", () => el("selecteur").click());
zone.addEventListener("dragover", (evenement) => {
  evenement.preventDefault();
  zone.classList.add("survol");
});
zone.addEventListener("dragleave", () => zone.classList.remove("survol"));
zone.addEventListener("drop", (evenement) => {
  evenement.preventDefault();
  zone.classList.remove("survol");
  if (evenement.dataTransfer.files.length) choisir(evenement.dataTransfer.files[0]);
});
el("selecteur").addEventListener("change", () => {
  if (el("selecteur").files.length) choisir(el("selecteur").files[0]);
});

function choisir(fichier) {
  fichierCourant = fichier;
  el("nom-fichier").textContent = fichier.name;
  el("pseudonymiser").disabled = false;
}

el("pseudonymiser").addEventListener("click", async () => {
  montrerErreur("");
  const donnees = new FormData();
  donnees.append("fichier", fichierCourant);
  donnees.append("dossier_id", el("dossier").value);
  donnees.append("mode", el("mode").value);
  try {
    const reponse = await fetch("/ui/fichier", { method: "POST", body: donnees });
    const corps = await reponse.json();
    if (!reponse.ok) throw new Error(corps.detail || "Erreur inattendue.");
    afficher(corps);
  } catch (erreur) { montrerErreur(erreur.message); }
});

// Surlignage côté client à partir des positions (arbitrage Q3) : le texte
// appartient à l'utilisateur, le serveur n'a renvoyé que des positions.
function surligner(texte, detections) {
  const triees = [...detections].sort((a, b) => a.debut - b.debut);
  let html = "";
  let curseur = 0;
  for (const detection of triees) {
    if (detection.debut < curseur) continue;
    html += echapper(texte.slice(curseur, detection.debut));
    html += `<mark title="${echapper(detection.type)}">`
      + echapper(texte.slice(detection.debut, detection.fin)) + "</mark>";
    curseur = detection.fin;
  }
  return html + echapper(texte.slice(curseur));
}

function afficher(corps) {
  corpsCourant = corps;
  el("resultat").style.display = "block";
  el("origine").innerHTML = surligner(corps.texte_origine, corps.detections);
  el("pseudo").textContent = corps.texte;
  el("pastilles").innerHTML = Object.entries(corps.comptes_par_type)
    .map(([type, compte]) =>
      `<span class="pastille">${echapper(type)} : ${echapper(compte)}</span>`)
    .join("");
  el("export-docx").disabled = !fichierCourant.name.toLowerCase().endsWith(".docx");
  let html = "";
  if (corps.entites_en_revue && corps.entites_en_revue.length) {
    html += `<p>Masqués par prudence, à faire relire (politique « revue ») :
      ${corps.entites_en_revue.map(echapper).join(", ")}</p>`;
  }
  if (corps.ambiguites_coreference && corps.ambiguites_coreference.length) {
    html += `<p>Rattachements à vérifier (homonymes possibles) :
      ${corps.ambiguites_coreference.map(echapper).join(", ")}</p>`;
  }
  el("synthese").innerHTML = html;
}

el("export-txt").addEventListener("click", () => {
  const blob = new Blob([corpsCourant.texte], { type: "text/plain" });
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(blob);
  lien.download = `pseudonymise-${fichierCourant.name.replace(/\\.[^.]+$/, "")}.txt`;
  lien.click();
  URL.revokeObjectURL(lien.href);
});

el("export-docx").addEventListener("click", async () => {
  montrerErreur("");
  const donnees = new FormData();
  donnees.append("fichier", fichierCourant);
  donnees.append("dossier_id", el("dossier").value);
  donnees.append("mode", el("mode").value);
  try {
    const reponse = await fetch("/ui/fichier/export-docx", { method: "POST", body: donnees });
    if (!reponse.ok) {
      const corps = await reponse.json();
      throw new Error(corps.detail || "Erreur inattendue.");
    }
    const blob = await reponse.blob();
    const lien = document.createElement("a");
    lien.href = URL.createObjectURL(blob);
    lien.download = `pseudonymise-${fichierCourant.name}`;
    lien.click();
    URL.revokeObjectURL(lien.href);
  } catch (erreur) { montrerErreur(erreur.message); }
});
</script>
</body>
</html>
"""
)
