"""Vault : table de correspondance placeholder ↔ valeur, scopée par dossier.

Le vault ne quitte jamais la zone de confiance (invariant du 00-CONTEXT).
Ce module fournit l'interface commune et l'implémentation en mémoire du
Lot 4 ; le vault persistant chiffré arrive au Lot 5 derrière la même interface.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet

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


def generer_cle() -> bytes:
    """Génère une clé de chiffrement Fernet (à conserver hors du dépôt)."""
    return Fernet.generate_key()


class VaultChiffre(VaultMemoire):
    """Vault persistant, chiffré au repos (REQ-004), compteurs durables (REQ-005).

    Le fichier ne contient que du chiffré Fernet (AES-128-CBC + HMAC). La clé
    vient de l'appelant : en production, keyring ou gestionnaire de secrets,
    jamais le dépôt ni les logs.
    """

    def __init__(self, chemin: Path | str, cle: bytes) -> None:
        super().__init__()
        self._chemin = Path(chemin)
        self._fernet = Fernet(cle)
        if self._chemin.exists():
            self._charger()

    def placeholder_pour(self, dossier_id: str, type_: str, valeur: str) -> str:
        deja_connu = (type_, valeur) in self._par_valeur[dossier_id]
        placeholder = super().placeholder_pour(dossier_id, type_, valeur)
        if not deja_connu:
            self._persister()
        return placeholder

    def purger(self, dossier_id: str) -> None:
        """Efface définitivement les correspondances d'un dossier (cadrage §9.6)."""
        self._par_valeur.pop(dossier_id, None)
        self._par_placeholder.pop(dossier_id, None)
        self._compteurs.pop(dossier_id, None)
        self._persister()

    def _persister(self) -> None:
        contenu = {
            "mappings": {
                dossier: dict(corr) for dossier, corr in self._par_placeholder.items()
            },
            "types": {
                dossier: {ph: t for (t, _v), ph in corr.items()}
                for dossier, corr in self._par_valeur.items()
            },
            "compteurs": {
                dossier: dict(compteurs) for dossier, compteurs in self._compteurs.items()
            },
        }
        octets = self._fernet.encrypt(json.dumps(contenu).encode("utf-8"))
        self._chemin.write_bytes(octets)

    def _charger(self) -> None:
        contenu = json.loads(self._fernet.decrypt(self._chemin.read_bytes()))
        for dossier, correspondances in contenu["mappings"].items():
            types = contenu["types"][dossier]
            for placeholder, valeur in correspondances.items():
                self._par_placeholder[dossier][placeholder] = valeur
                self._par_valeur[dossier][(types[placeholder], valeur)] = placeholder
        for dossier, compteurs in contenu["compteurs"].items():
            for nom, numero in compteurs.items():
                self._compteurs[dossier][nom] = numero
