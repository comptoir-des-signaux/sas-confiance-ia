# Déploiement et validation manuelle

Le sas se déploie en Docker Compose (distribution de référence, ADR-013) ou
directement via `uv`. Les tests automatisés n'appellent JAMAIS un backend
réel : la validation de bout en bout décrite ici est **manuelle**, hors CI.

## 1. Démarrage local complet (sas + Ollama, GPU NVIDIA)

Prérequis : Docker, NVIDIA container toolkit, un GPU avec assez de VRAM pour
le modèle choisi (poste de référence : RTX 5090, 24 Go).

```bash
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull mistral-small:24b
```

Le sas écoute sur `http://127.0.0.1:8787` (boucle locale par défaut).
Le NER CamemBERT est intégré à l'image, téléchargé au build : aucun
téléchargement au démarrage. L'interface web minimale est servie à la
racine (`http://127.0.0.1:8787/`) : pseudonymiser, ré-identifier,
télécharger ; l'API du proxy reste sous `/v1/`.

### Sans Docker

```bash
uv venv && uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e ".[ner]"
uv run python -m sas_confiance_ia.telechargement
SAS_BACKEND_BASE_URL=http://localhost:11434/v1 SAS_MODELES=mistral-small:24b \
  uv run python -m sas_confiance_ia
```

## 1 bis. Lancer, arrêter, mettre à jour le conteneur

Toutes les commandes se lancent depuis la racine du dépôt (là où vit
`docker-compose.yml`).

```bash
# Lancer (sas seul, backend externe à définir) :
SAS_BACKEND_BASE_URL=... SAS_MODELES=... docker compose up -d

# Lancer avec le service Ollama local (GPU NVIDIA) :
docker compose --profile ollama up -d

# État et journaux :
docker compose ps
docker compose logs -f sas          # Ctrl+C pour quitter le suivi

# Arrêter (les conteneurs s'arrêtent, volumes et images conservés) :
docker compose stop sas             # le sas seul
docker compose --profile ollama stop  # sas + Ollama

# Redémarrer sans changement de code :
docker compose start sas

# Mettre à jour après un changement de code (reconstruit l'image puis
# remplace le conteneur ; Ollama n'est pas touché) :
docker compose up -d --build sas
```

Points d'attention :

- **Vault en mémoire par défaut** : sans `SAS_VAULT_CHEMIN` + `SAS_VAULT_CLE`,
  arrêter ou remplacer le conteneur perd toutes les correspondances (les
  placeholders déjà distribués ne seront plus ré-identifiables). Pour
  persister : §5.
- `docker compose down` supprime les conteneurs (volumes conservés) ;
  `docker compose down --volumes` supprime AUSSI le volume `donnees`, donc
  un vault persistant qui s'y trouverait : geste volontaire uniquement.
- La reconstruction (`--build`) réinstalle les dépendances et retélécharge
  le modèle NER épinglé : plusieurs minutes et du réseau au BUILD (jamais au
  runtime, HANDOFF règle 1). Le conteneur en cours continue de servir
  jusqu'à la bascule.
- Vérification après bascule : `curl http://127.0.0.1:8787/health` puis un
  tour sur `http://127.0.0.1:8787/` et `http://127.0.0.1:8787/fichiers`.

## 2. Test d'intégration manuel (checklist)

Toutes les valeurs ci-dessous sont synthétiques (corpus du dépôt). À
dérouler après chaque changement touchant le proxy, les backends ou Docker.

```bash
# 2.1 Santé et modèles
curl -s http://127.0.0.1:8787/health
curl -s http://127.0.0.1:8787/v1/models

# 2.2 Aller-retour pseudonymisé (le backend ne voit jamais les valeurs)
curl -s -X POST http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" -H "X-Dossier-Id: demo-001" \
  -d '{
    "model": "mistral-small:24b",
    "messages": [{"role": "user", "content": "Résume : Marie Martin (marie.martin@exemple.fr, 06 12 34 56 78) demande la révision de son dossier ALL-2026-0457."}]
  }'

# 2.3 Réponse brute pseudonymisée (sans ré-identification)
#     Ajouter : -H "X-Reidentify-Response: false"
# 2.4 Streaming converti (REQ-010) : "stream": true  ->  réponse complète
#     non streamée (HTTP 200), événement conversion_streaming au journal
# 2.5 Backend éteint : docker compose stop ollama  ->  HTTP 502
#     avec détail limité au type d'erreur, puis docker compose start ollama
```

Attendu : la réponse 2.2 est ré-identifiée (les valeurs réapparaissent) et
le bloc `sas_confiance_ia` indique `integrite.action: ok`. Côté Ollama,
`docker compose logs ollama` ne doit montrer que des placeholders
(`[PERSONNE_001]`, `[EMAIL_001]`...) dans les prompts reçus.

## 3. OpenWebUI pointé sur le sas (REQ-013)

Le plus simple : le profil `openwebui` du compose, qui lance OpenWebUI
préconfiguré sur le sas via le réseau Docker interne.

```bash
docker compose --profile ollama --profile openwebui up --build -d
# OpenWebUI : http://127.0.0.1:3000/  (premier compte créé = admin)
```

Pour une instance OpenWebUI existante : Paramètres > Connexions > ajouter
une connexion de type OpenAI avec pour base URL
`http://<hôte-du-sas>:8787/v1` (aucune clé requise par défaut). Les modèles
de `SAS_MODELES` apparaissent ; toute conversation passe alors par le sas.

OpenWebUI demande du streaming par défaut : le sas convertit la requête en
non-streaming (REQ-010) et la réponse s'affiche d'un bloc en fin de
génération. C'est le comportement attendu, pas une panne.

## 4. Backends cloud : la même abstraction, zéro code spécifique

Changer de backend = changer la configuration (REQ-013). Exemples, la clé
API étant toujours fournie par l'environnement ou un gestionnaire de
secrets, jamais écrite dans un fichier versionné :

```bash
# Infomaniak AI Tools (Suisse, OpenAI-compatible), premier cloud qualifié (ADR-005)
export SAS_BACKEND_BASE_URL="https://api.infomaniak.com/1/ai/<product_id>/openai/v1"
export SAS_MODELES="mistral24b"
export SAS_BACKEND_CLE_API="<clé depuis votre gestionnaire de secrets>"

# Scaleway Generative APIs (France)
export SAS_BACKEND_BASE_URL="https://api.scaleway.ai/v1"
export SAS_MODELES="mistral-small-3.1-24b-instruct-2503"
export SAS_BACKEND_CLE_API="<clé depuis votre gestionnaire de secrets>"

docker compose up --build -d   # sans le profil ollama : topologie T2
```

Vérifier les identifiants de modèles dans la console du fournisseur : ils
évoluent. Dérouler ensuite la checklist §2 (2.5 se simule en coupant le
réseau sortant ou avec une base URL invalide).

## 5. Vault persistant (optionnel)

Par défaut le vault vit en mémoire : rien sur disque, et tout est perdu à
l'arrêt du processus ou du conteneur. Pour la persistance chiffrée
(REQ-004, REQ-005), avec Docker Compose (le volume `donnees` est monté sur
`/donnees` dans le conteneur et les deux variables sont transmises) :

```bash
export SAS_VAULT_CHEMIN=/donnees/vault.sas
export SAS_VAULT_CLE="$(uv run python -c 'from sas_confiance_ia.vault import generer_cle; print(generer_cle().decode())')"
docker compose up -d
```

Vérifier après démarrage que le vault est bien persistant : redémarrer le
conteneur et confirmer qu'un placeholder déjà émis se ré-identifie encore.
Conserver la clé dans un gestionnaire de secrets ; la perdre rend le vault
définitivement illisible (c'est voulu).

## 6. Choix du NER à l'exécution

`SAS_NER=transformers` (défaut) exige le modèle CamemBERT épinglé : présent
dans l'image Docker, à télécharger une fois hors Docker
(`python -m sas_confiance_ia.telechargement`). Le démarrage est **refusé**
si le moteur demandé n'est pas chargeable : la couverture ne se dégrade
jamais en silence. Pour un sas volontairement sans NER (couverture réduite
aux types déterministes) : `SAS_NER=inactif`, choix journalisé. Le repli
`SAS_NER=spacy` exige l'extra `[ner-repli-spacy]`, non embarqué dans
l'image de référence (le moteur transformers y est déjà).

## 7. Politiques de remplacement à l'exécution (Lot 14)

Défauts d'instance par `SAS_POLITIQUES` (format « TYPE=action », séparé par
des virgules ; actions : `pseudonymiser`, `masquer`, `conserver`, `revue`) :

```bash
export SAS_POLITIQUES="FR_SIREN=conserver,REFERENCE_DOSSIER=revue"
```

Une action ou un type inconnu **refuse le démarrage** ; `conserver` est
tracé en avertissement (les valeurs de ce type partent en clair vers le
backend). Chaque dossier peut surcharger ces défauts depuis l'interface
(dates procédurales, surrogates réalistes) : ce choix est stocké dans le
vault et survit au redémarrage. Détail des actions et des surrogates
(REQ-012, arbitrage Q5) : README, section « Politiques de remplacement par
type ».
