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

## Par où commencer

- **Installer le sas** : le [tutoriel pas à pas](tutoriel-installation.md)
  (Kubuntu / Docker, avec ou sans GPU).
- **L'exploiter** : le [guide de déploiement](deploiement.md) (cycle de vie
  du conteneur, vault persistant, backends souverains, politiques).
- **Former avec** : le [parcours formateur](parcours-formateur.md) (déroulé
  d'atelier d'1 h 30 sur corpus synthétique).
- **Contribuer** :
  [CONTRIBUTING](https://github.com/comptoir-des-signaux/sas-confiance-ia/blob/main/CONTRIBUTING.md).

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
Les documents de travail (consignes d'agents, arbitrages) restent lisibles
[dans le dépôt](https://github.com/comptoir-des-signaux/sas-confiance-ia/tree/main/docs/specs).
