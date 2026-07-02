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
qu'aucun autre Dupont n'est connu du dossier.
