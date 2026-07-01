# 03-SPEC : exigences falsifiables

**Statut :** v0.1 du 2026-07-01. Chaque exigence suit le format
Current / Target / Acceptance. Les REQ-001 à 010 reprennent le cadrage initial ;
les REQ-011 et suivantes ajoutent les arbitrages du 2026-07-01.

---

## Invariants de sécurité (Phase 0)

### REQ-001 : absence de fuite vers le backend IA
- **Current :** aucun mécanisme vérifié ne garantit l'absence de données brutes
  dans le payload sortant.
- **Target :** toute valeur détectée dans le corpus synthétique est absente du
  JSON réellement envoyé au backend.
- **Acceptance :** un faux backend capture la requête HTTP finale ; les tests
  échouent si une valeur brute connue du corpus y apparaît.

### REQ-002 : ré-identification exacte
- **Current :** substitutions non garanties réversibles.
- **Target :** tout placeholder créé en mode réversible possède une
  correspondance unique dans le vault.
- **Acceptance :** `reidentifier(pseudonymiser(texte)) == texte` sur tout le
  corpus de test couvert.

### REQ-003 : journal sans DCP
- **Current :** les logs peuvent contenir prompts, réponses ou valeurs.
- **Target :** journaux limités aux métadonnées techniques (horodatage, id de
  requête, dossier_id, backend, modèle, compte d'entités par type, statut).
- **Acceptance :** tests automatiques cherchant chaque valeur synthétique du
  corpus dans les logs produits : zéro occurrence.

### REQ-004 : vault chiffré au repos
- **Current :** correspondance potentiellement stockée en clair.
- **Target :** vault chiffré au repos en mode sérieux, clé via keyring ou
  gestionnaire de secrets, jamais en dur ni en variable committée.
- **Acceptance :** inspection binaire du fichier vault : aucune valeur brute en
  clair.

### REQ-005 : compteurs persistants
- **Current :** risque de collision de placeholders après redémarrage.
- **Target :** compteurs persistants par dossier et par type.
- **Acceptance :** test de redémarrage simulé : aucun placeholder existant
  réattribué ; deux dossiers distincts ont des mappings isolés.

### REQ-006 : placeholders inconnus bloquants
- **Current :** une réponse IA peut contenir un placeholder inventé.
- **Target :** tout placeholder inconnu ou manquant déclenche une anomalie
  (blocage ou revue requise), jamais une réponse finale silencieuse.
- **Acceptance :** test avec `[PERSONNE_999]` absent du vault : réponse marquée
  `review_required` ou bloquée, avec rapport d'intégrité.

### REQ-007 : séparation démo / sérieux
- **Current :** un prototype peut exposer le vault (cas amo-presidio).
- **Target :** le mode sérieux ne retourne jamais le vault ni les valeurs
  détectées en clair ; `/analyze` sérieux retourne types, positions et scores
  uniquement.
- **Acceptance :** tests API : aucune réponse en mode sérieux ne contient une
  valeur du vault.

### REQ-008 : politique de dates différenciée
- **Current :** toutes les dates masquées indistinctement.
- **Target :** date de naissance masquée par défaut ; dates procédurales
  conservées ou marquées pour revue selon la politique du dossier.
- **Acceptance :** corpus mêlant date de naissance et date de décision : la
  première est remplacée, la seconde suit la règle configurée.

### REQ-009 : aucune donnée réelle en phase 0
- **Current :** risque d'exemples réels dans les tests.
- **Target :** corpus 100 % synthétique, documenté comme tel.
- **Acceptance :** revue du corpus : aucun fichier issu de données client ou
  personnelles réelles.

### REQ-010 : pas de streaming v1
- **Current :** le streaming coupe les placeholders entre chunks.
- **Target :** streaming désactivé.
- **Acceptance :** toute requête `stream=true` est refusée (HTTP 400 explicite)
  ou convertie en `stream=false` avec journalisation.

## Exigences produit (arbitrées le 2026-07-01)

### REQ-011 : cohérence de coréférence par dossier
- **Current :** Presidio traite chaque mention isolément ; « M. Dupont » et
  « Jean Dupont » reçoivent des placeholders différents.
- **Target :** au sein d'un dossier, les mentions d'une même entité (nom
  complet, nom seul, civilité + nom, alias déjà vus) reçoivent le même
  placeholder, y compris entre plusieurs pièces traitées successivement.
- **Acceptance :** corpus multi-pièces synthétique : « Jean Dupont » (pièce 1)
  et « M. Dupont » (pièce 2) → même `[PERSONNE_001]` ; deux homonymes partiels
  distincts documentés comme limite.

### REQ-012 : politique de substitution configurable
- **Current :** un seul style de remplacement.
- **Target :** placeholders typés `[PERSONNE_001]` par défaut ; surrogates
  réalistes cohérents en genre (Faker fr_FR) en option par dossier, avec la
  même réversibilité.
- **Acceptance :** même corpus traité dans les deux modes : réversibilité
  exacte dans les deux cas ; en mode surrogate, le genre grammatical des
  substituts correspond à celui des originaux sur le corpus de test.

### REQ-013 : proxy OpenAI-compatible multi-backends
- **Current :** pas de proxy.
- **Target :** `/v1/chat/completions` et `/v1/models` conformes au format
  OpenAI ; backend sélectionné par configuration (Ollama local, Infomaniak AI
  Tools, Scaleway Generative APIs, tout endpoint OpenAI-compatible), aucun code
  spécifique par fournisseur.
- **Acceptance :** OpenWebUI configuré avec la seule base URL du sas obtient
  une réponse complète ; changer de backend ne demande qu'un changement de
  configuration ; les tests utilisent exclusivement le faux backend.

### REQ-014 : juge LLM local optionnel et dégradable
- **Current :** détection limitée aux regex et au NER.
- **Target :** troisième passe par LLM local (Ollama) qui signale les entités
  candidates manquées ; activable / désactivable ; le sas reste fonctionnel et
  documenté comme moins couvrant sans le juge ; le juge n'appelle jamais un
  service distant.
- **Acceptance :** corpus contenant des identifiants indirects (fonction rare,
  petite commune) : le juge en signale au moins une partie que regex + NER
  manquent ; sas opérationnel avec juge désactivé ; test réseau : zéro appel
  sortant pendant la passe juge.

### REQ-015 : conformité commun numérique
- **Current :** rien de publié.
- **Target :** dépôt public avec licence EUPL-1.2, README bilingue FR (EN
  résumé), CONTRIBUTING, crédit explicite du travail de Romain Bochet pour les
  reconnaisseurs réutilisés, aucune donnée client, aucun secret, aucune
  métadonnée de génération automatique dans les fichiers livrés.
- **Acceptance :** checklist de publication passée en revue avant tout push
  public ; scan de secrets et de données du corpus sur l'historique git.

### REQ-016 : détection française de référence
- **Current :** couverture hétérogène selon les POC.
- **Target :** détecteurs validés pour NIR (clé de contrôle, Corse 2A/2B),
  SIRET / SIREN (Luhn), IBAN, email, téléphone FR, adresse postale, plaque
  d'immatriculation, date de naissance, personne, organisation, lieu, fonction ;
  priorité de résolution des chevauchements :
  `FR_NIR > FR_SIRET > FR_SIREN > IBAN > EMAIL > PHONE > ADDRESS > CREDIT_CARD >
  PERSON > ORGANIZATION > LOCATION > DATE > GENERIC`.
- **Acceptance :** suite de tests par type (dont NIR corses valides et
  invalides) ; le cas « SIRET détecté comme carte bancaire » résout vers
  FR_SIRET ; les tests portent sur les réponses API réelles, pas seulement les
  fonctions internes.
