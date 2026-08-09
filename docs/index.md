# Sas Confiance IA

**Le sas de pseudonymisation avant IA** : détectez les données personnelles
françaises dans vos textes, remplacez-les par des pseudonymes, envoyez le
texte protégé à un modèle de langage, puis ré-identifiez la réponse en zone
de confiance. La table de correspondance ne quitte jamais votre
infrastructure.

Un commun numérique porté par
[Comptoir des Signaux](https://www.comptoirdessignaux.com), conçu pour les
collectivités territoriales et la fonction publique, sous licence
[EUPL-1.2](https://github.com/comptoir-des-signaux/sas-confiance-ia/blob/main/LICENSE).

> *English summary: a French-first pseudonymization gateway for LLM usage.
> Detects French personal data (NIR, SIRET, IBAN, names...), substitutes
> reversible placeholders, proxies OpenAI-compatible requests, re-identifies
> responses locally. The mapping vault never leaves your trust zone.*

!!! warning "Maturité : V1 locale, poste unique"

    Le sas tourne dans votre zone de confiance, sur la boucle locale
    (`127.0.0.1`). Il ne porte **aucune authentification** : quiconque atteint
    son port et connaît un identifiant de dossier peut ré-identifier. C'est un
    périmètre assumé, pas un oubli.

    **Usages visés aujourd'hui** : poste de travail, atelier, formation,
    expérimentation contrôlée sur corpus synthétique.

    **À ne pas faire encore** : exposer le sas sur un réseau partagé ou sur
    Internet sans authentification frontale et filtrage ; traiter de vrais
    documents sans cadrage préalable (base légale, information des personnes,
    registre, AIPD si nécessaire, validation DPO et RSSI, tests sur un corpus
    représentatif de votre organisation).

## Le flux : ce qui reste, ce qui sort

![Schéma du flux : dans la zone de confiance, le poste de travail envoie un
document au sas, qui détecte les données personnelles, les remplace par des
pseudonymes et conserve la table de correspondance dans son vault. Seul le
texte pseudonymisé franchit la limite de la zone de confiance vers le backend
d'IA. La réponse revient pseudonymisée, puis le sas la ré-identifie localement.
Le journal ne contient que des métadonnées.](assets/schema-flux.svg)

## La preuve par le flux

L'argument du sas n'est pas « nous pseudonymisons ». C'est « vous pouvez le
vérifier ». Demandez au modèle de recopier votre question, ré-identification
désactivée : sa réponse brute montre exactement ce qu'il a reçu.

| Étape | Contenu |
|---|---|
| Ce que vous saisissez | `quel dossier suit Marie Martin (marie.martin@exemple.fr) ?` |
| Ce que le modèle reçoit | `quel dossier suit [PERSONNE_001] ([EMAIL_001]) ?` |
| Ce que le modèle renvoie | `quel dossier suit [PERSONNE_001] ([EMAIL_001]) ?` |
| Ce que vous recevez | `quel dossier suit Marie Martin (marie.martin@exemple.fr) ?` |

Le modèle n'a jamais vu les valeurs : il ne peut restituer que ce qu'il a
reçu. Cette propriété n'est pas déclarative, elle est tenue par des tests. Un
faux backend capture le payload HTTP réellement émis, et la suite échoue si
une valeur sensible connue y figure. La commande complète est dans le
[tutoriel d'installation](tutoriel-installation.md#5-premiere-pseudonymisation).

## À qui s'adresse ce sas

**Vous êtes DSI, RSSI ou chef de projet numérique.** Vous voulez savoir ce qui
sort réellement de votre réseau, comment le sas se déploie et où vit la clé du
vault. Commencez par le [guide de déploiement](deploiement.md) : cycle de vie
du conteneur, vault persistant, backends souverains, politiques par type
d'entité.

**Vous êtes DPO, juriste ou délégué à la protection des données.** Vous voulez
savoir ce que l'outil réduit, ce qu'il ne réduit pas, et ce qui reste à votre
charge. Lisez [ce que le sas garantit](#ce-que-le-sas-garantit-et-ne-garantit-pas)
plus bas, puis les mesures publiées :
[détection](eval/evaluation-ner.md) et [juge LLM](eval/evaluation-juge.md).
Le sas ne remplace ni le registre, ni l'AIPD, ni votre analyse.

**Vous formez, accompagnez ou animez.** Vous cherchez un support concret pour
montrer à des agents ce que devient un document envoyé à une IA. Le
[parcours formateur](parcours-formateur.md) est un déroulé d'atelier d'1 h 30
sur corpus 100 % synthétique.

**Ce que le sas n'est pas.** Ce n'est pas une plateforme multi-utilisateurs
prête à l'emploi : il n'y a ni comptes, ni authentification, ni cloisonnement
entre utilisateurs, ni service hébergé. Ce n'est pas non plus une offre avec
engagement de support : c'est un commun, maintenu comme tel. Ce qu'il est : un
démonstrateur vérifiable, un support de formation et une base de discussion
entre DSI, DPO et RSSI.

## Trois parcours

**1. Comprendre en 3 minutes.** Cette page, le tableau de la preuve par le
flux ci-dessus, et les [mesures publiées](eval/evaluation-ner.md). Vous saurez
ce que le sas fait, ce qu'il ne fait pas, et à quel niveau de rappel.

**2. Essayer en 30 minutes.** Le [tutoriel d'installation](tutoriel-installation.md)
(Kubuntu ou Docker, avec ou sans GPU), puis une première pseudonymisation sur
le [corpus synthétique](https://github.com/comptoir-des-signaux/sas-confiance-ia/tree/main/corpus/synthetique).
N'utilisez jamais un document réel pour vos essais.

**3. Auditer et contribuer.** Le cadrage complet est public (voir plus bas),
les exigences sont falsifiables, les tests sont dans le dépôt. Pour proposer
un cas de détection manqué ou une évolution :
[CONTRIBUTING](https://github.com/comptoir-des-signaux/sas-confiance-ia/blob/main/CONTRIBUTING.md).
Pour signaler une fuite, jamais d'issue publique :
[SECURITY](https://github.com/comptoir-des-signaux/sas-confiance-ia/blob/main/SECURITY.md).

## Ce que le sas garantit (et ne garantit pas)

Le sas **réduit** les données personnelles transmises aux modèles d'IA et
rend ces flux **vérifiables** : des tests capturent le payload réellement
envoyé et échouent si une valeur sensible connue y figure.

Le sas **ne garantit pas** une anonymisation parfaite ni une conformité
RGPD automatique : aucun détecteur n'atteint 100 % de rappel, la
ré-identification par faisceau d'indices reste possible, et l'outil assiste
le responsable de traitement sans remplacer le DPO, l'AIPD ni le registre.
Ces limites sont documentées et **mesurées** :
[évaluation de la détection](eval/evaluation-ner.md),
[évaluation du juge LLM](eval/evaluation-juge.md).

## Transparence du cadrage

Tout le cadrage du projet est public : produit
([PRD](specs/01-PRD.md)), risques et parades IA
([AI-SPEC](specs/02-AI-SPEC.md)), exigences falsifiables
([SPEC](specs/03-SPEC.md)), décisions d'architecture
([ADR](specs/04-ADR.md)) et feuille de route ([PLAN](specs/05-PLAN.md)).

Ces documents portent aussi leurs écarts : quand ce qui a été livré diffère de
ce qui avait été prévu, l'écart est signalé là où il se trouve plutôt que
gommé. Les documents de travail (consignes de reprise, arbitrages en cours)
restent lisibles
[dans le dépôt](https://github.com/comptoir-des-signaux/sas-confiance-ia/tree/main/docs/specs).
