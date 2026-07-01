"""Point d'entrée du sas : python -m sas_confiance_ia.

Configuration par variables d'environnement (voir configuration.py) ;
SAS_HOTE et SAS_PORT pilotent l'écoute (défaut : 127.0.0.1:8787, boucle
locale seule : exposer davantage est un choix explicite de déploiement).
"""

import os

import uvicorn

from .configuration import creer_application_depuis_environnement

if __name__ == "__main__":
    application = creer_application_depuis_environnement()
    uvicorn.run(
        application,
        host=os.environ.get("SAS_HOTE", "127.0.0.1"),
        port=int(os.environ.get("SAS_PORT", "8787")),
    )
