"""Pseudonymisation réversible : détection C1 puis substitution par placeholders.

La ré-identification de ce module est l'opération brute (remplacement des
placeholders connus) ; le contrôle d'intégrité des réponses IA (placeholders
inconnus ou manquants, REQ-006) est porté par le module integrity.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from .coreference import TYPE_PERSONNE, ResolveurCoreference, _genre_civilite
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
    # Rendu surrogate (REQ-012) : le texte porte ce nom factice, le vault et
    # le contrôle d'intégrité continuent de raisonner sur le placeholder.
    surrogate: str | None = None


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
        generateur_surrogates=None,
    ) -> None:
        self._vault = vault
        self._moteurs = list(moteurs)
        # Créé paresseusement au premier dossier en mode surrogate : Faker
        # n'est chargé que si l'option est utilisée.
        self._generateur_surrogates = generateur_surrogates
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
        if politique.surrogates:
            pseudonymise, remplacements = self._appliquer_surrogates(
                dossier_id, pseudonymise, remplacements
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

    def _appliquer_surrogates(
        self, dossier_id: str, texte: str, remplacements: list[Remplacement]
    ) -> tuple[str, list[Remplacement]]:
        """Rend les placeholders PERSONNE sous forme de noms factices (REQ-012).

        Le placeholder reste la clé du vault et du contrôle d'intégrité ; le
        surrogate n'est qu'un rendu, mémorisé dans le vault pour rester
        stable sur tout le dossier (y compris entre redémarrages).
        """
        if self._generateur_surrogates is None:
            from .surrogates import GenerateurSurrogates

            self._generateur_surrogates = GenerateurSurrogates()
        rendus = []
        for r in remplacements:
            if r.entite.type != TYPE_PERSONNE or not MOTIF_PLACEHOLDER.fullmatch(
                r.placeholder
            ):
                rendus.append(r)
                continue
            surrogate = self._vault.surrogate_pour(dossier_id, r.placeholder)
            if surrogate is None:
                surrogate = self._generateur_surrogates.nom_personne(
                    self._genre_connu(dossier_id, r.placeholder, r.entite.valeur),
                    interdits=self._noms_interdits(dossier_id),
                )
                self._vault.associer_surrogate(dossier_id, r.placeholder, surrogate)
            texte = texte.replace(r.placeholder, surrogate)
            rendus.append(
                Remplacement(entite=r.entite, placeholder=r.placeholder, surrogate=surrogate)
            )
        return texte, rendus

    def _genre_connu(self, dossier_id: str, placeholder: str, mention: str) -> str | None:
        """Genre porté par la mention courante ou une civilité déjà vue (C4)."""
        genre = _genre_civilite(mention)
        if genre is not None:
            return genre
        for forme, ph in self._vault.valeurs_pour_type(dossier_id, TYPE_PERSONNE).items():
            if ph == placeholder:
                genre = _genre_civilite(forme)
                if genre is not None:
                    return genre
        return None

    def _noms_interdits(self, dossier_id: str) -> set[str]:
        """Un surrogate ne reprend jamais un nom du dossier, réel ou factice :
        la ré-identification restituerait le mauvais nom à cet endroit."""
        return set(self._vault.valeurs_pour_type(dossier_id, TYPE_PERSONNE)) | set(
            self._vault.surrogates_dossier(dossier_id).values()
        )

    def placeholders_connus(self, dossier_id: str) -> set[str]:
        return self._vault.placeholders_connus(dossier_id)

    def restaurer_surrogates(self, texte: str, dossier_id: str) -> str:
        """Ramène les surrogates du dossier à leur placeholder [PERSONNE_NNN].

        Correspondance exacte uniquement, les plus longs d'abord : un
        surrogate altéré par le LLM (« Mme Roussel » pour « Camille
        Roussel ») n'est pas restauré, limite assumée de Q5.
        """
        surrogates = self._vault.surrogates_dossier(dossier_id)
        for placeholder, surrogate in sorted(
            surrogates.items(), key=lambda kv: -len(kv[1])
        ):
            texte = texte.replace(surrogate, placeholder)
        return texte

    def reidentifier(self, texte: str, dossier_id: str) -> str:
        def substituer(m: re.Match[str]) -> str:
            valeur = self._vault.valeur_pour(dossier_id, m.group(0))
            return valeur if valeur is not None else m.group(0)

        return MOTIF_PLACEHOLDER.sub(substituer, self.restaurer_surrogates(texte, dossier_id))
