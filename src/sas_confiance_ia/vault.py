"""Vault : table de correspondance placeholder ↔ valeur, scopée par dossier.

Le vault ne quitte jamais la zone de confiance (invariant du 00-CONTEXT).
Ce module fournit l'interface commune et l'implémentation en mémoire du
Lot 4 ; le vault persistant chiffré arrive au Lot 5 derrière la même interface.
"""

from collections import defaultdict
from typing import Protocol

# Étiquettes lisibles utilisées dans les placeholders, par type détecté.
ETIQUETTES = {
    "FR_NIR": "NIR",
    "FR_SIRET": "SIRET",
    "FR_SIREN": "SIREN",
    "IBAN": "IBAN",
    "EMAIL": "EMAIL",
    "TELEPHONE": "TELEPHONE",
    "CARTE_BANCAIRE": "CARTE",
    "PLAQUE": "PLAQUE",
    "REFERENCE_DOSSIER": "REFERENCE",
    "DATE_NAISSANCE": "DATE_NAISSANCE",
    "PERSONNE": "PERSONNE",
    "ORGANISATION": "ORGANISATION",
    "LIEU": "LIEU",
    "ADRESSE": "ADRESSE",
}


def etiquette(type_: str) -> str:
    return ETIQUETTES.get(type_, type_)


class Vault(Protocol):
    """Interface commune aux vaults (mémoire, chiffré persistant)."""

    def placeholder_pour(self, dossier_id: str, type_: str, valeur: str) -> str: ...

    def valeur_pour(self, dossier_id: str, placeholder: str) -> str | None: ...

    def placeholders_connus(self, dossier_id: str) -> set[str]: ...


class VaultMemoire:
    """Vault en mémoire : correspondances et compteurs par dossier et par type."""

    def __init__(self) -> None:
        # dossier -> valeur (par type) -> placeholder
        self._par_valeur: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
        # dossier -> placeholder -> valeur
        self._par_placeholder: dict[str, dict[str, str]] = defaultdict(dict)
        # dossier -> étiquette -> dernier numéro attribué
        self._compteurs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def placeholder_pour(self, dossier_id: str, type_: str, valeur: str) -> str:
        cle = (type_, valeur)
        existant = self._par_valeur[dossier_id].get(cle)
        if existant is not None:
            return existant
        nom = etiquette(type_)
        self._compteurs[dossier_id][nom] += 1
        placeholder = f"[{nom}_{self._compteurs[dossier_id][nom]:03d}]"
        self._par_valeur[dossier_id][cle] = placeholder
        self._par_placeholder[dossier_id][placeholder] = valeur
        return placeholder

    def valeur_pour(self, dossier_id: str, placeholder: str) -> str | None:
        return self._par_placeholder[dossier_id].get(placeholder)

    def placeholders_connus(self, dossier_id: str) -> set[str]:
        return set(self._par_placeholder[dossier_id])
