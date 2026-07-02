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
from .politique import (
    ACTION_CONSERVER,
    ACTION_MASQUER,
    ACTION_REVUE,
    Politique,
)
from .vault import Vault, etiquette

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
    # Placeholders dont la politique du type est « revue » (Lot 14) : masqués
    # par prudence, à faire relire par un humain.
    en_revue: list[str] = field(default_factory=list)


class Pseudonymiseur:
    def __init__(
        self,
        vault: Vault,
        moteurs: Sequence[Moteur] = (),
        coreference: bool = True,
        politique: Politique | None = None,
    ) -> None:
        self._vault = vault
        self._moteurs = list(moteurs)
        # Défauts d'instance (SAS_POLITIQUES) ; la politique du dossier,
        # stockée dans le vault, les surcharge type par type (Lot 14).
        self._politique_defaut = politique or Politique()
        # C4 (REQ-011) : actif par défaut ; sans lui, l'aller-retour reste
        # exact au caractère près mais chaque forme de surface devient une
        # entité distincte (arbitrage Q1, docs/specs/QUESTIONS.md).
        self._resolveur = ResolveurCoreference(vault) if coreference else None

    @property
    def vault(self) -> Vault:
        return self._vault

    def _placeholder_pour(self, dossier_id: str, entite: EntiteDetectee) -> str:
        if self._resolveur is not None and entite.type == TYPE_PERSONNE:
            return self._resolveur.placeholder_pour(dossier_id, entite.valeur)
        return self._vault.placeholder_pour(dossier_id, entite.type, entite.valeur)

    def politique_pour(self, dossier_id: str) -> Politique:
        stockee = self._vault.politique_dossier(dossier_id)
        if stockee is None:
            return self._politique_defaut
        return self._politique_defaut.surcharger(Politique.depuis_dict(stockee))

    def pseudonymiser(self, texte: str, dossier_id: str) -> ResultatPseudonymisation:
        ambiguites_avant = (
            self._resolveur.ambiguites(dossier_id) if self._resolveur else set()
        )
        politique = self.politique_pour(dossier_id)
        entites = detecter(texte, moteurs=self._moteurs)
        # La politique s'applique entre la détection et le remplacement : une
        # entité conservée reste comptée (le journal documente ce qui a été
        # vu) mais ne touche ni le texte ni le vault.
        remplacements = []
        en_revue = []
        for e in entites:
            action = politique.action_pour(e.type)
            if action == ACTION_CONSERVER:
                continue
            if action == ACTION_MASQUER:
                # Marqueur sans numéro : aucune entrée vault, irréversible.
                remplacements.append(
                    Remplacement(entite=e, placeholder=f"[{etiquette(e.type)}]")
                )
                continue
            remplacement = Remplacement(
                entite=e, placeholder=self._placeholder_pour(dossier_id, e)
            )
            remplacements.append(remplacement)
            if action == ACTION_REVUE:
                en_revue.append(remplacement.placeholder)
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
            # Seules les ambiguïtés apparues pendant CET appel : le cumul du
            # dossier reste consultable via le résolveur.
            ambiguites=(
                sorted(self._resolveur.ambiguites(dossier_id) - ambiguites_avant)
                if self._resolveur
                else []
            ),
            en_revue=sorted(set(en_revue)),
        )

    def placeholders_connus(self, dossier_id: str) -> set[str]:
        return self._vault.placeholders_connus(dossier_id)

    def reidentifier(self, texte: str, dossier_id: str) -> str:
        def substituer(m: re.Match[str]) -> str:
            valeur = self._vault.valeur_pour(dossier_id, m.group(0))
            return valeur if valeur is not None else m.group(0)

        return MOTIF_PLACEHOLDER.sub(substituer, texte)
