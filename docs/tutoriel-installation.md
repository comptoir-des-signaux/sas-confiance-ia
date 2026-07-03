# Tutoriel d'installation (Kubuntu / Docker)

Ce tutoriel part d'une machine vierge et aboutit à un sas fonctionnel avec
son LLM local et, en option, une interface de chat. Il est écrit pour
Kubuntu 26.04 (poste de référence du projet) et vaut pour tout Ubuntu ou
dérivé. Pour l'exploitation au quotidien (arrêter, mettre à jour,
persistance du vault), voir le [guide de déploiement](deploiement.md).

**Ce qu'il vous faut :**

- une machine Linux avec Docker ;
- pour le LLM local : un GPU NVIDIA avec assez de VRAM pour le modèle choisi
  (référence : 24 Go pour mistral-small:24b ; des modèles plus petits
  tournent avec moins) ;
- sans GPU : un compte chez un fournisseur d'IA souverain OpenAI-compatible
  (Infomaniak, Scaleway...), voir l'étape 5 bis.

## 1. Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"
```

Fermez la session et rouvrez-la (le groupe `docker` doit être pris en
compte), puis vérifiez :

```bash
docker run --rm hello-world
```

## 2. NVIDIA container toolkit (si GPU, pour le LLM local)

Pilote NVIDIA d'abord (`sudo ubuntu-drivers install`, puis redémarrage),
ensuite le toolkit qui permet aux conteneurs d'utiliser le GPU :

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Vérification : `docker run --rm --gpus all ubuntu nvidia-smi` doit afficher
votre GPU.

## 3. Récupérer le sas

```bash
git clone https://github.com/comptoir-des-signaux/sas-confiance-ia.git
cd sas-confiance-ia
```

## 4. Premier démarrage (sas + LLM local)

```bash
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull mistral-small:24b
```

Le premier build prend plusieurs minutes : l'image télécharge ses
dépendances et le modèle de détection CamemBERT **au build** (jamais au
démarrage ni pendant l'usage : une fois construit, le sas ne télécharge
plus rien).

Vérification :

```bash
curl http://127.0.0.1:8787/health     # {"statut":"ok"}
```

## 5. Première pseudonymisation

Ouvrez `http://127.0.0.1:8787/` : collez un texte (utilisez le
[corpus synthétique](../corpus/synthetique/) du dépôt, jamais un vrai
document pour vos essais), pseudonymisez, observez les types détectés,
ré-identifiez. La page `http://127.0.0.1:8787/fichiers` accepte le
glisser-déposer (`.txt`, `.md`, `.csv`, `.docx`, `.pdf` textuel) et affiche
l'original et la version pseudonymisée côte à côte.

Par l'API (le sas est un proxy OpenAI-compatible) :

```bash
curl -s -X POST http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" -H "X-Dossier-Id: essai-001" \
  -d '{
    "model": "mistral-small:24b",
    "messages": [{"role": "user", "content": "Résume : Marie Martin (marie.martin@exemple.fr, 06 12 34 56 78) demande la révision de son dossier ALL-2026-0457."}]
  }'
```

Le modèle ne voit que des pseudonymes (`docker compose logs ollama` pour le
constater) ; la réponse vous revient ré-identifiée.

## 5 bis. Sans GPU : backend souverain distant

Le sas garde la détection et le vault **en local** ; seul le texte déjà
pseudonymisé part vers le fournisseur :

```bash
export SAS_BACKEND_BASE_URL="https://api.infomaniak.com/1/ai/<product_id>/openai/v1"
export SAS_MODELES="mistral24b"
export SAS_BACKEND_CLE_API="<clé depuis votre gestionnaire de secrets>"
docker compose up --build -d
```

Exemples pour d'autres fournisseurs : [guide de déploiement](deploiement.md),
section 4.

## 6. Interface de chat (option)

Pour une interface type ChatGPT par-dessus le sas :

```bash
docker compose --profile ollama --profile openwebui up -d
```

OpenWebUI est servi sur `http://127.0.0.1:3000/` (le premier compte créé
est administrateur) et parle au sas, jamais directement au modèle. La
réponse s'affiche d'un bloc en fin de génération : le sas convertit le
streaming en non-streaming (REQ-010), c'est le comportement attendu.

## 7. Et ensuite

- **Persistance du vault** (sinon les correspondances sont perdues à
  l'arrêt) : [déploiement, section 5](deploiement.md).
- **Politiques par type** (conserver les SIREN, marquer les références de
  dossier pour revue...) : [déploiement, section 7](deploiement.md).
- **Ce que le sas garantit et ne garantit pas** : [README](../README.md),
  à lire avant tout usage sur documents réels.

## Dépannage

| Symptôme | Cause probable | Remède |
|---|---|---|
| `502 Backend indisponible` à chaque requête | Pas de backend : profil `ollama` absent et `SAS_BACKEND_BASE_URL` non défini | Relancer avec `--profile ollama`, ou définir la variable |
| Le sas refuse de démarrer (moteur NER) | Modèle NER non chargeable | Reconstruire l'image (`docker compose up --build -d`) ; un sas sans NER se choisit explicitement avec `SAS_NER=inactif` |
| `nvidia-smi` inconnu dans le conteneur | Toolkit NVIDIA non configuré | Reprendre l'étape 2, redémarrer Docker |
| Placeholders plus ré-identifiables après redémarrage | Vault en mémoire (défaut) | Configurer la persistance chiffrée, [déploiement §5](deploiement.md) |
| OpenWebUI ne liste aucun modèle | Le modèle n'est pas tiré côté Ollama | `docker compose exec ollama ollama pull <modèle>` et vérifier `SAS_MODELES` |
