# 06-HANDOFF : consignes strictes pour l'agent de code

**Statut :** v0.1 du 2026-07-01. Ce document s'adresse à tout agent (Claude
Code ou autre) qui implémente Sas Confiance IA. Il prime sur toute habitude ou
préférence de l'agent. Lire d'abord : 00-CONTEXT, 03-SPEC, 05-PLAN.

---

## Interdictions absolues (violations = arrêt immédiat)

1. **Aucun appel réseau externe** depuis le code de test ou la Phase 0 : pas
   d'API OpenAI, Anthropic, Mistral, Infomaniak, Scaleway, pas de télémétrie,
   pas de téléchargement au runtime. Les modèles (spaCy, CamemBERT) se
   téléchargent au build (Dockerfile ou étape d'installation documentée),
   jamais pendant les tests.
2. **Aucune donnée réelle** : tout exemple, fixture, docstring ou test utilise
   le corpus synthétique ou des valeurs inventées à clés valides. Ne jamais
   copier un exemple contenant un nom réel trouvé en ligne.
3. **Le vault ne transite jamais** vers un LLM, un log, une réponse API en mode
   sérieux, ou un message d'erreur.
4. **Ne jamais affaiblir un test d'invariant** (REQ-001 à 010) pour le faire
   passer. Si un test semble faux, s'arrêter et le signaler.
5. **Pas de secret en dur**, pas de clé committée, pas de `.env` versionné.
6. **Pas de tiret cadratin** dans les textes produits ; français accentué
   partout (code, commentaires, commits, docs).

## Méthode imposée

- **TDD strict** : suivre les lots du 05-PLAN dans l'ordre. Pour chaque lot :
  écrire les tests, vérifier qu'ils échouent (rouge), implémenter le minimum,
  vérifier le vert, refactorer, committer.
- **Commits atomiques** en français : un lot peut faire plusieurs commits, un
  commit ne mélange jamais deux lots.
- **Aucune fonctionnalité non demandée** : pas de streaming, pas d'OCR, pas
  d'authentification, pas de connecteur en Phase 0-1, même « pour préparer la
  suite ».
- **Toute ambiguïté de spec** : choisir l'interprétation la plus protectrice
  pour les données, la consigner en commentaire de commit et dans un fichier
  `docs/specs/QUESTIONS.md` à faire arbitrer.

## Définition de « terminé » pour un lot

1. Tests du lot verts, suite complète verte, ruff sans erreur.
2. Les tests de non-fuite (payload + logs) passent sur TOUTE la suite, pas
   seulement le lot.
3. Aucun `TODO` silencieux : chaque report est tracé dans `QUESTIONS.md`.
4. La documentation touchée par le lot est mise à jour dans le même commit.

## Contexte technique de référence

- Python 3.12+, gestion par `uv`, FastAPI, pytest, ruff.
- Presidio in-process (ADR-009) ; modèles épinglés par version exacte.
- Poste cible : Kubuntu 26.04, RTX 5090 24 Go VRAM, 128 Go RAM, Docker avec
  NVIDIA container toolkit.
- L'accord de Romain Bochet pour le réemploi des reconnaisseurs français
  d'`rbochet/amo-presidio` est acquis (2026-07-01, ADR-001) : créditer son
  travail dans le README et les en-têtes des modules concernés.

## Ce que l'agent doit signaler au lieu de résoudre seul

- Un test d'invariant qui contredit une exigence.
- Une dépendance dont la licence est incompatible EUPL-1.2.
- Un cas où la pseudonymisation détruit l'utilité métier du texte.
- Toute situation où la spec pousse à journaliser ou exposer une valeur brute.
