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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .validators import iban_valide, luhn_valide, nir_valide

# Priorité de résolution des chevauchements (REQ-016). Les types déterministes
# (C1, clés validées ou contexte explicite) priment tous sur les types
# probabilistes du NER (PERSONNE > ORGANISATION > LIEU) : une couche moins
# fiable ne dégrade jamais ce qu'une couche plus fiable a établi (02-AI-SPEC §1).
# Les types *_SUSPECT (arbitrage Q4 : motif structurel à clé invalide masqué
# en contexte explicite) suivent immédiatement leur type validé ; le SIRET
# suspect prime sur un préfixe SIREN à Luhn valide (sinon le NIC fuit), et
# tous priment sur CARTE_BANCAIRE (un NIR fictif peut passer Luhn).
PRIORITE = [
    "FR_NIR",
    "FR_SIRET",
    "FR_NIR_SUSPECT",
    "FR_SIRET_SUSPECT",
    "FR_SIREN",
    "FR_SIREN_SUSPECT",
    "IBAN",
    "IBAN_SUSPECT",
    "RPPS",
    "MATRICULE",
    "EMAIL",
    "TELEPHONE",
    "ADRESSE",
    "CODE_POSTAL",
    "CARTE_BANCAIRE",
    "PLAQUE",
    "REFERENCE_DOSSIER",
    "DATE_NAISSANCE",
    "PERSONNE",
    "ORGANISATION",
    "LIEU",
]


@dataclass(frozen=True)
class EntiteDetectee:
    type: str
    debut: int
    fin: int
    score: float
    valeur: str


class Moteur(Protocol):
    """Une couche de détection supplémentaire (NER C2, juge C3) : mêmes candidats."""

    def reconnaitre(self, texte: str) -> list[EntiteDetectee]: ...


@dataclass(frozen=True)
class Reconnaisseur:
    type: str
    motif: re.Pattern[str]
    score: float
    groupe: int = 0
    validation: Callable[[str], bool] | None = None
    # Contexte requis AVANT le motif (fenêtre de caractères) : porte les
    # reconnaisseurs fail-safe de Q4 (motif structurel masqué seulement si
    # un mot explicite le précède : « NIR », « SIRET », « matricule »...).
    contexte: re.Pattern[str] | None = None
    fenetre_contexte: int = 40

    def reconnaitre(self, texte: str) -> list[EntiteDetectee]:
        entites = []
        for m in self.motif.finditer(texte):
            valeur = m.group(self.groupe)
            if self.validation is not None and not self.validation(valeur):
                continue
            if self.contexte is not None:
                debut = m.start(self.groupe)
                fenetre = texte[max(0, debut - self.fenetre_contexte) : debut]
                if not self.contexte.search(fenetre):
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


# Motifs structurels partagés entre le type validé et son suspect (Q4).
_MOTIF_NIR = re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?(?:\d{2}|2[AB])\s?\d{3}\s?\d{3}\s?\d{2}\b")
_MOTIF_SIRET = re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\s?\d{5}\b")
_MOTIF_SIREN = re.compile(r"\b\d{3}\s?\d{3}\s?\d{3}\b")
_MOTIF_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b")

_CONTEXTE_NIR = re.compile(r"(?i)\bNIR\b|s[ée]curit[ée]\s+sociale|\bINSEE\b")
_CONTEXTE_SIRET = re.compile(r"(?i)\bSIRET\b")
_CONTEXTE_SIREN = re.compile(r"(?i)\bSIREN\b")
_CONTEXTE_IBAN = re.compile(r"(?i)\bIBAN\b|\bRIB\b|compte bancaire")

RECONNAISSEURS: list[Reconnaisseur] = [
    Reconnaisseur(
        type="FR_NIR",
        motif=_MOTIF_NIR,
        score=0.95,
        validation=nir_valide,
    ),
    Reconnaisseur(
        type="FR_NIR_SUSPECT",
        motif=_MOTIF_NIR,
        score=0.7,
        contexte=_CONTEXTE_NIR,
    ),
    Reconnaisseur(
        type="FR_SIRET_SUSPECT",
        motif=_MOTIF_SIRET,
        score=0.7,
        contexte=_CONTEXTE_SIRET,
    ),
    Reconnaisseur(
        type="FR_SIREN_SUSPECT",
        motif=_MOTIF_SIREN,
        score=0.65,
        contexte=_CONTEXTE_SIREN,
    ),
    Reconnaisseur(
        type="IBAN_SUSPECT",
        motif=_MOTIF_IBAN,
        score=0.7,
        contexte=_CONTEXTE_IBAN,
        # « IBAN communiqué pour le remboursement des frais médicaux : ... » :
        # le mot de contexte peut être loin du motif.
        fenetre_contexte=80,
    ),
    Reconnaisseur(
        type="RPPS",
        motif=re.compile(r"\b\d{11}\b"),
        score=0.9,
        # Clé Luhn non exigée (Q4) : en contexte RPPS explicite, la fuite
        # d'un numéro de professionnel de santé prime sur la clé.
        contexte=re.compile(r"(?i)\bRPPS\b"),
        fenetre_contexte=20,
    ),
    Reconnaisseur(
        type="MATRICULE",
        motif=re.compile(r"\b\d{2,6}-\d{2,6}\b"),
        score=0.8,
        contexte=re.compile(r"(?i)\bmatricule\b"),
        fenetre_contexte=20,
    ),
    Reconnaisseur(
        type="CODE_POSTAL",
        # Cinq chiffres immédiatement suivis d'un mot capitalisé : un code
        # postal devant sa commune (« 82000 Montauban »), ré-identifiant en
        # combinaison même quand la commune est masquée par le NER.
        motif=re.compile(r"\b(\d{5})(?=\s+[A-ZÀÂÉÈÊÎÔÙÛ])"),
        score=0.75,
        groupe=1,
    ),
    Reconnaisseur(
        type="FR_SIRET",
        motif=_MOTIF_SIRET,
        score=0.9,
        validation=lambda v: luhn_valide(_sans_separateurs(v)),
    ),
    Reconnaisseur(
        type="FR_SIREN",
        motif=_MOTIF_SIREN,
        score=0.85,
        validation=lambda v: luhn_valide(_sans_separateurs(v)),
    ),
    Reconnaisseur(
        type="IBAN",
        motif=_MOTIF_IBAN,
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

# Caractères de bordure retirés des résidus de rognage (jamais de l'entité
# d'origine) : blancs et ponctuation de liaison.
_BORDURES = " \t\n\r,;:.()!?«»\"'"


def _rogner(entite: EntiteDetectee, retenues: list[EntiteDetectee]) -> list[EntiteDetectee]:
    """Sous-empans de l'entité non couverts par les retenues, bordures épurées.

    REQ-001 : un candidat chevauchant n'est jamais écarté en bloc, sinon son
    résidu (« Marie Martin » dans un empan NER englobant aussi l'email déjà
    retenu) resterait en clair dans le texte pseudonymisé.
    """
    libres = [(entite.debut, entite.fin)]
    for retenue in retenues:
        suivants = []
        for debut, fin in libres:
            if retenue.fin <= debut or retenue.debut >= fin:
                suivants.append((debut, fin))
                continue
            if debut < retenue.debut:
                suivants.append((debut, retenue.debut))
            if retenue.fin < fin:
                suivants.append((retenue.fin, fin))
        libres = suivants
    residus = []
    for debut, fin in libres:
        fragment = entite.valeur[debut - entite.debut : fin - entite.debut]
        epure = fragment.strip(_BORDURES)
        if not epure:
            continue
        debut_epure = debut + (len(fragment) - len(fragment.lstrip(_BORDURES)))
        residus.append(
            EntiteDetectee(
                type=entite.type,
                debut=debut_epure,
                fin=debut_epure + len(epure),
                score=entite.score,
                valeur=epure,
            )
        )
    return residus


def _resoudre_chevauchements(candidats: list[EntiteDetectee]) -> list[EntiteDetectee]:
    """Garde, pour chaque zone du texte, l'entité la plus prioritaire (REQ-016).

    À priorité égale, la plus longue puis la mieux notée l'emporte. Une
    entité moins prioritaire qui déborde d'une entité retenue est rognée à
    ses parties libres (jamais rejetée en bloc, REQ-001).
    """
    ordonnes = sorted(
        candidats,
        key=lambda e: (_RANG.get(e.type, len(PRIORITE)), -(e.fin - e.debut), -e.score),
    )
    retenues: list[EntiteDetectee] = []
    for entite in ordonnes:
        if all(entite.fin <= r.debut or entite.debut >= r.fin for r in retenues):
            retenues.append(entite)
        else:
            retenues.extend(_rogner(entite, retenues))
    return sorted(retenues, key=lambda e: e.debut)


# Types probabilistes dont les empans contigus fusionnent : le NER découpe
# parfois une même mention (« avenue de l' » + « Europe »), produisant deux
# placeholders collés dans le texte pseudonymisé. Les types déterministes ne
# fusionnent jamais (deux NIR côte à côte restent deux entités).
_TYPES_FUSIONNABLES = {"PERSONNE", "ORGANISATION", "LIEU"}
_LIANTS = " '’-"


def _fusionner_adjacentes(
    entites: list[EntiteDetectee], texte: str
) -> list[EntiteDetectee]:
    fusionnees: list[EntiteDetectee] = []
    for entite in entites:
        if fusionnees:
            precedente = fusionnees[-1]
            ecart = texte[precedente.fin : entite.debut]
            if (
                entite.type == precedente.type
                and entite.type in _TYPES_FUSIONNABLES
                and len(ecart) <= 1
                and all(c in _LIANTS for c in ecart)
            ):
                fusionnees[-1] = EntiteDetectee(
                    type=precedente.type,
                    debut=precedente.debut,
                    fin=entite.fin,
                    score=min(precedente.score, entite.score),
                    valeur=texte[precedente.debut : entite.fin],
                )
                continue
        fusionnees.append(entite)
    return fusionnees


def detecter(texte: str, moteurs: Iterable[Moteur] = ()) -> list[EntiteDetectee]:
    """Détection : reconnaisseurs C1 plus moteurs fournis, puis résolution REQ-016."""
    candidats: list[EntiteDetectee] = []
    for reconnaisseur in RECONNAISSEURS:
        candidats.extend(reconnaisseur.reconnaitre(texte))
    for moteur in moteurs:
        candidats.extend(moteur.reconnaitre(texte))
    return _fusionner_adjacentes(_resoudre_chevauchements(candidats), texte)
