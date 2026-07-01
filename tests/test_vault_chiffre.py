"""Lot 5 : vault persistant chiffré (REQ-004) et compteurs durables (REQ-005)."""

import pytest
from cryptography.fernet import InvalidToken

from sas_confiance_ia.vault import VaultChiffre, generer_cle


@pytest.fixture
def cle():
    return generer_cle()


@pytest.fixture
def chemin(tmp_path):
    return tmp_path / "test.vault"


def test_le_fichier_ne_contient_aucune_valeur_en_clair(chemin, cle):
    # REQ-004 : inspection binaire du fichier.
    vault = VaultChiffre(chemin, cle)
    vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    vault.placeholder_pour("d1", "FR_NIR", "1 80 03 74 118 218 22")
    octets = chemin.read_bytes()
    assert b"jean.dupont" not in octets
    assert b"180037411821822" not in octets
    assert b"118 218" not in octets


def test_redemarrage_les_correspondances_survivent(chemin, cle):
    vault = VaultChiffre(chemin, cle)
    p1 = vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    # Redémarrage simulé : nouvelle instance sur le même fichier.
    vault2 = VaultChiffre(chemin, cle)
    assert vault2.valeur_pour("d1", p1) == "jean.dupont@exemple.fr"
    assert vault2.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr") == p1


def test_redemarrage_aucun_placeholder_reattribue(chemin, cle):
    # REQ-005 : après redémarrage, les compteurs reprennent, ils ne repartent
    # pas de zéro.
    vault = VaultChiffre(chemin, cle)
    p1 = vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    assert p1 == "[EMAIL_001]"
    vault2 = VaultChiffre(chemin, cle)
    p2 = vault2.placeholder_pour("d1", "EMAIL", "marie.martin@exemple.fr")
    assert p2 == "[EMAIL_002]"
    assert vault2.valeur_pour("d1", "[EMAIL_001]") == "jean.dupont@exemple.fr"


def test_les_dossiers_restent_isoles_apres_redemarrage(chemin, cle):
    vault = VaultChiffre(chemin, cle)
    vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    vault2 = VaultChiffre(chemin, cle)
    p = vault2.placeholder_pour("d2", "EMAIL", "marie.martin@exemple.fr")
    assert p == "[EMAIL_001]"
    assert vault2.valeur_pour("d2", "[EMAIL_001]") == "marie.martin@exemple.fr"
    assert vault2.valeur_pour("d1", "[EMAIL_001]") == "jean.dupont@exemple.fr"


def test_une_mauvaise_cle_ne_dechiffre_pas(chemin, cle):
    vault = VaultChiffre(chemin, cle)
    vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    with pytest.raises(InvalidToken):
        VaultChiffre(chemin, generer_cle())


def test_purge_d_un_dossier(chemin, cle):
    # Exigence du cadrage §9.6 : vault purgeable, par dossier.
    vault = VaultChiffre(chemin, cle)
    vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    vault.purger("d1")
    vault2 = VaultChiffre(chemin, cle)
    assert vault2.valeur_pour("d1", "[EMAIL_001]") is None
    assert b"jean.dupont" not in chemin.read_bytes()
