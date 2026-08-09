# Politique de sécurité

Sas Confiance IA est un outil de réduction du risque de circulation des
données personnelles. Une faille dans un tel outil est plus grave qu'ailleurs :
elle transforme une garantie affichée en faux sentiment de sécurité. Ce
document dit comment nous prévenir, et ce que nous nous engageons à faire.

> *English: report vulnerabilities privately via GitHub's private vulnerability
> reporting, never through a public issue. Never include real personal data in
> a report: reproduce on the synthetic corpus.*

## Périmètre et maturité

**V1 locale, poste unique.** Le sas est conçu pour tourner dans une zone de
confiance, sur la boucle locale (`127.0.0.1:8787` par défaut). Il ne porte
**aucune authentification** : c'est un choix de périmètre assumé, pas un
oubli. Quiconque atteint le port du sas et connaît ou devine un identifiant de
dossier peut demander une ré-identification.

En conséquence :

- ne pas exposer le sas sur un réseau partagé ni sur Internet sans
  authentification frontale, filtrage réseau et cadrage DPO/RSSI ;
- protéger l'interface de chat optionnelle (OpenWebUI) par son propre
  mécanisme d'authentification ;
- traiter la clé de chiffrement du vault comme un secret d'exploitation
  (secret Docker ou coffre, jamais dans le dépôt, jamais dans une image).

L'absence d'authentification n'est donc **pas** une vulnérabilité à signaler :
elle est documentée ici et dans le README. Un moyen de contourner le périmètre
annoncé, lui, en est une.

## Ce qui constitue une vulnérabilité

Tout chemin par lequel :

1. une valeur détectée atteint le backend d'IA (violation de REQ-001) ;
2. une valeur détectée atteint les journaux (violation de REQ-003) ;
3. une valeur détectée ou la table de correspondance atteint une réponse d'API
   en mode sérieux (violations de REQ-007) ;
4. le vault au repos se lit en clair (violation de REQ-004) ;
5. un placeholder inconnu obtient une ré-identification au lieu d'un blocage
   (violation de REQ-006) ;
6. le mode démonstration s'active alors que des dossiers sérieux sont actifs ;
7. le juge LLM atteint un service distant malgré le contrôle d'adresse.

Les exigences sont décrites dans
[`docs/specs/03-SPEC.md`](docs/specs/03-SPEC.md).

Un cas non détecté par les couches de détection (faux négatif) n'est pas une
vulnérabilité : aucun détecteur n'atteint 100 % de rappel et cette limite est
publiée et mesurée. C'est en revanche une contribution très utile : ouvrez une
issue publique avec un exemple **synthétique**.

## Comment signaler

**Canal privé, dans cet ordre de préférence :**

1. **Signalement privé GitHub** (recommandé) : onglet *Security* du dépôt,
   *Report a vulnerability*. Le fil reste privé jusqu'à publication conjointe.
2. À défaut, écrivez à Comptoir des Signaux, coordonnées sur
   [comptoirdessignaux.com](https://www.comptoirdessignaux.com), en indiquant
   « Sas Confiance IA, signalement de sécurité » en objet.

**N'ouvrez jamais d'issue publique** pour un chemin de fuite.

## Ce que doit contenir un signalement

- la version ou le commit concerné ;
- la configuration (moteur NER, backend, politiques, vault mémoire ou chiffré) ;
- un cas reproductible **sur données synthétiques uniquement** ;
- l'exigence enfreinte si vous l'identifiez (REQ-001 à 016) ;
- l'impact tel que vous l'estimez.

**Aucune donnée personnelle réelle dans un signalement**, y compris en pièce
jointe, y compris tronquée. Le corpus de
[`corpus/synthetique/`](corpus/synthetique/) est fait pour cela : il porte des
valeurs à clés valides (NIR, SIRET, IBAN) qui n'appartiennent à personne. Un
signalement contenant des données réelles sera supprimé et vous sera renvoyé
pour reformulation.

## Ce que nous nous engageons à faire

- **Accusé de réception sous 5 jours ouvrés.**
- **Première qualification sous 15 jours ouvrés** : périmètre, exigence
  enfreinte, gravité.
- **Correction assortie de son test de non-régression.** Un correctif de
  sécurité n'est jamais fusionné sans le test qui échouait avant lui : c'est
  la règle du projet, y compris pour nous.
- **Publication de la faille une fois corrigée**, avec sa mesure d'impact.
  Un projet qui se vend sur l'honnêteté des limites publie aussi ses failles.
- **Crédit au rapporteur** dans les notes de version, sauf demande contraire.

Ce projet est un commun porté par une structure de petite taille : ces délais
sont un engagement de traitement, pas un contrat de service.

## Versions suivies

Le projet est en V1. Seule la branche `main` est suivie : il n'y a pas encore
de branche de maintenance ni de rétroportage.
