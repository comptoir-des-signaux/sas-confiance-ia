# 05-PLAN : plan TDD par petits lots

**Statut :** v0.1 du 2026-07-01. Chaque lot suit le cycle rouge → vert →
refactor : les tests du lot sont écrits et échouent AVANT le code. Un lot n'est
commencé que lorsque le précédent est vert. Les REQ citées renvoient au 03-SPEC.

Stack : Python 3.12+, `pyproject.toml` (uv), FastAPI, pytest, ruff. Structure
`src/sas_confiance_ia/` et `tests/`. Docker en Lot 10.

---

## Phase 0 : le socle qui prouve les invariants

### Lot 0 : scaffold
Repo initialisé : `pyproject.toml`, `src/`, `tests/`, `.gitignore` strict
(vaults, clés, `.env`, corpus non synthétiques), CI GitHub Actions (pytest +
ruff), licence EUPL-1.2, README minimal avec crédit Romain Bochet.
**Vert :** `pytest` passe (un test sanité), CI verte.

### Lot 1 : validateurs français purs
`nir_key`, `nir_is_valid` (dont Corse 2A/2B), `luhn_ok` (SIREN/SIRET),
`iban_valid`. Fonctions pures, sans dépendance modèle : réemploi des
implémentations de Romain Bochet après accord (ADR-001), avec tests exhaustifs
(valides, invalides, clés fausses, espaces, séparateurs).
**REQ :** 016 (partiel). **Rouge d'abord :** cas de test issus du corpus.

### Lot 2 : corpus synthétique et oracle
`corpus/synthetique/` : 5 scénarios + dossier multi-pièces +
`valeurs-connues.json` (oracle de non-fuite). Test de cohérence : chaque valeur
déclarée est bien présente dans son document source.
**REQ :** 009.

### Lot 3 : détection déterministe (C1)
Reconnaisseurs en Python pur (regex + validateurs du Lot 1) : NIR, SIRET,
SIREN, IBAN, email, téléphone FR, plaque, date de naissance en contexte.
Résolution des chevauchements selon la priorité REQ-016 (le SIRET l'emporte
sur CREDIT_CARD). Interface compatible avec l'intégration Presidio du Lot 9 :
la Phase 0 reste sans modèle et sans téléchargement (règle 1 du HANDOFF),
Presidio in-process (ADR-009) arrive avec le NER en Phase 1.
**Vert :** rappel 1,0 sur les types déterministes du corpus.

### Lot 4 : pseudonymisation et vault en mémoire
Placeholders typés `[PERSONNE_001]`, compteurs par dossier et par type,
mapping bidirectionnel. `reidentifier(pseudonymiser(t)) == t`.
**REQ :** 002 (en mémoire), 011 (squelette : même valeur → même placeholder).

### Lot 5 : vault persistant chiffré et compteurs durables
SQLite chiffré (SQLCipher) ou fichier Fernet, clé via keyring. Test de
redémarrage simulé : aucun placeholder réattribué, dossiers isolés. Inspection
binaire : aucune valeur en clair.
**REQ :** 004, 005.

### Lot 6 : faux backend de capture et proxy minimal
`POST /v1/chat/completions` + `GET /v1/models` (FastAPI). Le faux backend
enregistre le payload HTTP exact. Tests de non-fuite : aucune valeur de
l'oracle dans le payload capturé. `stream=true` → 400 explicite.
**REQ :** 001, 010, 013 (partiel : format OpenAI).

### Lot 7 : contrôle d'intégrité et ré-identification de la réponse
Placeholders inconnus / manquants / altérés → rapport d'intégrité, blocage ou
`review_required`. Headers `X-Dossier-Id`, `X-Privacy-Mode`,
`X-Reidentify-Response`.
**REQ :** 006, et les 5 cas de test d'intégrité du cadrage §14.6.

### Lot 8 : journalisation propre
Journal structuré (métadonnées seules). Test : aucune valeur de l'oracle, aucun
prompt, aucune réponse, aucun secret dans les logs produits par toute la suite.
**REQ :** 003.

**Fin de Phase 0 : les 7 invariants du cadrage sont prouvés par des tests sur
faux backend. Aucun appel externe n'a jamais été émis.**

## Phase 1 : détection sérieuse et premier vrai backend

### Lot 9 : NER CamemBERT (C2)
Moteur transformers de Presidio avec modèle NER français épinglé ; repli spaCy
configurable. Mesure de rappel / précision PERSON, ORG, LOC publiée.
**REQ :** 016 complet. Porte d'éval 4.4 du 02-AI-SPEC en place.

### Lot 10 : Docker et backend réel
Dockerfile + compose (GPU NVIDIA optionnel), backend Ollama local puis
Infomaniak par configuration (ADR-005, ADR-013). Les tests restent sur faux
backend ; un test d'intégration manuel documenté valide Ollama.
**REQ :** 013 complet.

### Lot 11 : coréférence par dossier (C4)
Normalisation (casse, civilités, nom seul vs nom complet), alias persistants
par dossier, multi-pièces. Ambiguïtés → revue.
**REQ :** 011.

### Lot 12 : interface web minimale
Page unique servie par le même FastAPI : coller, choisir le mode, voir le
résumé des détections (types et comptes en mode sérieux), télécharger,
ré-identifier. Bandeau démo distinct.
**REQ :** 007 côté UI.

## Phase 2 : différenciateurs

### Lot 13 : juge LLM local (C3)
Passe Ollama optionnelle, sortie JSON stricte, candidats en revue humaine,
test réseau zéro appel sortant, éval canaris.
**REQ :** 014.

### Lot 14 : politiques par type et surrogates
Politique configurable par type d'entité (cadrage §9.5), dates différenciées,
surrogates genrés optionnels (Faker fr_FR).
**REQ :** 008, 012.

### Lot 15 : fichiers
Ingestion `.txt`, `.md`, `.docx`, `.pdf` textuel ; refus documenté des PDF
scannés.

### Lot 16 : publication du commun
MkDocs Material + GitHub Pages, tutoriel d'installation Kubuntu / Docker,
parcours formateur, CONTRIBUTING, checklist de publication, scan de secrets
sur l'historique.
**REQ :** 015.

---

## Règles transverses

1. Jamais de code sans test rouge préalable dans le lot.
2. Jamais de donnée réelle, jamais d'appel réseau externe dans la suite de
   tests (un test l'interdit activement).
3. Chaque lot = un ou plusieurs commits atomiques, messages en français accentué.
4. Toute limite découverte (cas non détecté, ambiguïté) devient soit un test,
   soit une ligne dans la section « limites » de la doc : jamais un silence.
