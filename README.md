# Sas Confiance IA

**Le sas de pseudonymisation avant IA** : détectez les données personnelles
françaises dans vos textes, remplacez-les par des pseudonymes, envoyez le texte
protégé à un modèle de langage, puis ré-identifiez la réponse **en zone de
confiance**. La table de correspondance ne quitte jamais votre infrastructure.

Un commun numérique porté par [Comptoir des Signaux](https://www.comptoirdessignaux.com),
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

**Phase 1 livrée** : plus de 200 tests automatisés
prouvent les invariants de sécurité sur faux backend de capture : non-fuite
des valeurs détectées, désormais au périmètre complet noms / lieux /
organisations inclus (REQ-001), ré-identification exacte (REQ-002), journaux
sans donnée personnelle (REQ-003), vault chiffré au repos (REQ-004),
compteurs persistants (REQ-005), placeholders inconnus bloquants (REQ-006),
streaming converti en non-streaming journalisé (REQ-010). La détection s'appuie sur le NER français
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
des dossiers sérieux sont actifs dans l'instance. Phase 1 complète.
**Phase 2 en cours (lots 13 à 15 livrés)** : un juge LLM local
optionnel (REQ-014) relit le texte déjà pseudonymisé et signale les
identifiants indirects (fonction rare, petite commune, surnom, périphrase)
pour revue humaine, jamais en remplacement automatique ; couverture
[mesurée et publiée sur les canaris](docs/eval/evaluation-juge.md). Chaque
type d'entité suit désormais une politique configurable par dossier
(pseudonymiser, masquer sans coffre, conserver, revue : cadrage §9.5), la
date de naissance est distinguée des dates procédurales (REQ-008) et les
personnes peuvent recevoir des surrogates réalistes cohérents en genre,
réversibles par le vault (REQ-012, arbitrage Q5). La page Fichiers accepte
le glisser-déposer (.txt, .md, .csv, .docx, .pdf textuel), affiche le
document et sa version pseudonymisée côte à côte avec surlignage, et
exporte en .txt ou .docx reconstruit.
**Lot 16 (publication du commun)** : site de documentation MkDocs Material
publié par GitHub Pages ([tutoriel d'installation](docs/tutoriel-installation.md),
[parcours formateur](docs/parcours-formateur.md), cadrage rendu public par
transparence), [CONTRIBUTING](CONTRIBUTING.md),
[checklist de publication](docs/checklist-publication.md) (REQ-015) avec
premier scan de secrets de l'historique passé et propre. Une interface de
chat optionnelle (OpenWebUI, profil Docker Compose dédié) se branche sur le
sas : la boucle y est entièrement automatique (pseudonymisation à l'aller,
ré-identification au retour, l'utilisateur ne voit jamais un placeholder).
La « preuve par le flux » est documentée et testée : demander au modèle de
réciter sa question avec `X-Reidentify-Response: false`, sa réponse brute
ne contient que des placeholders. L'interface du sas se lit en deux
colonnes, à la manière du viewport d'amo-presidio (aller : original puis
pseudonymisé ; retour : réponse de l'IA puis ré-identifié). Reste :
contresigner la checklist et activer GitHub Pages (Settings > Pages >
Source : GitHub Actions).

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
