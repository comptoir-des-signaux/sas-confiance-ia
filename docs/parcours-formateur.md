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
- Le [corpus synthétique](https://github.com/comptoir-des-signaux/sas-confiance-ia/tree/main/corpus/synthetique)
  du dépôt est ouvert dans
  un éditeur : c'est votre matière. **Jamais de document réel en atelier**,
  même « anonymisé à la main » : c'est précisément le réflexe que l'atelier
  veut déconstruire.
- Vidéoprojection de deux fenêtres : l'interface du sas
  (`http://127.0.0.1:8787/`) et un terminal avec la commande « preuve par
  le flux » prête à lancer (l'écho ci-dessous, séquence 2). Inutile de
  projeter les journaux d'Ollama : ils ne montrent jamais le contenu des
  prompts, seulement leur provenance.

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
2. **Ce qui part réellement** : la zone 2 de l'interface montre le texte
   qui part vers le modèle. Puis le moment le plus convaincant de
   l'atelier, la preuve par le flux : demander au modèle **de réciter
   lui-même sa question**, ré-identification désactivée. Sa réponse brute
   ne contient que des placeholders : il n'a jamais vu les valeurs, et
   c'est lui qui en témoigne, pas une brochure.

    ```bash
    curl -s -X POST http://127.0.0.1:8787/v1/chat/completions \
      -H "Content-Type: application/json" -H "X-Dossier-Id: atelier-echo" \
      -H "X-Reidentify-Response: false" \
      -d '{"model": "mistral-small:24b", "messages": [{"role": "user",
           "content": "Recopie exactement ma question entre guillemets : quel dossier suit Marie Martin (marie.martin@exemple.fr, 06 12 34 56 78) ?"}]}'
    # → "quel dossier suit [PERSONNE_001] ([EMAIL_001], [TELEPHONE_001]) ?"
    ```
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

## Les deux questions qui reviennent à chaque atelier

### « Avec une interface de chat branchée sur le sas, dois-je copier-coller pour ré-identifier ? »

Non. Quand l'interface de chat (OpenWebUI par exemple) est branchée sur le
sas, **toute la boucle est automatique et invisible** : le participant tape
son texte brut, le sas pseudonymise au passage, le modèle ne voit que des
pseudonymes, et le sas ré-identifie la réponse au retour. Ce qui s'affiche
dans le chat contient déjà les vraies valeurs. Un seul onglet, zéro
copier-coller. La règle à faire retenir :

- **IA branchée sur le sas** : tout est automatique.
- **IA ailleurs** (chat en ligne non relié au sas) : on passe par la page
  du sas à la main : pseudonymiser (étapes 1 et 2), coller dans l'IA,
  rapporter sa réponse (étapes 3 et 4).

Piège classique (vécu, donc à montrer) : coller un texte **déjà
pseudonymisé** dans le chat branché sur le sas. Les placeholders viennent
d'un autre dossier : le sas, qui ne les connaît pas, refuse par prudence de
ré-identifier la réponse (un placeholder inconnu est bloquant, REQ-006), et
la réponse s'affiche avec ses placeholders. C'est un garde-fou, pas une
panne : la ré-identification se fait alors sur la page du sas, avec le
dossier d'origine. De même, si le modèle abîme un placeholder au point de
créer un doute, la ré-identification automatique se bloque et la réponse
arrive pseudonymisée : la page du sas sert de rattrapage après relecture.

### « À quoi servent les noms factices (surrogates) ? »

Quand le sas trouve « Camille Durand », il a deux masques possibles : le
placeholder `[PERSONNE_001]` (défaut, jeton robotique impossible à
confondre avec du vrai texte) ou le surrogate « Camille Roussel » (faux nom
inventé, cohérent en genre, qui laisse un texte naturel). Dans les deux cas
le vault sait ce qui se cache derrière et la ré-identification restitue le
vrai nom.

L'intérêt du surrogate : un modèle rédige mieux sur « Camille Roussel a
rencontré Paul Berger » que sur « [PERSONNE_001] a rencontré
[PERSONNE_002] », et il n'abîme pas un nom comme il abîme un jeton. La
contrepartie (affichée « intégrité réduite » dans l'interface) : si le
modèle écrit « Mme Roussel », le sas ne peut pas le rattraper, ce bout de
texte garde le faux nom ; un placeholder altéré, lui, reste reconnaissable
et se rattrape. Ce n'est jamais une fuite (le nom est inventé), c'est une
ré-identification incomplète. Message d'atelier : placeholders par défaut,
surrogates quand la qualité rédactionnelle prime.

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
