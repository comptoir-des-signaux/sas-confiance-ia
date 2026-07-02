"""Pseudonymisation réversible : détection C1 puis substitution par placeholders.

La ré-identification de ce module est l'opération brute (remplacement des
placeholders connus) ; le contrôle d'intégrité des réponses IA (placeholders
inconnus ou manquants, REQ-006) est porté par le module integrity.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from .coreference import TYPE_PERSONNE, ResolveurCoreference
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
    # Placeholders PERSONNE créés faute de rattachement sûr (F4) : à revoir.
    ambiguites: list[str] = field(default_factory=list)


class Pseudonymiseur:
    def __init__(
        self, vault: Vault, moteurs: Sequence[Moteur] = (), coreference: bool = True
    ) -> None:
        self._vault = vault
        self._moteurs = list(moteurs)
        # C4 (REQ-011) : actif par défaut ; sans lui, l'aller-retour reste
        # exact au caractère près mais chaque forme de surface devient une
        # entité distincte (arbitrage Q1, docs/specs/QUESTIONS.md).
        self._resolveur = ResolveurCoreference(vault) if coreference else None

    def _placeholder_pour(self, dossier_id: str, entite: EntiteDetectee) -> str:
        if self._resolveur is not None and entite.type == TYPE_PERSONNE:
            return self._resolveur.placeholder_pour(dossier_id, entite.valeur)
        return self._vault.placeholder_pour(dossier_id, entite.type, entite.valeur)

    def pseudonymiser(self, texte: str, dossier_id: str) -> ResultatPseudonymisation:
        entites = detecter(texte, moteurs=self._moteurs)
        remplacements = [
            Remplacement(entite=e, placeholder=self._placeholder_pour(dossier_id, e))
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
            ambiguites=(
                sorted(self._resolveur.ambiguites(dossier_id)) if self._resolveur else []
            ),
        )

    def placeholders_connus(self, dossier_id: str) -> set[str]:
        return self._vault.placeholders_connus(dossier_id)

    def reidentifier(self, texte: str, dossier_id: str) -> str:
        def substituer(m: re.Match[str]) -> str:
            valeur = self._vault.valeur_pour(dossier_id, m.group(0))
            return valeur if valeur is not None else m.group(0)

        return MOTIF_PLACEHOLDER.sub(substituer, texte)
