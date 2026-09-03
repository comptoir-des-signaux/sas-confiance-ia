# Surcoût en jetons de la pseudonymisation

**Mesure du 2026-09-03** sur le corpus synthétique (`corpus/synthetique/`),
moteur transformers de Presidio, modèle `Jean-Baptiste/camembert-ner`
épinglé à la révision `ef35fe7767c1dad71f5c853838cdd80d0b3441ed`,
encodage `cl100k_base` (tiktoken).

Question posée en public : pseudonymiser gonfle-t-il la facture de jetons
envoyée au backend ? Deux effets s'opposent. Un identifiant en clair coûte
cher à encoder (un NIR est une suite de chiffres espacés) là où son
placeholder est compact ; à l'inverse, le proxy ajoute à chaque requête
portant des jetons une consigne système de préservation
(`CONSIGNE_PRESERVATION_JETONS`, parade F5 du 02-AI-SPEC §3).

## Résultats

| Document | Entités | Jetons en clair | Jetons pseudonymisé | Écart |
|---|---|---|---|---|
| `01-courrier-usager.md` | 22 | 312 | 317 | +5 |
| `02-note-rh.md` | 15 | 279 | 304 | +25 |
| `03-contrat-prestation.md` | 19 | 349 | 351 | +2 |
| `04-dossier-usager/piece-1-courrier.md` | 17 | 246 | 256 | +10 |
| `04-dossier-usager/piece-2-note-interne.md` | 10 | 247 | 257 | +10 |
| `04-dossier-usager/piece-3-compte-rendu.md` | 6 | 232 | 241 | +9 |
| `05-compte-rendu-reunion.md` | 13 | 301 | 322 | +21 |
| `06-canaris.md` | 1 | 297 | 293 | -4 |
| `07-conseil-medical.md` | 252 | 4369 | 4348 | -21 |

**Total : 9 documents, 355 entités, 6632 jetons en clair contre 6689
pseudonymisés, soit +0,9 % sur le texte.** La consigne système ajoute
89 jetons à chaque requête, soit +2,2 % sur ce corpus.

## Méthodologie

- Chaque document est pseudonymisé dans un dossier distinct : des compteurs
  partagés feraient dépendre la numérotation des placeholders, donc leur
  coût, de l'ordre de lecture des fichiers.
- Le comptage porte sur le texte des messages. Il ignore l'enveloppe de chat
  (rôles, balises de conversation) qui varie d'un backend à l'autre et que le
  sas ne modifie pas.
- Reproduire : `uv pip install -e ".[ner,jetons]"` puis
  `uv run python -m sas_confiance_ia.evaluation_jetons`.
- Le calcul est couvert par `tests/test_evaluation_jetons.py`, avec un
  compteur injecté : l'encodage tiktoken se télécharge au premier usage, et
  aucun test de ce dépôt ne touche le réseau (AGENTS.md, interdiction 1).

## Lecture honnête des chiffres

- **Le vrai surcoût est une constante, pas un pourcentage.** Les 89 jetons de
  consigne se paient à chaque requête, quelle que soit sa taille. Ils pèsent
  +2,0 % sur le document de conseil médical (4369 jetons), mais près de
  **+30 % sur un tour de conversation court** de 300 jetons. Une facture
  raisonnée se lit donc par tour, pas en moyenne sur un corpus.
- **Sur le texte lui-même, la pseudonymisation est quasi neutre**, et devient
  favorable sur les documents denses en identifiants : `07-conseil-medical.md`
  perd 21 jetons une fois pseudonymisé. Un NIR en clair coûte 13 jetons,
  son placeholder 7 ; un courriel 11 contre 5. À l'inverse, un nom court
  coûte parfois moins cher que son jeton : les documents où les entités sont
  surtout des noms et des lieux (`02-note-rh.md`, +25) paient un peu plus.
- **Le chiffre dépend du tokenizer, donc du backend.** `cl100k_base` est
  l'encodage des modèles OpenAI ; un backend Mistral, Llama ou Qwen découpe
  autrement, en particulier les crochets et les tirets bas des placeholders.
  L'ordre de grandeur se transporte, pas la décimale : rejouer la mesure avec
  `--encodage` sur le tokenizer réellement visé.
- **Cette mesure ne dit rien du coût en euros.** Elle compte des jetons
  d'entrée. Le sas convertit par ailleurs `stream=true` en non-streaming
  (REQ-010) : sans effet sur le nombre de jetons, avec effet sur la latence
  perçue.
- **La comptabilité de jetons du backend n'est pas relayée** : la réponse du
  sas ne reprend pas le bloc `usage` renvoyé par le fournisseur. Un appelant
  qui pilote un budget doit aujourd'hui le mesurer lui-même. Limite connue,
  suivie en dette.
