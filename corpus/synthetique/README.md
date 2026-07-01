# Corpus synthétique : Sas Confiance IA

**Toutes les données de ce corpus sont fictives** (REQ-009) : personnes,
adresses, organisations, situations. Toute ressemblance avec des personnes ou
organismes existants serait fortuite. Les identifiants (NIR, SIREN, SIRET,
IBAN) sont générés avec des **clés de contrôle valides** afin d'exercer les
validateurs, mais ne correspondent à aucune personne ni entité réelle.

## Contenu

| Fichier | Scénario | Exerce |
|---|---|---|
| `01-courrier-usager.md` | Courrier d'une usagère à sa mairie | Nom, NIR, date de naissance, adresse, email, téléphone, numéro de dossier |
| `02-note-rh.md` | Note RH disciplinaire fictive | Noms, date de naissance, matricule, fonction, petite commune |
| `03-contrat-prestation.md` | Contrat de prestation | SIREN, SIRET, IBAN, gérant, montants |
| `04-dossier-usager/` | Dossier multi-pièces (3 pièces) | Coréférence inter-documents (REQ-011) : « Jean Dupont », « M. Dupont », « le requérant » |
| `05-compte-rendu-reunion.md` | Compte rendu de conseil municipal | Élus, fonctions, dates procédurales vs personnelles (REQ-008) |
| `06-canaris.md` | Identifiants indirects | Éval du juge LLM (02-AI-SPEC §4.3) : rien n'y est détectable par regex ni NER classique |
| `valeurs-connues.json` | Oracle de non-fuite | REQ-001 et REQ-003 : aucune de ces valeurs ne doit apparaître dans un payload sortant ni dans un log |

## Usage dans les tests

1. **Non-fuite (REQ-001)** : après pseudonymisation et envoi au faux backend,
   aucune valeur de `valeurs-connues.json` ne figure dans le payload capturé.
2. **Logs propres (REQ-003)** : aucune de ces valeurs dans les journaux.
3. **Aller-retour (REQ-002)** : la ré-identification restitue exactement le
   document d'origine.
4. **Cohérence de l'oracle** : un test vérifie que chaque valeur déclarée est
   bien présente verbatim dans son document source.
