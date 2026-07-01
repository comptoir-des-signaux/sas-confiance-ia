"""Lot 1 : validateurs français purs (REQ-016 partiel).

Cas de test alignés sur le corpus synthétique et sur les limites documentées
du cadrage (NIR Corse 2A/2B).
"""

from sas_confiance_ia.validators import iban_valide, luhn_valide, nir_cle, nir_valide

# ---------------------------------------------------------------------------
# NIR : clé de contrôle sur 13 caractères, cas Corse 2A/2B inclus
# ---------------------------------------------------------------------------


def test_nir_cle_calculee_sur_les_valeurs_du_corpus():
    assert nir_cle("1800374118218") == 22
    assert nir_cle("2920782045033") == 55


def test_nir_valide_accepte_les_nir_du_corpus():
    assert nir_valide("1 80 03 74 118 218 22")
    assert nir_valide("2 92 07 82 045 033 55")
    assert nir_valide("180037411821822")


def test_nir_valide_rejette_une_cle_fausse():
    assert not nir_valide("1 80 03 74 118 218 23")
    assert not nir_valide("2 92 07 82 045 033 54")


def test_nir_valide_gere_la_corse():
    # Département 2A : le A vaut 0 et le nombre est diminué de 1 000 000.
    corps = "1 80 03 2A 118 218".replace(" ", "")
    cle = nir_cle(corps)
    assert nir_valide(f"{corps}{cle:02d}")
    assert not nir_valide(f"{corps}{(cle % 97) + 1:02d}")
    # Département 2B : le B vaut 0 et le nombre est diminué de 2 000 000.
    corps_b = "2 92 07 2B 045 033".replace(" ", "")
    cle_b = nir_cle(corps_b)
    assert nir_valide(f"{corps_b}{cle_b:02d}")


def test_nir_valide_rejette_les_longueurs_fausses():
    assert not nir_valide("1 80 03 74 118 218")
    assert not nir_valide("")
    assert not nir_valide("abcdefghijklmno")


# ---------------------------------------------------------------------------
# Luhn : SIREN (9 chiffres) et SIRET (14 chiffres)
# ---------------------------------------------------------------------------


def test_luhn_valide_siren_et_siret_du_corpus():
    assert luhn_valide("824750004")
    assert luhn_valide("82475000400007")


def test_luhn_rejette_un_chiffre_altere():
    assert not luhn_valide("824750005")
    assert not luhn_valide("82475000400008")


def test_luhn_rejette_le_non_numerique():
    assert not luhn_valide("82475OOO4")
    assert not luhn_valide("")


# ---------------------------------------------------------------------------
# IBAN : contrôle mod 97 (ISO 13616)
# ---------------------------------------------------------------------------


def test_iban_valide_celui_du_corpus():
    assert iban_valide("FR11 3000 3000 1100 0987 6543 185")
    assert iban_valide("FR1130003000110009876543185")


def test_iban_rejette_une_cle_fausse():
    assert not iban_valide("FR12 3000 3000 1100 0987 6543 185")


def test_iban_rejette_les_formats_invalides():
    assert not iban_valide("FR11")
    assert not iban_valide("")
