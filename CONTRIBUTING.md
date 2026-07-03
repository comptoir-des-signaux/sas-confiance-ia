# Contribuer à Sas Confiance IA

Merci de votre intérêt pour ce commun numérique. Ce document décrit comment
contribuer sans casser ce qui fait la valeur du projet : des garanties de
sécurité prouvées par des tests, et une honnêteté totale sur les limites.

> *English: contributions are welcome. Security invariants are proven by
> tests and must never be weakened; the test suite makes no network call and
> contains no real personal data. Open an issue first for any significant
> change. Code, comments and commits are in French.*

## L'esprit du projet

Le sas est conçu pour les collectivités territoriales et la fonction publique
française. Trois conséquences pratiques :

1. **La confiance se prouve, elle ne se déclare pas.** Chaque invariant de
   sécurité (REQ-001 à 010, voir [`docs/specs/03-SPEC.md`](docs/specs/03-SPEC.md))
   est vérifié par un test automatisé sur un faux backend de capture.
2. **Les limites se publient.** Un cas non détecté ou une ambiguïté devient
   soit un test, soit une ligne dans la documentation : jamais un silence.
3. **Français d'abord.** Code, commentaires, commits, documentation :
   français accentué. Le README porte un résumé anglais.

## Interdictions absolues

Toute contribution qui enfreint l'un de ces points sera refusée, quelle que
soit sa qualité technique :

1. **Aucun appel réseau externe** depuis la suite de tests : pas d'API, pas
   de télémétrie, pas de téléchargement au runtime. Un test l'interdit
   activement ; les modèles se téléchargent au build ou à l'installation.
2. **Aucune donnée réelle** : tout exemple, fixture, docstring ou test
   utilise le corpus synthétique ([`corpus/synthetique/`](corpus/synthetique/))
   ou des valeurs inventées à clés valides. Ne copiez jamais un exemple
   contenant un nom réel trouvé en ligne.
3. **Le vault ne transite jamais** vers un LLM, un journal, une réponse API
   en mode sérieux, ni un message d'erreur.
4. **Ne jamais affaiblir un test d'invariant** (REQ-001 à 010) pour le faire
   passer. Si un test vous semble faux, ouvrez une issue plutôt que de le
   modifier.
5. **Pas de secret en dur**, pas de clé committée, pas de `.env` versionné.

## Mise en route

```bash
git clone https://github.com/comptoir-des-signaux/sas-confiance-ia.git
cd sas-confiance-ia
uv venv && uv pip install -e ".[dev]"
uv run pytest -m "not ner"      # socle, sans les dépendances NER
uv run ruff check src tests     # lint
```

Pour travailler sur la détection NER (CamemBERT), voir le README : les tests
NER s'exécutent dès que le modèle épinglé est présent en cache.

## Méthode

- **Tests d'abord** : toute fonctionnalité ou correction arrive avec son test,
  écrit avant l'implémentation (rouge, puis vert, puis refactor).
- **Commits atomiques en français** : un commit fait une chose et la dit
  clairement. Pas de tiret cadratin dans les textes.
- **Documentation dans le même commit** : si votre changement touche un
  comportement documenté, la documentation change avec lui.
- **Suite complète verte** avant toute demande de fusion : les tests de
  non-fuite (payload et journaux) portent sur toute la suite, pas seulement
  sur votre lot.

## Proposer un changement

1. **Ouvrez une issue** avant tout changement significatif : nouveau
   détecteur, nouvelle politique, changement d'API. Décrivez le besoin métier
   (quelle collectivité, quel document, quel risque).
2. Pour un correctif simple (faute, cas de détection manqué), une pull
   request directe avec son test suffit.
3. Toute nouvelle dépendance doit avoir une licence compatible EUPL-1.2 :
   signalez-la explicitement dans la pull request (la licence AGPL de
   PyMuPDF a par exemple été écartée, voir Q6 dans
   [`docs/specs/QUESTIONS.md`](docs/specs/QUESTIONS.md)).

## Signaler une faille ou une fuite

Si vous découvrez un chemin par lequel une valeur sensible peut atteindre le
backend, les journaux ou une réponse en mode sérieux : n'ouvrez pas d'issue
publique. Écrivez à Comptoir des Signaux (coordonnées sur
[comptoirdessignaux.com](https://www.comptoirdessignaux.com)) avec un cas
reproductible sur données synthétiques.

## Crédits et licence

Les validateurs français (NIR avec cas Corse, Luhn) reprennent le travail de
Romain Bochet ([rbochet/amo-presidio](https://github.com/rbochet/amo-presidio)),
réutilisé avec son accord. En contribuant, vous acceptez que votre apport
soit distribué sous [EUPL-1.2](LICENSE).
