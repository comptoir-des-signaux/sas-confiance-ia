# AGENTS.md : Sas Confiance IA

Sas de pseudonymisation avant IA pour les collectivités territoriales et la
fonction publique française. Porté par Comptoir des Signaux, licence EUPL-1.2.

Ce document s'adresse à tout agent de code travaillant sur ce projet et prime
sur les habitudes de l'agent.

> **Pourquoi ce fichier est public.** Le sas a été construit en grande partie
> avec des agents de code, sous contraintes strictes. Publier ces contraintes
> fait partie de la transparence du projet : on peut vérifier non seulement ce
> que fait le code, mais la discipline sous laquelle il a été écrit. Un
> relecteur humain y trouvera aussi le résumé le plus court de l'architecture.

Lire avant d'agir : `docs/specs/06-HANDOFF.md` (consignes strictes),
`docs/specs/03-SPEC.md` (exigences falsifiables), `docs/specs/05-PLAN.md`
(plan TDD par lots).

## Stack

Python 3.12+, gestion par `uv`, FastAPI, pytest, ruff. Presidio in-process
(ADR-009). Modèles épinglés par version exacte. Docker Compose pour le
déploiement (sas + Ollama optionnel).

## Structure du code

```
src/sas_confiance_ia/
  api.py              Proxy OpenAI-compatible (/v1/chat/completions, /v1/models)
  pseudonymiseur.py   Orchestrateur central : détection -> vault -> envoi -> intégrité -> ré-identification
  detection.py        Pipeline C1 (regex) + C2 (NER) + C3 (juge), résolution des chevauchements (REQ-016)
  ner.py              Couche C2 : CamemBERT via Presidio (repli spaCy)
  juge.py             Couche C3 : LLM local via Ollama, sortie JSON stricte, candidats en revue
  coreference.py      Couche C4 : résolution par dossier, alias, formes canoniques
  politique.py        Politiques par type : pseudonymiser / masquer / conserver / revue (cadrage 9.5)
  surrogates.py       Noms factices Faker fr_FR genrés, rendu par-dessus les placeholders (REQ-012)
  vault.py            Vault abstrait + VaultMemoire (correspondances en mémoire)
  integrite.py        Contrôle des placeholders en sortie (altérés, inventés, manquants)
  backends.py         BackendOpenAICompatible (réel) + BackendCapture (faux, pour les tests)
  configuration.py    Configuration par variables d'environnement
  validators.py       Validateurs français purs : NIR (clé, Corse 2A/2B), Luhn (SIREN/SIRET), IBAN
  fichiers.py         Extraction .txt/.md/.csv/.docx/.pdf textuel, refus documenté des PDF scannés
  journal.py          Journal structuré sans DCP (métadonnées techniques uniquement)
  ui.py               Interface web minimale (copier-coller, modes sérieux/démo)
  evaluation.py       Évaluation du rappel NER sur corpus synthétique
  evaluation_juge.py  Évaluation du juge LLM sur les canaris
  evaluation_jetons.py Surcoût en jetons de la pseudonymisation (compteur injecté)
tests/                200+ tests, tous sur faux backend, aucun appel réseau
corpus/synthetique/   Corpus 100 % synthétique avec oracle de non-fuite
docs/specs/           PRD, AI-SPEC, SPEC (REQ-001 à 016), ADR, PLAN, HANDOFF, QUESTIONS
```

Les modules les plus connectés, donc les plus coûteux à modifier :
`VaultMemoire`, `Pseudonymiseur`, `detecter()`, `Vault`,
`charger_configuration()`. Avant de toucher l'un d'eux, lire ses appelants.

## Interdictions absolues (violations = arrêt immédiat)

1. **Aucun appel réseau externe** depuis les tests : pas d'API, pas de
   télémétrie, pas de téléchargement au runtime. Un test l'interdit activement.
2. **Aucune donnée réelle** : tout exemple, fixture ou test utilise le corpus
   synthétique ou des valeurs inventées à clés valides.
3. **Le vault ne transite jamais** vers un LLM, un log, une réponse API en mode
   sérieux, ou un message d'erreur.
4. **Ne jamais affaiblir un test d'invariant** (REQ-001 à 010) pour le faire
   passer. Si un test semble faux, s'arrêter et le signaler.
5. **Pas de secret en dur**, pas de clé committée, pas de `.env` versionné.
6. **Pas de tiret cadratin** dans les textes produits ; français accentué
   partout (code, commentaires, commits, docs).

## Méthode imposée

- **TDD strict** : suivre les lots du `05-PLAN.md` dans l'ordre. Pour chaque
  lot : tests en rouge d'abord, implémentation minimale, vert, refactor,
  commit atomique.
- **Commits atomiques** en français : un commit ne mélange jamais deux lots.
- **Aucune fonctionnalité non demandée** : pas de streaming, pas d'OCR, pas
  d'authentification, pas de connecteur, même « pour préparer la suite ».
- **Toute ambiguïté de spec** : choisir l'interprétation la plus protectrice
  pour les données, la consigner dans `docs/specs/QUESTIONS.md` à faire
  arbitrer.

## Définition de « terminé » pour un lot

1. Tests du lot verts, suite complète verte, ruff sans erreur.
2. Les tests de non-fuite (payload + logs) passent sur TOUTE la suite.
3. Aucun `TODO` silencieux : chaque report est tracé dans `QUESTIONS.md`.
4. La documentation touchée par le lot est mise à jour dans le même commit.

## Invariants de sécurité (REQ-001 à 010)

Ces exigences sont prouvées par des tests sur faux backend de capture. Les
affaiblir est une interdiction absolue (voir ci-dessus).

| REQ | Exigence | Test clé |
|---|---|---|
| 001 | Aucune valeur sensible dans le payload envoyé au backend | Faux backend capture le HTTP, valeurs de l'oracle absentes |
| 002 | Ré-identification exacte (à la forme canonique près pour les alias fusionnés) | `reidentifier(pseudonymiser(t)) == t` sur le corpus |
| 003 | Journal sans DCP | Aucune valeur de l'oracle dans les logs |
| 004 | Vault chiffré au repos | Inspection binaire : aucune valeur en clair |
| 005 | Compteurs persistants par dossier | Redémarrage simulé : aucun placeholder réattribué |
| 006 | Placeholders inconnus bloquants | `[PERSONNE_999]` absent du vault : blocage ou revue |
| 007 | Séparation démo / sérieux | Mode sérieux ne retourne jamais le vault ni les valeurs |
| 008 | Dates procédurales vs date de naissance | Politique configurée par dossier |
| 009 | Corpus 100 % synthétique | Aucune donnée réelle dans les tests |
| 010 | Pas de streaming v1 | `stream=true` -> conversion en `stream=false` journalisée (statut `conversion_streaming`), réponse complète jamais en flux |

## Ce que l'agent doit signaler au lieu de résoudre seul

- Un test d'invariant qui contredit une exigence.
- Une dépendance dont la licence est incompatible EUPL-1.2.
- Un cas où la pseudonymisation détruit l'utilité métier du texte.
- Toute situation où la spec pousse à journaliser ou exposer une valeur brute.

## Commandes utiles

```bash
uv venv && uv pip install -e ".[dev]"           # installation (socle sans NER)
uv pip install -e ".[dev,ner]"                   # installation avec NER (CamemBERT)
uv run python -m sas_confiance_ia.telechargement # téléchargement du modèle NER (une fois)
uv run pytest                                    # suite complète
uv run pytest -m "not ner"                       # sans les tests NER
uv run ruff check src tests                      # lint
python -m sas_confiance_ia                       # lancer le sas (localhost:8787)
```
