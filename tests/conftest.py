"""Garde-fous globaux de la suite de tests.

Règle 1 du HANDOFF : aucun appel réseau externe pendant les tests. Toute
tentative de connexion vers autre chose que la boucle locale échoue
immédiatement.
"""

import socket

import pytest

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_original_connect = socket.socket.connect


def _connect_local_seulement(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and host not in _LOOPBACK:
        raise RuntimeError(
            f"Appel réseau externe interdit pendant les tests : {host!r} (HANDOFF, règle 1)"
        )
    return _original_connect(self, address)


@pytest.fixture(autouse=True)
def interdiction_reseau_externe(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _connect_local_seulement)


def moteur_ner_disponible() -> bool:
    """Vrai si l'extra [ner] est installé ET le modèle épinglé déjà en cache."""
    try:
        from sas_confiance_ia.ner import modele_transformers_present

        return modele_transformers_present()
    except ImportError:
        return False


@pytest.fixture(scope="session")
def moteur_ner():
    """Moteur NER partagé par toute la session : le chargement du modèle est lourd."""
    if not moteur_ner_disponible():
        pytest.skip(
            "modèle NER absent : installer l'extra [ner] puis "
            "python -m sas_confiance_ia.telechargement"
        )
    from sas_confiance_ia.ner import creer_moteur_ner

    return creer_moteur_ner()
