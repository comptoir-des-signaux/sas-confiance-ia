# Checklist de publication (REQ-015)

À dérouler intégralement **avant tout push public** (première publication ou
reprise après une période de travail privé). Chaque ligne se coche avec la
commande ou la vérification indiquée. Une case non cochée bloque le push.

## 1. Secrets

- [ ] **Scan de l'historique complet** : aucun motif de secret (clés privées,
  jetons GitHub/OpenAI/Slack, AKIA, `password=`) sur toutes les révisions.

  ```bash
  git grep -iEn "BEGIN (RSA|EC|OPENSSH|PGP|DSA)? ?PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|github_pat_|xox[baprs]-|sk-[A-Za-z0-9]{20,}" $(git rev-list --all)
  ```

- [ ] **Scan outillé des fichiers suivis** : `git ls-files -z | xargs -0 uvx
  detect-secrets scan`, chaque signalement examiné et justifié. Faux positifs
  connus et acceptés : la fausse clé `sas-no-key-required` du
  `docker-compose.yml` et le hash de révision épinglée du modèle CamemBERT
  (`ner.py`, `docs/eval/ner-baseline.json`).
- [ ] **Aucun fichier sensible jamais committé** (`.env`, `*.pem`, `*.key`,
  `credentials`) :

  ```bash
  git log --all --diff-filter=A --name-only --pretty=format: | sort -u | grep -iE "\.env|secret|credential|\.pem$|\.key$|id_rsa"
  ```

- [ ] `.gitignore` couvre `.env`, `.env.*` et le venv.

## 2. Données

- [ ] Le corpus est 100 % synthétique (REQ-009) : aucun fichier issu de
  données client ou personnelles réelles, dans l'arbre **et** dans
  l'historique.
- [ ] Aucun nom de personne réelle dans les exemples, docstrings et tests
  (les noms de tiers repérés ont été transposés, voir commit « PV fictif
  transposé dans la Drôme »).
- [ ] Les journaux d'exemple et captures d'écran de la documentation ne
  montrent que des valeurs synthétiques.

## 3. Licences

- [ ] `LICENSE` = EUPL-1.2, référencée dans le README et `pyproject.toml`.
- [ ] Toutes les dépendances (y compris extras `ner`, `ner-repli-spacy`,
  `docs`) ont une licence compatible EUPL-1.2 ; PyMuPDF (AGPL) reste exclu
  (arbitrage Q6).
- [ ] Crédit de Romain Bochet (rbochet/amo-presidio) présent dans le README,
  le CONTRIBUTING et les en-têtes des modules concernés (`validators.py`,
  `detection.py`, `politique.py`).

## 4. Métadonnées et hygiène des fichiers

- [ ] Aucun fichier livré (exports `.docx` d'exemple, images) ne porte de
  métadonnée de génération automatique (« python-docx », dates factices) :
  les exports du sas recopient les propriétés du document source.
- [ ] Pas de tiret cadratin dans les textes publiés ; français accentué
  partout.
- [ ] « Comptoir des Signaux », jamais « Le Comptoir des Signaux ».
- [ ] Aucune consigne de travail interne (règles personnelles, chemins de
  postes de travail, conventions d'agents hors projet) dans les documents
  publiés : toute exigence citée s'appuie sur le cadrage du dépôt.

## 5. État du dépôt

- [ ] Suite complète verte (`uv run pytest`), lint propre
  (`uv run ruff check src tests`), CI verte sur `main`.
- [ ] `README.md` : état du projet à jour, résumé anglais présent.
- [ ] `docs/specs/QUESTIONS.md` : aucun report silencieux, chaque question
  ouverte a un statut.
- [ ] Le site de documentation se construit (`uv run mkdocs build --strict`).

## Journal des passages

| Date | Périmètre | Résultat | Qui |
|---|---|---|---|
| 2026-07-03 | Historique complet (sections 1 et 2) | Propre : aucun secret, aucun fichier sensible, 3 faux positifs documentés | Claude (session lot 16), contresigné par Pascal Chevallot le 2026-07-03 |
