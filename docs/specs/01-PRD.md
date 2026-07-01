# 01-PRD : Sas Confiance IA

**Statut :** v0.1 du 2026-07-01. Nom acté : **Sas Confiance IA**, sous-titre
« sas de pseudonymisation avant IA » (ADR-011).

---

## 1. Vision

Permettre aux organisations publiques et para-publiques d'utiliser l'IA
générative **sans abandonner la maîtrise des données, des flux et de la
responsabilité**. Entre l'interdiction paralysante et l'usage sauvage, l'outil
matérialise une troisième voie : un sas technique, documentaire et pédagogique.

Trois ambitions simultanées :

1. **Outil opérationnel** : un proxy et une interface utilisables en vrai, du
   poste isolé (T0) au déploiement souverain (T2 Infomaniak / Scaleway).
2. **Commun numérique** : dépôt public sous EUPL-1.2, documentation exemplaire,
   contributions ouvertes, réutilisable par toute collectivité ou prestataire.
3. **Actif pédagogique** : chaque concept (DCP, pseudonymisation, vault,
   non-fuite) est démontrable en formation avec des données synthétiques.

## 2. Utilisateurs

| Persona | Besoin principal |
|---|---|
| DPO / juriste / conformité | Comprendre et documenter ce qui sort, réduire les risques sans surpromesse |
| DSI / RSSI | Canaliser les usages sauvages, auditer sans exposer les contenus |
| Agent public / métier | Utiliser l'IA sans devenir expert RGPD, sans perdre plus de temps qu'il n'en gagne |
| Consultant / formateur / AMO | Démontrer la bonne pratique, manipuler des cas réalistes synthétiques |

Secondaires : DRH, directions juridiques, services sociaux, centres de gestion,
syndicats mixtes, agences techniques, cabinets d'avocats et d'expertise comptable.

## 3. Cas d'usage (ordre de livraison)

1. **Proxy IA transparent** (premier livrable fonctionnel, ADR-003) :
   l'utilisateur pointe OpenWebUI / LibreChat / tout client OpenAI-compatible
   vers le sas ; pseudonymisation à l'aller, contrôle d'intégrité et
   ré-identification optionnelle au retour.
2. **Copier-coller sécurisé** : coller un texte, voir les entités détectées,
   récupérer le texte pseudonymisé, ré-identifier la réponse.
3. **Analyse de document** : `.txt`, `.md`, `.docx`, `.pdf` textuel ; rapport de
   détection ; journal sans données brutes.
4. **Mode formation** : données synthétiques uniquement, affichage du vault et
   des détections, bandeau « Mode démonstration : ne pas utiliser avec des
   données réelles ».
5. **Mode revue humaine** : les détections ambiguës (dates procédurales,
   fonctions rares, mentions indirectes) sont proposées avant remplacement.
6. **Mode irréversible** : masquage sans conservation de correspondance.

## 4. Différenciateurs (vs POC existants)

| Différenciateur | Pourquoi c'est le cœur |
|---|---|
| **Tests de non-fuite prouvables** | Un faux backend capture le payload HTTP réellement sortant ; la CI échoue si une valeur brute connue apparaît. Personne ne le fait dans l'état de l'art praticien |
| **Cohérence de coréférence par dossier** | « Jean Dupont », « M. Dupont », « le requérant » → même `[PERSONNE_001]`, y compris entre plusieurs pièces d'un même dossier |
| **Triple détection** | Regex FR validées (NIR, SIRET, SIREN, IBAN, téléphone...) + NER CamemBERT + juge LLM local optionnel en troisième lecture |
| **Proxy OpenAI-compatible** | Se branche sans modification sur les clients existants et couvre Ollama, Infomaniak, Scaleway avec la même abstraction |
| **Vault chiffré, compteurs persistants** | Ré-identification exacte après redémarrage, placeholders jamais réattribués, purge maîtrisée |
| **Rigueur terminologique** | Pseudonymisation nommée pseudonymisation ; l'anonymisation est un mode, pas une promesse |
| **Pédagogie intégrée** | Mode démo séparé, documentation MkDocs, scénarios synthétiques prêts pour la formation |

## 5. Parcours clé (proxy, mode réversible)

```
Client (OpenWebUI) ──POST /v1/chat/completions──▶ Sas
  Sas : détection (regex + NER + juge) → pseudonymisation → vault (local, chiffré)
  Sas ──payload pseudonymisé──▶ Backend (Ollama / Infomaniak / Scaleway)
  Backend ──réponse pseudonymisée──▶ Sas
  Sas : contrôle d'intégrité des placeholders → ré-identification si politique l'autorise
  Sas ──réponse finale──▶ Client
```

Headers de pilotage : `X-Dossier-Id`, `X-Privacy-Mode` (reversible |
irreversible | review), `X-Reidentify-Response`. Streaming refusé en v1.

## 6. Non-objectifs (assumés)

L'application ne doit pas être : un gadget de remplacement de mots, une promesse
marketing de conformité, une boîte noire, un service cloud qui absorbe les
données sous prétexte de les protéger, un outil qui masque tout et détruit le
sens, une démo appelée production, un proxy sans tests de fuite, ni un outil
« d'anonymisation » qui fait de la pseudonymisation réversible.

Hors scope v1 : OCR, streaming, multi-tenant, connecteurs GED / email,
authentification multi-utilisateur, données réelles en phase de test.

## 7. Positionnement

> Un sas de pseudonymisation vérifiable pour permettre l'usage de l'IA
> générative sans exposer inutilement les données personnelles.

Pour les collectivités : aider à utiliser l'IA sans transformer les données des
agents, usagers et administrés en matière première non maîtrisée. Pour les
DSI / DPO : un proxy local ou souverain qui réduit les données envoyées aux
modèles, conserve la correspondance en zone de confiance et produit des journaux
exploitables sans fuite de contenu.

**Différenciation vs Écluse** (`ecluse-dev/ecluse`, concurrent direct identifié
le 2026-07-01) : eux visent santé, mobile-first et SDK Dart/Python sous
Apache-2.0 ; Sas Confiance IA vise les collectivités et la fonction publique
territoriale, le proxy OpenAI-compatible auto-hébergeable (Docker, T0 à T2),
la dimension formation intégrée et la licence EUPL-1.2. Les deux projets
peuvent coexister et se citer mutuellement.
