"""Téléchargement des modèles NER épinglés, à l'installation uniquement.

Usage : python -m sas_confiance_ia.telechargement

Règle 1 du HANDOFF : aucun téléchargement au runtime ni pendant les tests.
Cette étape est la seule à toucher le réseau ; elle épingle la révision
exacte du modèle (parade F9 du 02-AI-SPEC).
"""

from .ner import MODELE_TRANSFORMERS, chemin_modele_transformers


def telecharger() -> str:
    """Télécharge le modèle transformers épinglé et retourne son chemin local."""
    return chemin_modele_transformers(telechargement_autorise=True)


if __name__ == "__main__":
    print(f"Téléchargement de {MODELE_TRANSFORMERS} (révision épinglée)...")
    print(f"Modèle disponible : {telecharger()}")
