# 04-ADR : décisions d'architecture et de gouvernance

**Statut :** v0.1 du 2026-07-01. Les décisions marquées « actée » ont été
arbitrées par Pascal Chevallot le 2026-07-01 ; celles marquées « par défaut »
appliquent la recommandation de l'expert en l'absence de réponse et restent
réversibles à faible coût tant que rien n'est publié.

---

## ADR-001 : repo neuf avec réemploi ciblé d'amo-presidio (actée)

**Contexte.** Le POC `rbochet/amo-presidio` est un bon démonstrateur (NIR avec
clé de contrôle, SIRET/SIREN Luhn, extraction docx/pdf) mais monolithique, sans
tests, sans licence, avec vault retourné en clair et un nommage
« anonymisation » contraire au cadrage.

**Décision.** Nouveau dépôt, spec pack propre. Les reconnaisseurs français de
Romain Bochet sont réimportés comme composants testés, avec son accord et un
crédit explicite (README et en-têtes). `amo-presidio` reste le POC pédagogique
de Romain.

**Conséquences.** Accord de réemploi obtenu auprès de Romain Bochet
(confirmé par Pascal le 2026-07-01). Crédit explicite dans le README et les
en-têtes des modules concernés (validateurs NIR / Luhn).

## ADR-002 : licence EUPL-1.2 (actée)

**Décision.** Le commun numérique est publié sous EUPL-1.2 : licence officielle
de l'Union européenne, copyleft modéré compatible (liste de compatibilité
incluant GPL, AGPL, MPL), recommandée pour le secteur public français.

**Conséquences.** Vérifier la compatibilité des dépendances (Presidio MIT :
compatible). Les contributions externes se font sous la même licence (DCO
plutôt que CLA pour rester léger).

## ADR-003 : premier livrable fonctionnel = proxy OpenAI-compatible (actée)

**Décision.** Après la Phase 0 (socle + invariants + faux backend), le premier
livrable est `/v1/chat/completions`. L'interface web copier-coller vient
ensuite, servie par le même FastAPI.

**Conséquences.** Démontrable immédiatement avec OpenWebUI en formation ;
couvre Ollama, Infomaniak et Scaleway dès le premier jour via la configuration.

## ADR-004 : détection en triptyque, juge LLM local optionnel (actée)

**Décision.** Trois couches : (1) reconnaisseurs déterministes français
validés, (2) NER CamemBERT (Presidio accepte les modèles transformers), (3)
juge LLM local via Ollama en troisième lecture pour les « inconnus inconnus ».
Le juge est optionnel : le sas fonctionne sans lui sur machine modeste, la
couverture moindre étant documentée.

**Conséquences.** Le poste de référence (RTX 5090, 24 Go VRAM) exécute tout en
local. Le juge ne fait jamais d'appel distant (REQ-014). spaCy peut rester en
solution de repli légère derrière la même interface.

## ADR-005 : backends de démonstration : Ollama local puis Infomaniak (par défaut)

**Décision.** La démo fondatrice tourne 100 % en local (T0, récit « zéro
sortie »). Le premier backend cloud qualifié est Infomaniak AI Tools (Suisse,
OpenAI-compatible, hébergeur déjà utilisé par CdS), Scaleway Generative APIs en
second. Aucun code spécifique par fournisseur : tout passe par l'abstraction
OpenAI-compatible.

## ADR-006 : placeholders typés par défaut, surrogates en option (par défaut)

**Décision.** `[PERSONNE_001]` est le défaut : auditable, sans ambiguïté.
Les surrogates réalistes cohérents en genre sont une option par dossier, pour
les cas où les placeholders dégradent la qualité de sortie du LLM (accords
grammaticaux français).

## ADR-007 : vault à double mode (par défaut)

**Décision.** Deux modes assumés : (1) **stateless** : le vault chiffré est
rendu au client et rien ne persiste côté serveur (usage ponctuel, pédagogie) ;
(2) **stateful** : vault chiffré côté sas, scopé par dossier, compteurs
persistants (requis pour le proxy et le multi-pièces). Le mode sérieux ne
retourne jamais le vault en clair.

## ADR-008 : pas de streaming en v1 (actée via cadrage)

**Décision.** `stream=true` refusé ou converti explicitement : un placeholder
coupé entre deux chunks rend la ré-identification et le contrôle d'intégrité
non fiables. Réévaluation possible en v2 (tampon de re-fenêtrage).

## ADR-009 : Presidio in-process (actée via cadrage)

**Décision.** Presidio est utilisé comme bibliothèque Python dans le processus
FastAPI, pas comme conteneurs analyzer / anonymizer séparés : moins de surface
réseau interne, déploiement mono-conteneur possible, plus simple à auditer.

## ADR-010 : documentation MkDocs Material + kit atelier CdS séparé (par défaut)

**Décision.** Le dépôt public porte un site MkDocs Material (GitHub Pages) :
tutoriel d'installation Docker, parcours pédagogique, glossaire RGPD, limites.
Le kit d'atelier CdS (slides, scénarios d'animation, exercices minutés) reste
un actif différenciant dans `formations/`, hors du dépôt public.

## ADR-011 : nom de l'application : « Sas Confiance IA » (actée le 2026-07-01)

**Contexte.** Le premier choix, « L'Écluse », est tombé à la vérification de
disponibilité : `ecluse-dev/ecluse` (GitHub, créé en mai 2026, Apache-2.0,
actif) porte exactement le même nom et le même positionnement (sas RGPD avant
LLM, détecteurs français NIR / RPPS / FINESS, obsession santé). « Barbacane »
est également pris (passerelle IA bidirectionnelle).

**Décision.** L'application s'appelle **Sas Confiance IA**, avec le sous-titre
descriptif « sas de pseudonymisation avant IA ». Slug technique :
`sas-confiance-ia` (libre sur GitHub et PyPI au 2026-07-01). Le mot
« anonymisation » est exclu du nom (cadrage §6.5).

**Conséquences.** La communication reste sobre : le nom dit la confiance
construite par le sas, jamais une conformité garantie (formulations interdites
du 00-CONTEXT §6). Le projet Écluse est suivi comme concurrent direct et
source d'étude (leur bench Presidio et leur générateur de corpus sont
publics sous Apache-2.0).

## ADR-012 : hébergement sur une organisation GitHub CdS (par défaut)

**Décision.** Le dépôt public vit dans une organisation GitHub au nom de
Comptoir des Signaux (visibilité, CI, standard des communs numériques), pas sur
un compte personnel. Rien n'est publié avant la checklist REQ-015.

## ADR-013 : cible d'installation et de passage à l'échelle (actée via demande)

**Décision.** Distribution de référence : Docker Compose (image unique sas +
service Ollama optionnel), validée sur Kubuntu 26.04 avec GPU NVIDIA
(container toolkit). Le même compose, sans le service Ollama et pointé vers
Infomaniak ou Scaleway, constitue la topologie T2 de déploiement serveur.
