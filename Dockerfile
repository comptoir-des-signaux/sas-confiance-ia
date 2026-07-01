# Image du sas (ADR-013) : proxy + détection déterministe + NER CamemBERT.
# Les modèles sont téléchargés AU BUILD (HANDOFF règle 1 : jamais au runtime) ;
# l'exécution se fait sans réseau sortant autre que le backend configuré.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app

# Dépendances d'abord (cache de build) : torch CPU, le GPU est réservé au
# service Ollama, pas au NER.
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN uv venv /opt/venv --python 3.12 \
    && uv pip install --python /opt/venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu \
    && uv pip install --python /opt/venv/bin/python .[ner]

# Modèle NER épinglé, téléchargé au build dans un cache lisible par l'usager
# non privilégié.
ENV HF_HOME=/opt/modeles
RUN /opt/venv/bin/python -m sas_confiance_ia.telechargement \
    && useradd --create-home --uid 1000 sas \
    && chmod -R a+rX /opt/modeles \
    && mkdir /donnees && chown sas /donnees

USER sas
ENV PATH="/opt/venv/bin:$PATH" \
    SAS_HOTE=0.0.0.0 \
    SAS_PORT=8787
EXPOSE 8787

CMD ["python", "-m", "sas_confiance_ia"]
