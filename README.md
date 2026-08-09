# Sas Confiance IA

[![CI](https://github.com/comptoir-des-signaux/sas-confiance-ia/actions/workflows/ci.yml/badge.svg)](https://github.com/comptoir-des-signaux/sas-confiance-ia/actions/workflows/ci.yml)
[![Documentation](https://github.com/comptoir-des-signaux/sas-confiance-ia/actions/workflows/docs.yml/badge.svg)](https://github.com/comptoir-des-signaux/sas-confiance-ia/actions/workflows/docs.yml)
[![Licence EUPL-1.2](https://img.shields.io/badge/licence-EUPL--1.2-blue)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab)](pyproject.toml)

**Le sas de pseudonymisation avant IA** : détectez les données personnelles
françaises dans vos textes, remplacez-les par des pseudonymes, envoyez le texte
protégé à un modèle de langage, puis ré-identifiez la réponse **en zone de
confiance**. La table de correspondance ne quitte jamais votre infrastructure.

Un commun numérique porté par [Comptoir des Signaux](https://www.comptoirdessignaux.com),
conçu pour les collectivités territoriales et la fonction publique, sous
licence [EUPL-1.2](LICENSE).

**Documentation complète :**
[comptoir-des-signaux.github.io/sas-confiance-ia](https://comptoir-des-signaux.github.io/sas-confiance-ia/)

> *English summary: a French-first pseudonymization gateway for LLM usage.
> Detects French personal data (NIR, SIRET, IBAN, names...), substitutes
> reversible placeholders, proxies OpenAI-compatible requests, re-identifies
> responses locally. The mapping vault never leaves your trust zone.*

> [!WARNING]
> **Maturité : V1 locale, poste unique.** Le sas est conçu pour tourner dans
> votre zone de confiance, sur la boucle locale (`127.0.0.1`). Il ne porte
> **aucune authentification** : quiconque atteint son port et connaît un
> identifiant de dossier peut ré-identifier. Ne l'exposez pas sur un réseau
> partagé ni sur Internet sans authentification frontale, filtrage et cadrage
> DPO/RSSI. Usages visés aujourd'hui : poste de travail, atelier, formation,
> expérimentation contrôlée sur corpus synthétique.

## Le flux : ce qui reste, ce qui sort

![Schéma du flux : dans la zone de confiance, le poste de travail envoie un
document au sas, qui détecte les données personnelles, les remplace par des
pseudonymes et conserve la table de correspondance dans son vault. Seul le
texte pseudonymisé franchit la limite de la zone de confiance vers le backend
d'IA. La réponse revient pseudonymisée, puis le sas la ré-identifie localement.
Le journal ne contient que des métadonnées.](docs/assets/schema-flux.svg)

## La preuve par le flux

L'argument du sas n'est pas « nous pseudonymisons », c'est « vous pouvez le
vérifier ». Demandez au modèle de recopier votre question, ré-identification
désactivée : sa réponse brute montre ce qu'il a réellement reçu.

```bash
curl -s -X POST http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" -H "X-Dossier-Id: essai-001" \
  -H "X-Reidentify-Response: false" \
  -d '{
    "model": "mistral-small:24b",
    "messages": [{"role": "user", "content": "Recopie exactement ma question : quel dossier suit Marie Martin (marie.martin@exemple.fr) ?"}]
  }'
```

| Étape | Contenu |
|---|---|
| Ce que vous saisissez | `quel dossier suit Marie Martin (marie.martin@exemple.fr) ?` |
| Ce que le modèle reçoit | `quel dossier suit [PERSONNE_001] ([EMAIL_001]) ?` |
| Ce que le modèle renvoie | `quel dossier suit [PERSONNE_001] ([EMAIL_001]) ?` |
| Ce que vous recevez (ré-identification active) | `quel dossier suit Marie Martin (marie.martin@exemple.fr) ?` |

Le modèle n'a jamais vu les valeurs : il ne peut restituer que ce qu'il a reçu.
Cette propriété n'est pas déclarative, elle est tenue par des tests : un faux
backend capture le payload HTTP réellement émis, et la suite échoue si une
valeur de l'oracle synthétique y figure (REQ-001).

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

**Version publiée : [v0.1.0](https://github.com/comptoir-des-signaux/sas-confiance-ia/releases/tag/v0.1.0).**
Phase 1 complète, Phase 2 en cours (lots 13 à 15 livrés), publication du
commun close (lot 16).

### Ce qui est prouvé, pas déclaré

299 tests automatisés. Pendant la suite, le sas ne parle pas à un vrai modèle
mais à un faux backend qui enregistre le payload HTTP exact qu'il reçoit : les
tests échouent si une seule valeur de l'oracle synthétique y apparaît.

| Exigence | Ce qui est prouvé |
|---|---|
| REQ-001 | aucune valeur détectée dans le payload envoyé au backend, noms, lieux et organisations compris |
| REQ-002 | ré-identification exacte, à la forme canonique près pour les alias fusionnés |
| REQ-003 | journaux sans donnée personnelle |
| REQ-004 | vault chiffré au repos |
| REQ-005 | compteurs de placeholders persistants par dossier |
| REQ-006 | placeholders inconnus bloquants |
| REQ-007 | séparation stricte des modes démonstration et sérieux |
| REQ-008 | date de naissance distinguée des dates procédurales |
| REQ-009 | corpus de test 100 % synthétique |
| REQ-010 | streaming converti en non-streaming journalisé |

### Phase 1 : le socle (livrée)

- **Détection** : motifs français validés par leur clé de contrôle, puis NER
  CamemBERT (modèle épinglé par révision exacte, rappel et précision
  [mesurés et publiés](docs/eval/evaluation-ner.md)).
- **Proxy OpenAI-compatible** (REQ-013) : Ollama local, Infomaniak, Scaleway,
  par simple configuration, sans code spécifique par fournisseur.
- **Coréférence par dossier** (REQ-011) : « Jean Dupont » et « M. Dupont »
  reçoivent le même placeholder entre les pièces d'un dossier, et la
  ré-identification restitue la forme la plus complète connue. Un
  rattachement ambigu crée une entité distincte et part en revue : jamais de
  fusion hasardeuse (arbitrage Q1).
- **Interface web minimale** sur `http://127.0.0.1:8787/`, en deux colonnes :
  coller, pseudonymiser, ré-identifier. Le mode sérieux n'affiche jamais les
  valeurs détectées (types, positions et comptes seulement) ; le mode
  démonstration refuse de s'activer si un dossier sérieux existe dans
  l'instance.

### Phase 2 : affiner sans desserrer (lots 13 à 15 livrés)

- **Juge LLM local optionnel** (REQ-014) : relit le texte déjà pseudonymisé et
  signale les identifiants indirects (fonction rare, petite commune, surnom,
  périphrase) pour revue humaine, jamais en remplacement automatique.
  Couverture [mesurée et publiée sur les canaris](docs/eval/evaluation-juge.md).
- **Politiques par type d'entité** : pseudonymiser, masquer sans coffre,
  conserver ou signaler pour revue. Défauts par instance, surcharge par
  dossier conservée dans le vault.
- **Surrogates réalistes** (REQ-012, arbitrage Q5) : noms factices cohérents
  en genre, réversibles par le vault, en option par dossier. Le mode
  placeholder reste le défaut.
- **Fichiers** : glisser-déposer de `.txt`, `.md`, `.csv`, `.docx` et `.pdf`
  textuels, document et version pseudonymisée côte à côte avec surlignage,
  exports `.txt` et `.docx` reconstruit. Les PDF scannés sont refusés : pas
  d'OCR en v1.

### Publication du commun (lot 16, clos)

- **Site de documentation** MkDocs Material, publié par GitHub Actions à
  chaque commit sur `main` : [tutoriel d'installation](docs/tutoriel-installation.md),
  [guide de déploiement](docs/deploiement.md),
  [parcours formateur](docs/parcours-formateur.md),
  [comment ce sas a été construit](docs/methode.md) et le
  [cadrage complet](docs/specs/) rendu public par transparence.
- **Checklist de publication** (REQ-015) contresignée, premier scan de secrets
  de l'historique passé et propre.
- **Interface de chat optionnelle** (OpenWebUI, profil Docker Compose dédié) :
  la boucle y est entièrement automatique, l'utilisateur ne voit jamais un
  placeholder.

### Ce qui reste ouvert

Les limites connues sont suivies en
[issues publiques](https://github.com/comptoir-des-signaux/sas-confiance-ia/issues) :
corpus d'évaluation encore trop petit pour que les mesures soient
interprétables, authentification et topologies de déploiement non arbitrées,
pilotage de la politique depuis le proxy. La feuille de route détaillée et ses
écarts sont dans [`docs/specs/05-PLAN.md`](docs/specs/05-PLAN.md).

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

### Juge LLM local (identifiants indirects)

Troisième couche de détection, optionnelle par conception : un LLM local
(Ollama) relit le texte déjà pseudonymisé et signale pour revue humaine les
identifiants indirects que regex et NER manquent (« le chef du service
assainissement de la petite commune », surnoms, périphrases). Ses candidats
ne sont jamais remplacés automatiquement et reviennent sous forme de
positions (jamais d'extrait en clair dans la réponse en mode sérieux). Le
juge n'appelle jamais un service distant : l'hôte configuré doit se résoudre
en adresse locale ou privée, sinon le sas refuse de démarrer, et un test
réseau l'interdit aussi dans la suite.

```bash
SAS_JUGE_BASE_URL=http://localhost:11434/v1 \
SAS_JUGE_MODELE=mistral-small:24b \
python -m sas_confiance_ia
```

Sans ces variables, le sas fonctionne et se documente comme moins couvrant.
Couverture mesurée sur les canaris :
[docs/eval/evaluation-juge.md](docs/eval/evaluation-juge.md) (référence :
mistral-small:24b, 5/6 ; un modèle 4B n'en signale que 2/6).

### Politiques de remplacement par type

Chaque type d'entité détecté suit une politique (cadrage §9.5) :
`pseudonymiser` (défaut, réversible par le vault), `masquer` (marqueur
`[TYPE]` sans numéro, sans entrée vault, irréversible), `conserver` (choix
explicite, tracé en avertissement au démarrage) ou `revue` (pseudonymisé et
signalé pour relecture humaine dans `entites_en_revue`).

Défauts d'instance par variable d'environnement :

```bash
SAS_POLITIQUES="FR_SIREN=conserver,REFERENCE_DOSSIER=revue" python -m sas_confiance_ia
```

Chaque dossier peut surcharger ces défauts (champ `politiques` de
`/ui/pseudonymiser`) : la politique du dossier est stockée dans le vault et
survit au redémarrage, comme la séparation démo / sérieux. Une action ou un
type inconnu est refusé : une faute de frappe ne dégrade jamais la
couverture en silence.

**Surrogates réalistes (REQ-012).** Option par dossier : les personnes
reçoivent un nom factice Faker fr_FR cohérent en genre (« Camille Roussel »)
au lieu de `[PERSONNE_001]`, pour un texte naturel à soumettre au modèle.
La réversibilité passe toujours par le vault : le surrogate n'est qu'un
rendu, stable sur tout le dossier. Contrepartie assumée (arbitrage Q5,
`docs/specs/QUESTIONS.md`) : un surrogate que le LLM altère (« Mme
Roussel ») n'est ni restauré ni détecté, là où un placeholder altéré est
rattrapé par la lecture tolérante. Le mode placeholder reste le défaut.
Portée v1 : personnes uniquement.

### Fichiers : déposer, comparer, exporter

La page `/fichiers` accepte le glisser-déposer de documents `.txt`, `.md`,
`.csv`, `.docx` (paragraphes et tableaux) et `.pdf` textuels. Le texte
extrait s'affiche côte à côte avec le texte pseudonymisé, entités
surlignées : le surlignage se calcule dans le navigateur à partir des
positions (arbitrage Q3), le serveur ne renvoie jamais les valeurs en mode
sérieux. Exports : `.txt` pseudonymisé, et `.docx` reconstruit (mêmes
placeholders que l'analyse, propriétés du document source recopiées et
passées elles aussi à la détection).

Refus explicites : PDF scanné (pas d'OCR en v1 : pseudonymiser une image en
la laissant lisible serait un faux sentiment de sécurité) et formats non
supportés. Le nom du fichier déposé n'entre jamais au journal (il peut
contenir un nom de personne, REQ-003). Le PDF caviardé (PyMuPDF, licence
AGPL contaminante) est exclu de la v1 : arbitrage Q6,
[`docs/specs/QUESTIONS.md`](docs/specs/QUESTIONS.md).

**Dates différenciées (REQ-008).** La date de naissance (« née le 12 mai
1985 », « Date de naissance : 28/09/1986 ») est masquée par défaut. Les
dates procédurales (décision, séance, accident) sont détectées, comptées et
conservées par défaut : elles portent l'utilité métier du texte. La
politique du dossier peut les passer en `revue` (masquées et signalées pour
relecture) ou en `pseudonymiser` ; l'interface propose ce choix. Limites
documentées : une date sans année n'est pas reconnue, le tiret n'est pas un
séparateur admis (collision avec les matricules), et une date recouverte
par une entité plus sensible reste masquée avec elle.

## Contribuer et signaler

- **Contribuer** : [CONTRIBUTING.md](CONTRIBUTING.md) (esprit du projet,
  interdictions absolues, méthode TDD, licence des dépendances).
- **Signaler une faille ou une fuite** : [SECURITY.md](SECURITY.md).
  N'ouvrez jamais d'issue publique pour un chemin de fuite.
- **Règles de la communauté** : [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

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
