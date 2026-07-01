"""Détection déterministe des identifiants français (couche C1).

Reconnaisseurs en Python pur : regex spécialisées plus validation de clés
(NIR, Luhn, IBAN). La résolution des chevauchements applique la priorité du
03-SPEC (REQ-016) : en cas de recouvrement, le type le plus prioritaire gagne.
Les motifs NIR / SIRET / SIREN reprennent le travail de Romain Bochet
(rbochet/amo-presidio), réutilisé avec son accord.

L'interface (EntiteDetectee, detecter) est celle que la couche NER (Presidio,
Phase 1) devra alimenter à son tour : la Phase 0 reste sans modèle.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from .validators import iban_valide, luhn_valide, nir_valide

# Priorité de résolution des chevauchements (REQ-016). Les types absents de
# cette liste (couches NER et juge, Phase 1+) passeront après CARTE_BANCAIRE.
PRIORITE = [
    "FR_NIR",
    "FR_SIRET",
    "FR_SIREN",
    "IBAN",
    "EMAIL",
    "TELEPHONE",
    "ADRESSE",
    "CARTE_BANCAIRE",
    "PLAQUE",
    "REFERENCE_DOSSIER",
    "DATE_NAISSANCE",
]


@dataclass(frozen=True)
class EntiteDetectee:
    type: str
    debut: int
    fin: int
    score: float
    valeur: str


@dataclass(frozen=True)
class Reconnaisseur:
    type: str
    motif: re.Pattern[str]
    score: float
    groupe: int = 0
    validation: Callable[[str], bool] | None = None

    def reconnaitre(self, texte: str) -> list[EntiteDetectee]:
        entites = []
        for m in self.motif.finditer(texte):
            valeur = m.group(self.groupe)
            if self.validation is not None and not self.validation(valeur):
                continue
            entites.append(
                EntiteDetectee(
                    type=self.type,
                    debut=m.start(self.groupe),
                    fin=m.end(self.groupe),
                    score=self.score,
                    valeur=valeur,
                )
            )
        return entites


def _sans_separateurs(valeur: str) -> str:
    return re.sub(r"[\s.-]", "", valeur)


RECONNAISSEURS: list[Reconnaisseur] = [
    Reconnaisseur(
        type="FR_NIR",
        motif=re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?(?:\d{2}|2[AB])\s?\d{3}\s?\d{3}\s?\d{2}\b"),
        score=0.95,
        validation=nir_valide,
    ),
    Reconnaisseur(
        type="FR_SIRET",
        motif=re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\s?\d{5}\b"),
        score=0.9,
        validation=lambda v: luhn_valide(_sans_separateurs(v)),
    ),
    Reconnaisseur(
        type="FR_SIREN",
        motif=re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b"),
        score=0.85,
        validation=lambda v: luhn_valide(_sans_separateurs(v)),
    ),
    Reconnaisseur(
        type="IBAN",
        motif=re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b"),
        score=0.95,
        validation=iban_valide,
    ),
    Reconnaisseur(
        type="EMAIL",
        motif=re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
        score=0.95,
    ),
    Reconnaisseur(
        type="TELEPHONE",
        motif=re.compile(r"\b0[1-9](?:[ .-]?\d{2}){4}\b"),
        score=0.85,
    ),
    Reconnaisseur(
        type="CARTE_BANCAIRE",
        motif=re.compile(r"\b\d(?:[ -]?\d){12,15}\b"),
        score=0.6,
        validation=lambda v: luhn_valide(_sans_separateurs(v)),
    ),
    Reconnaisseur(
        type="PLAQUE",
        motif=re.compile(r"\b[A-Z]{2}-\d{3}-[A-Z]{2}\b"),
        score=0.8,
    ),
    Reconnaisseur(
        type="REFERENCE_DOSSIER",
        motif=re.compile(r"\b[A-Z]{2,5}-(?:\d{4}-)?\d{3,6}\b"),
        score=0.6,
    ),
    Reconnaisseur(
        type="DATE_NAISSANCE",
        motif=re.compile(r"\bn(?:ée|é)\s+le\s+(\d{1,2}(?:er)?\s+[a-zéèêûôîà]+\s+\d{4})"),
        score=0.85,
        groupe=1,
    ),
]

_RANG = {type_: i for i, type_ in enumerate(PRIORITE)}


def _resoudre_chevauchements(candidats: list[EntiteDetectee]) -> list[EntiteDetectee]:
    """Garde, pour chaque zone du texte, l'entité la plus prioritaire (REQ-016).

    À priorité égale, la plus longue puis la mieux notée l'emporte.
    """
    ordonnes = sorted(
        candidats,
        key=lambda e: (_RANG.get(e.type, len(PRIORITE)), -(e.fin - e.debut), -e.score),
    )
    retenues: list[EntiteDetectee] = []
    for entite in ordonnes:
        if all(entite.fin <= r.debut or entite.debut >= r.fin for r in retenues):
            retenues.append(entite)
    return sorted(retenues, key=lambda e: e.debut)


def detecter(texte: str) -> list[EntiteDetectee]:
    """Détection déterministe : reconnaisseurs C1 puis résolution REQ-016."""
    candidats: list[EntiteDetectee] = []
    for reconnaisseur in RECONNAISSEURS:
        candidats.extend(reconnaisseur.reconnaitre(texte))
    return _resoudre_chevauchements(candidats)
