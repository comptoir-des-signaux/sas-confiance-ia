# AGENTS.md : Sas Confiance IA

Sas de pseudonymisation avant IA pour les collectivites territoriales et la
fonction publique francaise. Porte par Comptoir des Signaux, licence EUPL-1.2.

Ce document s'adresse a tout agent de code travaillant sur ce projet. Il
complete le `CLAUDE.md` parent de l'atelier et prime sur les habitudes de
l'agent. Lire avant d'agir : `docs/specs/06-HANDOFF.md` (consignes strictes),
`docs/specs/03-SPEC.md` (exigences falsifiables), `docs/specs/05-PLAN.md`
(plan TDD par lots).

## Carte d'architecture (graphify)

Un graphe de connaissances du code est disponible dans `graphify-out/`. Il
cartographie 586 nuds, 1313 aretes et 25 communautes.

- **Point d'entree** : `graphify-out/wiki/index.md` (communautes triees par
  taille + 10 nuds centraux avec liens)
- **Rapport complet** : `graphify-out/GRAPH_REPORT.md` (god nodes, surprising
  connections, import cycles, knowledge gaps)
- **Graphe interactif** : `graphify-out/graph.html` (ouvrir dans un navigateur)
- **Interrogation** : `graphify query "<question>"` (traverse le graphe),
  `graphify path "A" "B"` (chemin court), `graphify explain "NodeName"`
- **Mise a jour** : `graphify . --update` (incremental, seulement les fichiers
  modifies)

**Avant de modifier un module**, consulter sa communaute dans le wiki pour
comprendre ses dependances. Les 5 nuds les plus connectes :
`VaultMemoire` (52), `detecter()` (48), `Pseudonymiseur` (48), `JugeLLM` (37),
`charger_configuration()` (29).

## Stack

Python 3.12+, gestion par `uv`, FastAPI, pytest, ruff. Presidio in-process
(ADR-009). Modeles epingles par version exacte. Docker Compose pour le
deploiement (sas + Ollama optionnel).

## Structure du code

```
src/sas_confiance_ia/
  api.py              Proxy OpenAI-compatible (/v1/chat/completions, /v1/models)
  pseudonymiseur.py   Orchestrateur central : detection -> vault -> envoi -> integrite -> re-identification
  detection.py        Pipeline C1 (regex) + C2 (NER) + C3 (juge), resolution des chevauchements (REQ-016)
  ner.py              Couche C2 : CamemBERT via Presidio (repli spaCy)
  juge.py             Couche C3 : LLM local via Ollama, sortie JSON stricte, candidats en revue
  coreference.py      Couche C4 : resolution par dossier, alias, formes canoniques
  politique.py        Politiques par type : pseudonymiser / masquer / conserver / revue (cadrage 9.5)
  surrogates.py       Noms factices Faker fr_FR genres, rendu par-dessus les placeholders (REQ-012)
  vault.py            Vault abstrait + VaultMemoire (correspondances en memoire)
  integrite.py        Controle des placeholders en sortie (alters, inventes, manquants)
  backends.py         BackendOpenAICompatible (reel) + BackendCapture (faux, pour les tests)
  configuration.py    Configuration par variables d'environnement
  validators.py       Validateurs francais purs : NIR (cle, Corse 2A/2B), Luhn (SIREN/SIRET), IBAN
  journal.py          Journal structure sans DCP (metadonnees techniques uniquement)
  ui.py               Interface web minimale (copier-coller, modes serieux/demo)
  evaluation.py       Evaluation du rappel NER sur corpus synthetique
  evaluation_juge.py  Evaluation du juge LLM sur les canaris
tests/                200+ tests, tous sur faux backend, aucun appel reseau
corpus/synthetique/   Corpus 100% synthetique avec oracle de non-fuite
docs/specs/           PRD, AI-SPEC, SPEC (REQ-001 a 016), ADR, PLAN, HANDOFF, QUESTIONS
```

## Interdictions absolues (violations = arret immediat)

1. **Aucun appel reseau externe** depuis les tests : pas d'API, pas de
   telemetrie, pas de telechargement au runtime. Un test l'interdit activement.
2. **Aucune donnee reelle** : tout exemple, fixture ou test utilise le corpus
   synthetique ou des valeurs inventees a cles valides.
3. **Le vault ne transite jamais** vers un LLM, un log, une reponse API en mode
   serieux, ou un message d'erreur.
4. **Ne jamais affaiblir un test d'invariant** (REQ-001 a 010) pour le faire
   passer. Si un test semble faux, s'arreter et le signaler.
5. **Pas de secret en dur**, pas de cle commitee, pas de `.env` versionne.
6. **Pas de tiret cadratin** dans les textes produits ; francais accentue
   partout (code, commentaires, commits, docs).

## Methode imposee

- **TDD strict** : suivre les lots du `05-PLAN.md` dans l'ordre. Pour chaque
  lot : tests en rouge d'abord, implementation minimale, vert, refactor,
  commit atomique.
- **Commits atomiques** en francais : un commit ne melange jamais deux lots.
- **Aucune fonctionnalite non demandee** : pas de streaming, pas d'OCR, pas
  d'authentification, pas de connecteur, meme « pour preparer la suite ».
- **Toute ambiguite de spec** : choisir l'interpretation la plus protectrice
  pour les donnees, la consigner dans `docs/specs/QUESTIONS.md` a faire
  arbitrer.

## Definition de « termine » pour un lot

1. Tests du lot verts, suite complete verte, ruff sans erreur.
2. Les tests de non-fuite (payload + logs) passent sur TOUTE la suite.
3. Aucun `TODO` silencieux : chaque report est trace dans `QUESTIONS.md`.
4. La documentation touchee par le lot est mise a jour dans le meme commit.

## Invariants de securite (REQ-001 a 010)

Ces exigences sont prouvees par des tests sur faux backend de capture. Les
affaiblir est une interdiction absolue (voir ci-dessus).

| REQ | Exigence | Test cle |
|---|---|---|
| 001 | Aucune valeur sensible dans le payload envoye au backend | Faux backend capture le HTTP, valeurs de l'oracle absentes |
| 002 | Re-identification exacte (a la forme canonique pres pour les alias fusionnes) | `reidentifier(pseudonymiser(t)) == t` sur le corpus |
| 003 | Journal sans DCP | Aucune valeur de l'oracle dans les logs |
| 004 | Vault chiffre au repos | Inspection binaire : aucune valeur en clair |
| 005 | Compteurs persistants par dossier | Redemarrage simule : aucun placeholder reattribue |
| 006 | Placeholders inconnus bloquants | `[PERSONNE_999]` absent du vault : blocage ou revue |
| 007 | Separation demo / serieux | Mode serieux ne retourne jamais le vault ni les valeurs |
| 008 | Dates procedurales vs date de naissance | Politique configuree par dossier |
| 009 | Corpus 100% synthetique | Aucune donnee reelle dans les tests |
| 010 | Pas de streaming v1 | `stream=true` -> HTTP 400 explicite |

## Ce que l'agent doit signaler au lieu de resoudre seul

- Un test d'invariant qui contredit une exigence.
- Une dependance dont la licence est incompatible EUPL-1.2.
- Un cas ou la pseudonymisation detruit l'utilite metier du texte.
- Toute situation ou la spec pousse a journaliser ou exposer une valeur brute.

## Commandes utiles

```bash
uv venv && uv pip install -e ".[dev]"          # installation (socle sans NER)
uv pip install -e ".[dev,ner]"                  # installation avec NER (CamemBERT)
uv run python -m sas_confiance_ia.telechargement # telechargement du modele NER (une fois)
uv run pytest                                    # suite complete
uv run pytest -m "not ner"                      # sans les tests NER
uv run ruff check src tests                      # lint
python -m sas_confiance_ia                       # lancer le sas (localhost:8787)
```
