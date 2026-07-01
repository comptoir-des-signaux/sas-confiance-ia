"""Validateurs français purs : NIR, Luhn (SIREN / SIRET), IBAN.

Fonctions sans état ni dépendance : elles valident des chaînes déjà repérées
par les reconnaisseurs. La logique NIR (clé de contrôle, cas Corse 2A/2B) et
Luhn reprend le travail de Romain Bochet (rbochet/amo-presidio), réutilisé
avec son accord.
"""

import re

_NON_NIR = re.compile(r"[^0-9AB]")


def luhn_valide(nombre: str) -> bool:
    """Contrôle de Luhn, utilisé pour SIREN (9 chiffres) et SIRET (14 chiffres)."""
    if not nombre.isdigit():
        return False
    somme = 0
    for i, c in enumerate(reversed(nombre)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        somme += d
    return somme % 10 == 0


def nir_cle(corps13: str) -> int:
    """Clé de contrôle du NIR sur ses 13 premiers caractères.

    Cas Corse : 2A vaut 0 avec retrait de 1 000 000 ; 2B vaut 0 avec retrait
    de 2 000 000 (règle officielle de l'insee).
    """
    s = corps13.upper()
    if "A" in s:
        n = int(s.replace("A", "0")) - 1_000_000
    elif "B" in s:
        n = int(s.replace("B", "0")) - 2_000_000
    else:
        n = int(s)
    return 97 - (n % 97)


def nir_valide(candidat: str) -> bool:
    """Vrai si la chaîne est un NIR complet (15 caractères) à clé exacte."""
    chaine = _NON_NIR.sub("", candidat.upper())
    if len(chaine) != 15:
        return False
    corps, cle = chaine[:13], chaine[13:]
    try:
        return nir_cle(corps) == int(cle)
    except ValueError:
        return False


def iban_valide(candidat: str) -> bool:
    """Contrôle mod 97 de l'ISO 13616 (tous pays, dont FR)."""
    chaine = re.sub(r"\s", "", candidat).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", chaine):
        return False
    reordonne = chaine[4:] + chaine[:4]
    nombre = "".join(str(int(c, 36)) for c in reordonne)
    return int(nombre) % 97 == 1
