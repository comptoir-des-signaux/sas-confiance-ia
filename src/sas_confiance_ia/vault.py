"""Vault : table de correspondance placeholder ↔ valeur, scopée par dossier.

Le vault ne quitte jamais la zone de confiance (invariant fondateur du projet).
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
    # Types fail-safe de Q4 : motif structurel à clé invalide, masqué en
    # contexte explicite ; l'étiquette distincte signale au réviseur que la
    # clé n'a pas validé (donnée fictive ou faute de frappe).
    "FR_NIR_SUSPECT": "NIR_SUSPECT",
    "FR_SIRET_SUSPECT": "SIRET_SUSPECT",
    "FR_SIREN_SUSPECT": "SIREN_SUSPECT",
    "IBAN_SUSPECT": "IBAN_SUSPECT",
    "RPPS": "RPPS",
    "MATRICULE": "MATRICULE",
    "CODE_POSTAL": "CODE_POSTAL",
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
    """Interface commune aux vaults (mémoire, chiffré persistant).

    Depuis le Lot 11 (coréférence), un placeholder peut posséder plusieurs
    formes de surface (alias) mais une seule valeur de restitution : la
    forme canonique (arbitrage Q1 de docs/specs/QUESTIONS.md).
    """

    def placeholder_pour(self, dossier_id: str, type_: str, valeur: str) -> str: ...

    def valeur_pour(self, dossier_id: str, placeholder: str) -> str | None: ...

    def placeholders_connus(self, dossier_id: str) -> set[str]: ...

    def valeurs_pour_type(self, dossier_id: str, type_: str) -> dict[str, str]: ...

    def associer_alias(
        self, dossier_id: str, type_: str, alias: str, placeholder: str
    ) -> None: ...

    def remplacer_valeur_canonique(
        self, dossier_id: str, type_: str, placeholder: str, valeur: str
    ) -> None: ...

    def marquer_dossier(self, dossier_id: str, mode: str) -> None: ...

    def mode_dossier(self, dossier_id: str) -> str | None: ...

    def un_dossier_serieux_existe(self) -> bool: ...

    def definir_politique(self, dossier_id: str, politique: dict) -> None: ...

    def politique_dossier(self, dossier_id: str) -> dict | None: ...


class VaultMemoire:
    """Vault en mémoire : correspondances et compteurs par dossier et par type."""

    def __init__(self) -> None:
        # dossier -> valeur (par type) -> placeholder
        self._par_valeur: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
        # dossier -> placeholder -> valeur
        self._par_placeholder: dict[str, dict[str, str]] = defaultdict(dict)
        # dossier -> étiquette -> dernier numéro attribué
        self._compteurs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # dossier -> mode (serieux / demo) : la séparation REQ-007 vit avec
        # les données, pas dans la mémoire du processus.
        self._modes: dict[str, str] = {}
        # dossier -> politique de remplacement (Lot 14) : elle vit avec les
        # données pour la même raison que le mode.
        self._politiques: dict[str, dict] = {}

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

    def valeurs_pour_type(self, dossier_id: str, type_: str) -> dict[str, str]:
        """Toutes les formes connues (canoniques et alias) d'un type donné."""
        return {
            valeur: placeholder
            for (t, valeur), placeholder in self._par_valeur[dossier_id].items()
            if t == type_
        }

    def associer_alias(self, dossier_id: str, type_: str, alias: str, placeholder: str) -> None:
        """Rattache une forme de surface supplémentaire à un placeholder existant."""
        self._par_valeur[dossier_id][(type_, alias)] = placeholder

    def remplacer_valeur_canonique(
        self, dossier_id: str, type_: str, placeholder: str, valeur: str
    ) -> None:
        """La restitution du placeholder devient cette forme (plus complète)."""
        self._par_placeholder[dossier_id][placeholder] = valeur
        self._par_valeur[dossier_id][(type_, valeur)] = placeholder

    def marquer_dossier(self, dossier_id: str, mode: str) -> None:
        self._modes[dossier_id] = mode

    def mode_dossier(self, dossier_id: str) -> str | None:
        return self._modes.get(dossier_id)

    def un_dossier_serieux_existe(self) -> bool:
        return any(mode == "serieux" for mode in self._modes.values())

    def definir_politique(self, dossier_id: str, politique: dict) -> None:
        self._politiques[dossier_id] = politique

    def politique_dossier(self, dossier_id: str) -> dict | None:
        return self._politiques.get(dossier_id)


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

    def associer_alias(self, dossier_id: str, type_: str, alias: str, placeholder: str) -> None:
        super().associer_alias(dossier_id, type_, alias, placeholder)
        self._persister()

    def remplacer_valeur_canonique(
        self, dossier_id: str, type_: str, placeholder: str, valeur: str
    ) -> None:
        super().remplacer_valeur_canonique(dossier_id, type_, placeholder, valeur)
        self._persister()

    def marquer_dossier(self, dossier_id: str, mode: str) -> None:
        super().marquer_dossier(dossier_id, mode)
        self._persister()

    def definir_politique(self, dossier_id: str, politique: dict) -> None:
        super().definir_politique(dossier_id, politique)
        self._persister()

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
            # Formes de surface qui ne sont pas la valeur canonique (Lot 11).
            "alias": {
                dossier: [
                    [t, valeur, ph]
                    for (t, valeur), ph in corr.items()
                    if self._par_placeholder[dossier].get(ph) != valeur
                ]
                for dossier, corr in self._par_valeur.items()
            },
            "compteurs": {
                dossier: dict(compteurs) for dossier, compteurs in self._compteurs.items()
            },
            "modes": dict(self._modes),
            "politiques": dict(self._politiques),
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
        # Lecture tolérante : les vaults antérieurs au Lot 11 n'ont pas d'alias.
        for dossier, triplets in contenu.get("alias", {}).items():
            for type_, valeur, placeholder in triplets:
                self._par_valeur[dossier][(type_, valeur)] = placeholder
        for dossier, compteurs in contenu["compteurs"].items():
            for nom, numero in compteurs.items():
                self._compteurs[dossier][nom] = numero
        self._modes.update(contenu.get("modes", {}))
        # Lecture tolérante : les vaults antérieurs au Lot 14 n'ont pas de politique.
        self._politiques.update(contenu.get("politiques", {}))
