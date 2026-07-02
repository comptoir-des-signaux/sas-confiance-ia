# Sas Confiance IA

**Le sas de pseudonymisation avant IA** : détectez les données personnelles
françaises dans vos textes, remplacez-les par des pseudonymes, envoyez le texte
protégé à un modèle de langage, puis ré-identifiez la réponse **en zone de
confiance**. La table de correspondance ne quitte jamais votre infrastructure.

Un commun numérique porté par [Comptoir des Signaux](https://comptoirdessignaux.fr),
conçu pour les collectivités territoriales et la fonction publique, sous
licence [EUPL-1.2](LICENSE).

> *English summary: a French-first pseudonymization gateway for LLM usage.
> Detects French personal data (NIR, SIRET, IBAN, names...), substitutes
> reversible placeholders, proxies OpenAI-compatible requests, re-identifies
> responses locally. The mapping vault never leaves your trust zone.*

## Ce que le sas garantit (et ne garantit pas)

Le sas **réduit** les données personnelles transmises aux modèles d'IA et rend
ces flux **vérifiables** : des tests capturent le payload réellement envoyé et
échouent si une valeur sensible connue y figure.

Le sas **ne garantit pas** une anonymisation parfaite ni une conformité RGPD
automatique : aucun détecteur n'atteint 100 % de rappel, la ré-identification
par faisceau d'indices reste possible, et l'outil assiste le responsable de
traitement sans remplacer le DPO, l'AIPD ni le registre. Ces limites sont
documentées et mesurées, jamais masquées.

## Principes

1. **Local-first** : la détection, le vault et la ré-identification tournent
   dans votre zone de confiance. Aucun appel externe pendant la pseudonymisation.
2. **Vérifiable** : chaque invariant de sécurité est prouvé par un test
   automatisé sur un faux backend de capture.
3. **Français d'abord** : NIR (avec clé de contrôle, Corse incluse),
   SIRET / SIREN (Luhn), IBAN, téléphones, puis NER français (CamemBERT).
4. **Pédagogique** : un mode démonstration, des données 100 % synthétiques et
   un tutoriel pensé pour la formation.
5. **Sobre et honnête** : pseudonymisation nommée pseudonymisation ;
   l'anonymisation irréversible est un mode, pas une promesse.

## État du projet

**Phase 1 en cours (lots 9 et 10 livrés)** : plus de 100 tests automatisés
prouvent les invariants de sécurité sur faux backend de capture : non-fuite
des valeurs détectées, désormais au périmètre complet noms / lieux /
organisations inclus (REQ-001), ré-identification exacte (REQ-002), journaux
sans donnée personnelle (REQ-003), vault chiffré au repos (REQ-004),
compteurs persistants (REQ-005), placeholders inconnus bloquants (REQ-006),
streaming refusé (REQ-010). La détection s'appuie sur le NER français
CamemBERT (modèle épinglé, rappel et précision
[mesurés et publiés](docs/eval/evaluation-ner.md)) et le proxy parle à tout
backend OpenAI-compatible par simple configuration (REQ-013) : Ollama local,
Infomaniak, Scaleway... La coréférence par dossier (REQ-011) rattache les
mentions d'une même personne (« Jean Dupont », « M. Dupont ») au même
placeholder entre les pièces d'un dossier ; la ré-identification restitue la
forme la plus complète connue et les rattachements ambigus sont signalés
pour revue, jamais fusionnés (limite documentée dans
[`docs/specs/QUESTIONS.md`](docs/specs/QUESTIONS.md)). Voir
[`docs/deploiement.md`](docs/deploiement.md)
pour l'installation Docker et la validation manuelle,
[`docs/specs/`](docs/specs/) pour le cadrage complet et
[`docs/specs/05-PLAN.md`](docs/specs/05-PLAN.md) pour la feuille de route.
Une interface web minimale est servie à la racine (`http://127.0.0.1:8787/`) :
coller un texte, pseudonymiser, ré-identifier ; le mode sérieux n'affiche
jamais les valeurs détectées (types, positions et comptes seulement), le mode
démonstration (bandeau distinct, données synthétiques) refuse de s'activer si
des dossiers sérieux sont actifs dans l'instance. Phase 1 complète ;
prochaine phase : juge LLM local, politiques par type, fichiers.

## Démarrage (développement)

```bash
git clone https://github.com/comptoir-des-signaux/sas-confiance-ia.git
cd sas-confiance-ia
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

### Détection NER (noms, organisations, lieux)

La couche NER (CamemBERT via Presidio, modèle épinglé par révision exacte)
est optionnelle : le socle fonctionne sans elle, avec la seule détection
déterministe. Pour l'activer :

```bash
# Sans GPU dédié au NER (recommandé : le GPU sert au LLM local, pas au NER) :
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e ".[dev,ner]"
# Téléchargement unique du modèle épinglé (jamais au runtime ni en test) :
uv run python -m sas_confiance_ia.telechargement
uv run pytest            # les tests NER s'exécutent dès que le modèle est présent
```

Repli léger sans transformers (machine modeste) : installer l'extra
`[ner-repli-spacy]` (spaCy `fr_core_news_lg`) et lancer avec
`SAS_NER=spacy`. La couverture est moindre que CamemBERT ; la mesure
publiée fait foi.

Au lancement du proxy, le NER est actif par défaut et **fail-closed** : si
le moteur demandé n'est pas chargeable, le sas refuse de démarrer plutôt
que de tourner silencieusement avec une couverture réduite. Un sas sans
NER se choisit explicitement (`SAS_NER=inactif`).

## Crédits

- Les validateurs français (clé NIR avec cas Corse 2A/2B, Luhn SIREN / SIRET)
  reprennent le travail de **Romain Bochet**
  ([rbochet/amo-presidio](https://github.com/rbochet/amo-presidio)), réutilisé
  avec son accord. Merci Romain.
- Détection : [Microsoft Presidio](https://github.com/microsoft/presidio)
  (MIT) à partir de la Phase 1.
- Corpus de test : entièrement synthétique, voir
  [`corpus/synthetique/`](corpus/synthetique/).

## Licence

[EUPL-1.2](LICENSE) : licence publique de l'Union européenne. Vous pouvez
utiliser, modifier et redistribuer ce logiciel, y compris commercialement, à
condition de conserver la licence sur les œuvres dérivées.
