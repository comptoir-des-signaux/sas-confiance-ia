# Comment ce sas a été construit

Le code de ce projet est public, donc vérifiable. Les jugements qui l'ont
produit ne le sont pas : ils vivent dans la tête de celui qui les a rendus, ou
dans des fichiers que personne ne lit. Or c'est sur ces jugements que repose la
confiance qu'on demande à une collectivité d'accorder à un outil qui manipule
des données personnelles.

Cette page publie ces jugements : la règle qui a tranché, les tensions qu'il a
fallu arbitrer, ce que chaque décision a coûté, ce qui a été refusé, et ce qui
reste ouvert.

## La règle qui a tranché tout le reste

Une seule règle a servi de tribunal à toutes les ambiguïtés rencontrées
pendant l'implémentation : **en cas de doute, retenir l'interprétation la plus
protectrice pour les données, puis consigner le doute pour arbitrage** plutôt
que de le résoudre en silence.

Cette règle se lit dans le produit fini, à des endroits où elle coûte du
confort :

- la couche NER est **fail-closed** : si le moteur demandé n'est pas
  chargeable, le sas refuse de démarrer plutôt que de tourner avec une
  couverture réduite sans le dire ;
- un placeholder inconnu en retour du modèle **bloque** au lieu d'être ignoré ;
- une politique ou un type mal orthographié est **refusé** : une faute de
  frappe ne dégrade jamais la couverture en silence ;
- un PDF scanné est **refusé** plutôt que traité : pseudonymiser une image en
  la laissant lisible fabriquerait un faux sentiment de sécurité ;
- le mode démonstration **refuse de s'activer** si un dossier sérieux existe
  dans l'instance.

Chacun de ces comportements est un renoncement à de la souplesse. C'est le
prix de la règle, et il est assumé.

## Six tensions, six arbitrages

Les ambiguïtés rencontrées ont été consignées au fil de l'eau dans un registre
public, [`docs/specs/QUESTIONS.md`](https://github.com/comptoir-des-signaux/sas-confiance-ia/blob/main/docs/specs/QUESTIONS.md),
avec l'interprétation retenue, la date et le nom de celui qui a tranché. Cinq
des six sont arbitrées et signées par Pascal Chevallot ; la sixième reste
ouverte, et le registre le dit.

### Q1 : la coréférence contre l'aller-retour exact

REQ-011 exige que « Jean Dupont » et « M. Dupont » reçoivent le même
`[PERSONNE_001]`. REQ-002 exige que la ré-identification rende le texte
exactement tel qu'il était. Les deux ne peuvent pas tenir ensemble : un
placeholder n'a qu'une valeur de restitution.

**Arbitrage : la forme canonique est restaurée.** Tous les alias partagent le
placeholder, et le vault restitue la forme la plus complète connue du dossier.
REQ-002 est réinterprétée : exact au caractère près partout, à la forme
canonique près pour les mentions fusionnées.

**Ce que ça coûte.** Une pièce qui disait « M. Dupont » ressortira « Jean
Dupont ». Le sens est préservé, la lettre non. Sans coréférence, le caractère
près reste garanti partout. Toute fusion douteuse crée un placeholder distinct
et part en revue : le projet préfère deux entités là où il n'y en avait
qu'une, à une fusion hasardeuse de deux personnes réelles.

### Q2 : ré-identifier sans authentification

Les placeholders sont énumérables par construction. Quiconque atteint le port
du sas et connaît un identifiant de dossier peut donc faire restituer des
valeurs. Le cadrage excluait explicitement l'authentification des premières
phases.

**Interprétation retenue, et seule question encore ouverte du registre.** Le
périmètre est la zone de confiance mono-utilisateur : écoute sur la boucle
locale, identifiant de dossier non devinable généré par l'interface, chaque
ré-identification journalisée en métadonnées. Toute exposition au-delà est un
choix de déploiement, documenté comme hors périmètre.

**Ce que ça coûte.** Le sas ne se déploie pas en service partagé aujourd'hui,
et cette limite est affichée en tête de chaque page plutôt que dissimulée dans
une annexe. L'arbitrage est renvoyé à la phase suivante, avec les topologies
de déploiement.

### Q3 : afficher le document d'origine en mode sérieux

Le besoin pédagogique appelle un affichage côte à côte de l'original et du
texte pseudonymisé, entités surlignées. La règle du mode sérieux disait
« types, positions et comptes, jamais de valeur ».

**Arbitrage : côte à côte dans les deux modes.** Le document appartient à
l'utilisateur et se trouve déjà dans son navigateur : le montrer ne révèle
rien qu'il ne possède. La règle se précise au bon endroit : c'est la
**réponse du serveur** qui ne contient jamais les valeurs ni le vault, et le
surlignage se calcule côté client à partir des seules positions.

**Ce que ça coûte.** Rien sur le contrat d'API, qui est inchangé. En revanche,
la démonstration devient possible sans passer par le mode démo, ce qui rend
l'outil enseignable sur des documents que l'organisation possède déjà.

### Q4 : les identifiants à clé invalide

La détection déterministe appliquait « clé validée ou rien ». Excellente
précision. Puis un test sur un procès-verbal fictif de conseil médical a
montré le revers : **12 NIR, 11 SIRET et 2 IBAN à clés invalides traversaient
le sas en clair**. Une simple faute de frappe dans un vrai NIR aurait fui de
la même manière.

**Arbitrage : masquer en contexte.** Un motif structurel à clé invalide est
masqué dès qu'un mot de contexte le précède (« NIR », « sécurité sociale »,
« SIRET », « IBAN »), sous un type distinct suffixé `_SUSPECT` et à score
moindre, pour que le réviseur voie que la clé n'a pas validé. Trois
reconnaisseurs sont ajoutés : RPPS, matricule, code postal.

**Ce que ça coûte.** Du sur-masquage assumé, donc des faux positifs. Et une
limite qui reste : sans mot de contexte, un motif à clé invalide passe
toujours. Le juge LLM est la parade de troisième rang pour ces cas, pas une
garantie. Le procès-verbal est entré au corpus avec son oracle : ce cas précis
ne peut plus régresser sans faire échouer la suite.

### Q5 : les surrogates réalistes contre le contrôle d'intégrité

Remplacer `[PERSONNE_001]` par « Camille Roussel » donne au modèle un texte
naturel, mieux accordé en français. Mais si le modèle répond « Mme Roussel »,
rien ne distingue un surrogate altéré d'un nom qu'il aurait inventé : la
ré-identification échoue sans qu'aucun blocage soit possible.

**Arbitrage : assumer et documenter.** Le surrogate devient une simple couche
de rendu. Le vault et la coréférence continuent de raisonner en
`[PERSONNE_NNN]`, compteurs et forme canonique intacts. Le mode surrogate est
une option par dossier, jamais un défaut d'instance.

**Ce que ça coûte.** Un surrogate altéré par le modèle n'est ni restauré ni
détecté : la mention reste factice dans la réponse. C'est une perte réelle par
rapport au mode placeholder, qui est resté le défaut pour cette raison. La
portée est limitée aux personnes.

### Q6 : le PDF caviardé et les métadonnées d'export

Le caviardage PDF façon rectangles noirs exige PyMuPDF, sous licence AGPL.
Cette licence est compatible EUPL-1.2 selon la matrice européenne, mais elle
est contaminante pour quiconque redéploie un sas modifié.

**Arbitrage : PDF caviardé exclu de la v1.** Le commun reste entièrement
MIT, BSD et EUPL, sans clause contaminante à expliquer à une DSI. Les exports
`.txt` et `.docx` couvrent le besoin. Second point tranché : les métadonnées
d'un `.docx` exporté sont recopiées du document source, car elles
appartiennent à l'utilisateur, mais elles passent **elles aussi** à la
détection. Un nom en propriété « auteur » ne doit pas fuir par la bande.

**Ce que ça coûte.** Pas de caviardage PDF, et un paragraphe modifié perd sa
mise en forme fine. Une fonctionnalité visible a été échangée contre une
licence simple à expliquer.

## Ce qui a été refusé

Un projet se définit autant par ce qu'il écarte. Outre PyMuPDF :

- **Le streaming.** Un placeholder coupé entre deux morceaux rend la
  ré-identification et le contrôle d'intégrité non fiables. La réponse est
  bufferisée puis rendue complète, et la conversion est journalisée.
- **L'OCR.** Traiter une image reviendrait à produire un document qui a l'air
  pseudonymisé et ne l'est pas.
- **L'authentification.** Hors périmètre déclaré. Un jeton ajouté dans
  l'urgence donnerait une assurance que le reste de l'architecture ne
  soutiendrait pas.
- **Le vault rendu au client.** Prévu au cadrage, jamais livré : cela
  déplacerait la responsabilité de sa conservation vers un poste dont le sas
  ne sait rien. La décision est marquée comme non implémentée plutôt que
  laissée en promesse.
- **Presidio en conteneurs séparés.** Utilisé comme bibliothèque dans le
  processus : moins de surface réseau interne, plus simple à auditer.

## Comment on prouve, au lieu d'affirmer

L'affirmation « le modèle ne voit pas vos données » ne vaut rien sans moyen de
la contredire. Le projet s'en est donné un.

**Le faux backend de capture** est le mécanisme central. Pendant les tests, le
sas ne parle pas à un vrai modèle : il parle à un faux backend qui enregistre
le contenu HTTP exact qu'il reçoit. Le corpus synthétique est accompagné d'un
oracle, la liste des valeurs sensibles qu'il contient. La suite de tests
compare l'un à l'autre et **échoue** si une seule de ces valeurs apparaît dans
ce qui est parti. La garantie n'est donc pas une intention de conception :
c'est une condition de passage de la CI.

Trois garde-fous complètent le dispositif :

- un test **interdit activement tout appel réseau** pendant la suite, ce qui
  rend impossible une fuite masquée par un service externe ;
- le corpus est **entièrement synthétique**, à clés valides mais
  n'appartenant à personne ;
- les modèles sont **épinglés par révision exacte**, pour qu'une mesure
  publiée reste reproductible.

La suite compte aujourd'hui 299 tests, dont 14 ne s'exécutent qu'avec le
modèle NER installé. Dix exigences numérotées, REQ-001 à REQ-010, portent
chacune leur test clé ; elles sont listées dans
[la SPEC](specs/03-SPEC.md).

## Ce qui est mesuré, et ce que valent les mesures

Les mesures sont publiées telles quelles, y compris quand elles sont mauvaises
ou quand elles ne veulent rien dire.

| Type | Rappel | Précision | Mentions |
|---|---|---|---|
| PERSONNE | 95,8 % | 92,3 % | 23 sur 24 |
| ORGANISATION | 100,0 % | 25,0 % | 1 sur 1 |
| LIEU | 82,6 % | 100,0 % | 19 sur 23 |

La ligne ORGANISATION est un bon exemple de ce que le projet refuse de faire.
Un rappel de 100 % sur **une seule mention** ne démontre rien, et une
précision de 25 % sur quatre détections non plus. Le chiffre est publié avec
sa fragilité écrite à côté, plutôt que mis en avant sans son dénominateur ou
retiré du tableau. Étoffer ce corpus est le premier chantier de mesure.

Le juge LLM est évalué sur six identifiants indirects fictifs. Avec
`mistral-small:24b` il en signale 5 sur 6 ; avec un modèle de 4 milliards de
paramètres, 2 sur 6. Un canari, un prédécesseur muté, échappe aux deux. La
conclusion publiée est donc double : le juge n'est utile qu'au-delà d'une
certaine taille de modèle, et il ne remplace en aucun cas la revue humaine.

Détail : une **porte de qualité** interdit toute régression de rappel de plus
de deux points par rapport à une base de référence versionnée. Une amélioration
qui dégraderait la couverture échouerait en CI.

Le détail des protocoles est dans
[l'évaluation de la détection](eval/evaluation-ner.md) et
[l'évaluation du juge](eval/evaluation-juge.md).

## Comment ce code a été écrit

Une part importante de ce sas a été écrite par des agents de code, sous
contraintes explicites, publiées dans
[`AGENTS.md`](https://github.com/comptoir-des-signaux/sas-confiance-ia/blob/main/AGENTS.md) :
développement piloté par les tests, commits atomiques, aucune fonctionnalité
non demandée même « pour préparer la suite », interdiction absolue d'affaiblir
un test d'invariant pour le faire passer, et obligation de s'arrêter et de
signaler plutôt que de trancher seul une ambiguïté de spécification. Le
registre d'arbitrages cité plus haut est la trace de cette dernière règle.

Ces contraintes sont publiées pour la même raison que le reste : elles font
partie de ce qu'on peut vérifier. Elles ne constituent pas pour autant un
argument d'autorité. Ce qui garantit le comportement du sas, ce n'est pas la
méthode qui a produit son code, ce sont les tests qui l'encadrent et les
mesures qui le décrivent. La méthode explique comment on en est arrivé là ;
elle ne prouve rien à elle seule.

## Ce qui reste ouvert

- **Le corpus d'évaluation est trop petit**, en particulier pour les
  organisations et les lieux complexes. C'est la limite la plus contraignante
  du projet aujourd'hui.
- **L'authentification et le déploiement mutualisé** ne sont pas arbitrés
  (Q2). Tant qu'ils ne le sont pas, le périmètre reste la zone de confiance
  locale.
- **Le pilotage de la politique depuis le proxy** est identifié et documenté,
  avec la règle qui devra l'encadrer : un en-tête pourra durcir le traitement,
  jamais le desserrer.
- **L'OCR et le caviardage PDF** restent hors périmètre.

Ces chantiers sont suivis dans les
[issues publiques](https://github.com/comptoir-des-signaux/sas-confiance-ia/issues)
du dépôt.

## Pour aller plus loin

Le cadrage complet est public : [PRD](specs/01-PRD.md) pour le produit,
[AI-SPEC](specs/02-AI-SPEC.md) pour les modes de défaillance du système IA et
leurs parades, [SPEC](specs/03-SPEC.md) pour les exigences falsifiables,
[ADR](specs/04-ADR.md) pour les décisions d'architecture et
[PLAN](specs/05-PLAN.md) pour la feuille de route et ses écarts.
