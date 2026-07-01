"""Pseudonymisation réversible : détection C1 puis substitution par placeholders.

La ré-identification de ce module est l'opération brute (remplacement des
placeholders connus) ; le contrôle d'intégrité des réponses IA (placeholders
inconnus ou manquants, REQ-006) est porté par le module integrity.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .detection import EntiteDetectee, Moteur, detecter
from .vault import Vault

MOTIF_PLACEHOLDER = re.compile(r"\[[A-Z_]+_\d{3,}\]")


@dataclass(frozen=True)
class Remplacement:
    entite: EntiteDetectee
    placeholder: str


@dataclass(frozen=True)
class ResultatPseudonymisation:
    texte: str
    remplacements: list[Remplacement]
    comptes_par_type: dict[str, int]


class Pseudonymiseur:
    def __init__(self, vault: Vault, moteurs: Sequence[Moteur] = ()) -> None:
        self._vault = vault
        self._moteurs = list(moteurs)

    def pseudonymiser(self, texte: str, dossier_id: str) -> ResultatPseudonymisation:
        entites = detecter(texte, moteurs=self._moteurs)
        remplacements = [
            Remplacement(
                entite=e,
                placeholder=self._vault.placeholder_pour(dossier_id, e.type, e.valeur),
            )
            for e in entites
        ]
        # Substitution de la fin vers le début pour préserver les positions.
        pseudonymise = texte
        for r in sorted(remplacements, key=lambda r: r.entite.debut, reverse=True):
            pseudonymise = (
                pseudonymise[: r.entite.debut] + r.placeholder + pseudonymise[r.entite.fin :]
            )
        return ResultatPseudonymisation(
            texte=pseudonymise,
            remplacements=remplacements,
            comptes_par_type=dict(Counter(e.type for e in entites)),
        )

    def placeholders_connus(self, dossier_id: str) -> set[str]:
        return self._vault.placeholders_connus(dossier_id)

    def reidentifier(self, texte: str, dossier_id: str) -> str:
        def substituer(m: re.Match[str]) -> str:
            valeur = self._vault.valeur_pour(dossier_id, m.group(0))
            return valeur if valeur is not None else m.group(0)

        return MOTIF_PLACEHOLDER.sub(substituer, texte)
