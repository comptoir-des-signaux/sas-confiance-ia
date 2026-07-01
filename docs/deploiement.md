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
téléchargement au démarrage.

### Sans Docker

```bash
uv venv && uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -e ".[ner]"
uv run python -m sas_confiance_ia.telechargement
SAS_BACKEND_BASE_URL=http://localhost:11434/v1 SAS_MODELES=mistral-small:24b \
  uv run python -m sas_confiance_ia
```

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
# 2.4 Streaming refusé (REQ-010) : "stream": true  ->  HTTP 400
# 2.5 Backend éteint : docker compose stop ollama  ->  HTTP 502
#     avec détail limité au type d'erreur, puis docker compose start ollama
```

Attendu : la réponse 2.2 est ré-identifiée (les valeurs réapparaissent) et
le bloc `sas_confiance_ia` indique `integrite.action: ok`. Côté Ollama,
`docker compose logs ollama` ne doit montrer que des placeholders
(`[PERSONNE_001]`, `[EMAIL_001]`...) dans les prompts reçus.

## 3. OpenWebUI pointé sur le sas (REQ-013)

Dans OpenWebUI : Paramètres > Connexions > ajouter une connexion de type
OpenAI avec pour base URL `http://<hôte-du-sas>:8787/v1` (aucune clé
requise par défaut). Les modèles de `SAS_MODELES` apparaissent ; toute
conversation passe alors par le sas.

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

Par défaut le vault vit en mémoire (rien sur disque). Pour la persistance
chiffrée (REQ-004, REQ-005) :

```bash
export SAS_VAULT_CHEMIN=/données/vault.sas
export SAS_VAULT_CLE="$(uv run python -c 'from sas_confiance_ia.vault import generer_cle; print(generer_cle().decode())')"
```

Conserver la clé dans un gestionnaire de secrets ; la perdre rend le vault
définitivement illisible (c'est voulu).
