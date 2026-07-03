# Parcours formateur : animer un atelier avec le sas

Le sas a été conçu aussi comme un outil pédagogique : montrer concrètement,
à des agents territoriaux, ce qui part vers un modèle d'IA, ce qui n'y part
pas, et pourquoi « anonymisé » est un mot à manier avec précaution. Ce
parcours propose un déroulé d'atelier d'environ 1 h 30, éprouvé en
formation par Comptoir des Signaux, à adapter à votre public.

## Avant l'atelier

- Une instance du sas fonctionne sur la machine du formateur
  ([tutoriel d'installation](tutoriel-installation.md)) ; en salle sans
  GPU, un backend souverain distant fait l'affaire (le propos pédagogique
  ne change pas : la détection et le vault restent locaux).
- Le [corpus synthétique](../corpus/synthetique/) du dépôt est ouvert dans
  un éditeur : c'est votre matière. **Jamais de document réel en atelier**,
  même « anonymisé à la main » : c'est précisément le réflexe que l'atelier
  veut déconstruire.
- Vidéoprojection de deux fenêtres : l'interface du sas
  (`http://127.0.0.1:8787/`) et un terminal pour les journaux
  (`docker compose logs -f ollama`).

## Séquence 1 : le problème (15 min)

Question d'ouverture : « qui a déjà collé un extrait de courrier, de
délibération ou de dossier d'usager dans un chat d'IA ? ». Poser le cadre
sans culpabiliser : l'outil est utile, le réflexe est compréhensible, le
risque est réel (données personnelles chez un tiers, hors de tout cadre).

Montrer un texte du corpus synthétique : NIR, téléphone, email, nom,
référence de dossier. Faire lister par la salle ce qui identifie la
personne. Les identifiants indirects (fonction rare, petite commune)
émergent en général tout seuls : les noter pour la séquence 4.

## Séquence 2 : le sas en mode démonstration (25 min)

Basculer l'interface en **mode démonstration** (bandeau distinct : ce mode
affiche les correspondances, il n'est jamais mélangé aux dossiers
sérieux). Coller le texte, pseudonymiser, dérouler :

1. **Ce qui a été détecté** : types, comptes, surlignage. Faire remarquer
   la cohérence : « Jean Dupont » puis « M. Dupont » reçoivent le même
   pseudonyme (coréférence par dossier).
2. **Ce qui part réellement** : montrer le journal Ollama sur le deuxième
   écran : le modèle ne voit que `[PERSONNE_001]`, `[EMAIL_001]`. C'est le
   moment le plus convaincant de l'atelier : la preuve par le flux, pas la
   promesse d'une brochure.
3. **Le retour** : la réponse revient ré-identifiée en zone de confiance.
   Expliquer le vault : la table de correspondance qui ne quitte jamais la
   machine.

Faire manipuler : chaque participant (ou binôme) colle un texte du corpus,
compare détection et attentes. La page Fichiers (côte à côte surligné)
fonctionne bien pour ce temps de manipulation.

## Séquence 3 : ce que le sas ne promet pas (20 min)

C'est la séquence qui distingue une formation honnête d'une démonstration
commerciale. Trois messages :

1. **Aucun détecteur n'est parfait.** Montrer les mesures publiées
   ([évaluation NER](eval/evaluation-ner.md)) : le rappel n'est pas de
   100 %, et il est mesuré sur corpus synthétique.
2. **Pseudonymisation n'est pas anonymisation.** Le faisceau d'indices
   ré-identifie : « le maire de la commune de 200 habitants qui... » n'a
   pas besoin d'un nom. Reprendre les identifiants indirects listés en
   séquence 1.
3. **L'outil assiste, il ne remplace pas** : ni le DPO, ni l'AIPD, ni le
   registre des traitements. Le responsable de traitement reste
   responsable.

Si un juge LLM local est configuré, montrer ses signalements
d'identifiants indirects ([évaluation du juge](eval/evaluation-juge.md)) :
y compris ses manques (5 canaris sur 6 pour le modèle de référence), pour
illustrer la revue humaine.

## Séquence 4 : et chez vous ? (20 min)

Travail en groupes : chaque groupe prend un cas métier de sa collectivité
(sans données réelles : décrire le type de document, pas son contenu) et
répond à trois questions :

- Quels types de données personnelles ce flux contient-il ?
- Que gagnerait-on à le faire passer par un sas ? Qu'est-ce que le sas ne
  couvrirait pas ?
- Qui décide (DPO, DSI, métier) et que faut-il documenter ?

Restitution rapide. Conclure sur la gouvernance : le sas rend le flux
**vérifiable** (tests de non-fuite, journal sans donnée personnelle), ce
qui donne au DPO une prise concrète.

## Points de vigilance pour le formateur

- **Modes démo et sérieux** : la séparation est stricte par conception. Un
  dossier utilisé en démonstration est refusé en mode sérieux (REQ-007) ;
  ne « recyclez » pas vos dossiers d'atelier.
- **Vault en mémoire par défaut** : après un redémarrage de l'instance
  d'atelier, les pseudonymes émis avant ne sont plus ré-identifiables.
  C'est une bonne surprise pédagogique si elle est voulue, une mauvaise
  sinon.
- **Ne jurez que par la mesure** : si l'on vous demande « ça détecte
  tout ? », la seule réponse honnête est la page d'évaluation publiée.
- **Restez sur le corpus synthétique.** Si un participant veut essayer avec
  « un vrai exemple, juste pour voir » : c'est l'occasion de rappeler
  pourquoi non, et c'est le cœur du sujet de l'atelier.
