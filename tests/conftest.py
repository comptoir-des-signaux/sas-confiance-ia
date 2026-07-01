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
