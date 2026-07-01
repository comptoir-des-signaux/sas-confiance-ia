"""Test sanité du Lot 0 : le paquet s'importe et le garde-fou réseau agit."""

import socket

import pytest

import sas_confiance_ia


def test_version():
    assert sas_confiance_ia.__version__


def test_le_reseau_externe_est_interdit():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="interdit"):
        s.connect(("93.184.215.14", 80))
    s.close()
