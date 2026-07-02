# QUESTIONS : ambiguïtés de spec et arbitrages

Registre prévu par le 06-HANDOFF : toute ambiguïté rencontrée pendant
l'implémentation est consignée ici avec l'interprétation retenue (la plus
protectrice pour les données) et son statut d'arbitrage.

## Q1 : REQ-011 contre REQ-002 (coréférence contre aller-retour exact)

**Constat (2026-07-02, Lot 11).** REQ-011 exige que toutes les mentions d'une
même personne (« Jean Dupont », « M. Dupont ») reçoivent le même
`[PERSONNE_001]`. Un placeholder n'ayant qu'une seule valeur de restitution
dans le vault, la ré-identification restitue nécessairement une forme unique :
l'aller-retour exact au caractère près (REQ-002) ne peut pas tenir sur les
mentions fusionnées.

**Arbitrage (Pascal Chevallot, 2026-07-02) : canonique restaurée.**

- Tous les alias d'une personne partagent le même placeholder (REQ-011 tenu
  tel qu'écrit) ; le vault restitue la **forme canonique**, c'est-à-dire la
  forme la plus complète connue du dossier (« Jean Dupont », même là où la
  pièce disait « M. Dupont »).
- REQ-002 s'interprète désormais ainsi : aller-retour exact au caractère près
  pour toutes les entités, **à la forme canonique près pour les alias
  fusionnés par la coréférence**. Sans coréférence (option désactivée), le
  caractère près reste garanti partout.
- La fusion n'opère que sur des règles sûres ; toute ambiguïté (deux
  homonymes partiels possibles) crée un placeholder distinct et est signalée
  pour revue (F4 : jamais de fusion hasardeuse).

**Limite documentée.** Deux personnes distinctes partageant un nom de famille
ne sont jamais fusionnées sur le nom seul dès que l'ambiguïté existe ; en
contrepartie, une mention « M. Dupont » antérieure à toute mention complète
crée sa propre entité, rattachée ensuite si « Jean Dupont » apparaît et
qu'aucun autre Dupont n'est connu du dossier. Les civilités de genres
contradictoires (« M. Dupont » / « Mme Dupont ») ne fusionnent jamais ; en
revanche, sans base de prénoms genrés, « Mme Dupont » se rattache à un
« Jean Dupont » connu si aucune civilité masculine n'a été vue : risque
résiduel F4 assumé et documenté. Une liaison sur forme réduite reste stable
mais repasse en revue dès qu'un homonyme apparaît dans le dossier.

## Q2 : ré-identification sans authentification (périmètre v1)

**Constat (2026-07-02, Lot 12).** `/ui/reidentifier` (et le proxy avec
`X-Dossier-Id`) permettent à quiconque atteint le port du sas de faire
restituer les valeurs d'un dossier : les placeholders sont énumérables par
construction. Le HANDOFF exclut explicitement l'authentification des
Phases 0-1.

**Interprétation retenue (à arbitrer pour la Phase 2).** Le périmètre v1 est
la **zone de confiance mono-utilisateur** : écoute sur la boucle locale par
défaut, identifiant de dossier non devinable généré par l'UI, chaque
ré-identification UI journalisée (métadonnées seules). Toute exposition
au-delà de la boucle locale est un choix explicite de déploiement, documenté
comme hors périmètre v1. L'authentification (jeton par dossier ou frontal)
est un chantier de Phase 2 à arbitrer avec les topologies T2-T4.

## Q3 : afficher le texte d'origine en mode sérieux (côte à côte pédagogique)

**Constat (2026-07-02, préparation Phase 2).** L'interface de référence
(rbochet/amo-presidio) et le besoin pédagogique des ateliers appellent un
affichage côte à côte du texte d'origine et du texte pseudonymisé, avec
mise en évidence des entités détectées. Or la règle du mode sérieux (Lot 12)
était « types, positions, scores et comptes, jamais de valeur ».

**Arbitrage (Pascal Chevallot, 2026-07-02) : côte à côte dans les deux modes.**

- Le document affiché appartient à l'utilisateur et reste dans sa boucle
  locale : le montrer à côté du texte pseudonymisé, entités surlignées, ne
  révèle rien qu'il ne possède déjà. L'affichage est admis en mode sérieux
  comme en mode démo.
- La règle du mode sérieux se précise ainsi : la **réponse du serveur** ne
  contient jamais les valeurs détectées ni le vault ; le surlignage se
  calcule **côté client** à partir des positions (début/fin) déjà exposées,
  sur le texte que le navigateur détient. Le contrat d'API du mode sérieux
  est inchangé.
- Pour les fichiers (Lot 15), le texte extrait par le serveur revient au
  navigateur : c'est le document de l'utilisateur, pas une valeur du vault.
  Le journal reste en métadonnées seules (REQ-003).
