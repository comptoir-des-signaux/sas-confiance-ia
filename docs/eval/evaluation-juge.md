# Évaluation du juge LLM (C3) sur les canaris

**Mesure du 2026-07-02** sur le sous-corpus canaris
(`corpus/synthetique/06-canaris.md`) : six identifiants indirects fictifs que
C1 et C2 manquent par construction (fonction rare, petite commune, surnom,
périphrase, matricule). Conformément au 02-AI-SPEC §4.3, il n'y a **pas de
seuil dur en v1** : la fraction signalée est publiée telle quelle et sert de
non-régression au changement de modèle juge (F9).

Le texte est d'abord pseudonymisé par C1+C2 (moteur transformers, comme en
production), puis soumis au juge via Ollama local. Un canari compte comme
signalé si un candidat du juge recouvre l'un de ses extraits de référence
(`verite-terrain-canaris.json`) : inclusion dans un sens ou dans l'autre, ou
majorité des mots significatifs retrouvés.

## Résultats

| Canari | mistral-small:24b | qwen3:4b |
|---|---|---|
| fonction-rare-epci | oui | non |
| elu-petite-commune | oui | non |
| professionnelle-unique | oui | non |
| surnom-jojo | oui | oui |
| predecesseur-mute | non | non |
| matricule-atypique | oui | oui |
| **Total** | **5/6 (83 %)** | **2/6 (33 %)** |

- **mistral-small:24b** : 5 candidats émis, tous pertinents (aucun bruit sur
  cette mesure). Seule la périphrase du prédécesseur (« muté après vingt-deux
  ans dans le même bureau ») lui échappe.
- **qwen3:4b** : 2 candidats émis, pertinents mais couverture faible. Un
  modèle de cette taille illustre F8 (fausse assurance d'une troisième
  lecture) : préférer un modèle de la classe 20B+ pour le rôle de juge.

**Recommandation de référence : `mistral-small:24b`** (RTX 5090, ~14 Go de
VRAM, ~10 s par passe). Sans juge configuré, le sas fonctionne et journalise
explicitement la moindre couverture (REQ-014).

## Procédure (manuelle, hors CI)

La suite de tests n'appelle JAMAIS le réseau (garde-fou de `conftest.py`) :
cette mesure s'exécute à la main contre un Ollama local, à rejouer à chaque
changement de modèle juge (F9).

```bash
# Pile de démo (Ollama dans le réseau compose, non exposé sur l'hôte) :
docker compose cp corpus/synthetique/06-canaris.md sas:/tmp/06-canaris.md
docker compose cp corpus/synthetique/verite-terrain-canaris.json \
  sas:/tmp/verite-terrain-canaris.json
docker compose exec sas python -m sas_confiance_ia.evaluation_juge \
  --base-url http://ollama:11434/v1 --modele mistral-small:24b \
  --corpus /tmp/06-canaris.md --verite /tmp/verite-terrain-canaris.json

# Ollama installé sur l'hôte :
python -m sas_confiance_ia.evaluation_juge \
  --base-url http://127.0.0.1:11434/v1 --modele mistral-small:24b
```

Options : `--score-min` (défaut 0,5), `--moteur transformers|spacy|aucun`
(couche C2 appliquée avant la passe juge).

## Limites

- Six canaris seulement : la mesure est indicative, pas statistique. Le
  sous-corpus s'enrichit à chaque limite découverte (règle transverse 4 du
  plan).
- L'appariement souple peut compter comme signalé un candidat voisin de
  l'extrait attendu ; les candidats émis restent listés par la CLI pour
  vérification humaine.
- Les candidats du juge partent en revue : cette mesure ne dit rien du taux
  de faux positifs en usage réel (surveillé via F7, score minimal 0,5).
