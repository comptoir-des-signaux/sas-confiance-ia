"""Juge LLM local (Lot 13, C3, REQ-014).

Troisième couche de détection, la moins fiable et la plus couvrante
(02-AI-SPEC §1) : un LLM local (Ollama) relit le texte DÉJÀ pseudonymisé
par C1+C2 et signale les identifiants indirects restants (fonction rare,
petite commune, surnom, périphrase, combinaison ré-identifiante). Ses
candidats partent en revue humaine : jamais de remplacement direct en v1.

Le juge n'est pas un `Moteur` de détection (REQ-016) : il ne fournit pas de
positions fiables ni de candidats de remplacement, il signale. D'où une
interface distincte, sur la même abstraction `Backend` que le LLM applicatif
(REQ-013) : il tourne exclusivement en local et n'appelle jamais un service
distant (garde-fou réseau des tests).

Parade F7 (hallucinations) : sortie JSON stricte rejetée si non conforme,
score minimal configurable, placeholders déjà couverts filtrés.
"""

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from .backends import Backend, ErreurBackend
from .journal import Journal
from .pseudonymiseur import MOTIF_PLACEHOLDER

CONSIGNE_JUGE = (
    "Tu es le juge d'un sas de pseudonymisation. Le texte fourni a déjà été "
    "pseudonymisé : les jetons au format [TYPE_NNN] protègent des valeurs "
    "déjà traitées, ne les signale jamais. Ta mission : repérer les "
    "identifiants INDIRECTS restants qui permettraient de reconnaître une "
    "personne (fonction rare, petite commune, surnom, périphrase, matricule, "
    "combinaison ré-identifiante). Réponds UNIQUEMENT par un tableau JSON, "
    "sans aucun texte autour, dont chaque élément a exactement les clés "
    '"segment" (extrait exact du texte), "type_candidat", "justification" '
    '(une phrase) et "score" (nombre entre 0 et 1). Réponds [] si rien à '
    "signaler. Ne réécris pas le texte, ne réponds rien d'autre."
)

SCORE_MIN_DEFAUT = 0.5

_CLES_CANDIDAT = {"segment", "type_candidat", "justification", "score"}

# Épuration déterministe (pas une interprétation) : clôture de raisonnement
# des modèles pensants (qwen3) et barrière markdown autour du JSON.
_MOTIF_RAISONNEMENT = re.compile(r"\A\s*<think>.*?</think>", re.DOTALL)
_MOTIF_BARRIERE = re.compile(r"\A\s*```[a-z]*\s*(.*?)\s*```\s*\Z", re.DOTALL)


@dataclass(frozen=True)
class CandidatJuge:
    """Un identifiant indirect signalé pour revue humaine."""

    segment: str
    type_candidat: str
    justification: str
    score: float


class ErreurJuge(Exception):
    """Échec de la passe juge (backend ou sortie non conforme).

    Comme ErreurBackend : ne transporte jamais le texte analysé ni la sortie
    du modèle (elles peuvent citer des valeurs), seulement un type d'erreur
    et un message technique neutre (REQ-003).
    """

    def __init__(self, erreur_type: str, message: str) -> None:
        super().__init__(message)
        self.erreur_type = erreur_type


class JugeLLM:
    def __init__(
        self,
        backend: Backend,
        modele: str,
        score_min: float = SCORE_MIN_DEFAUT,
    ) -> None:
        self.backend = backend
        self.modele = modele
        self.score_min = score_min

    def signaler(self, texte: str) -> list[CandidatJuge]:
        """Relit un texte pseudonymisé, renvoie les candidats à revoir."""
        payload = {
            "model": self.modele,
            "messages": [
                {"role": "system", "content": CONSIGNE_JUGE},
                {"role": "user", "content": texte},
            ],
            # Déterminisme maximal pour une passe d'audit rejouable.
            "temperature": 0,
        }
        try:
            reponse = self.backend.completer(payload)
        except ErreurBackend as exc:
            raise ErreurJuge(exc.erreur_type, "échec de l'appel au juge") from exc
        return self._interpreter(reponse.contenu)

    def _interpreter(self, contenu: str) -> list[CandidatJuge]:
        candidats: list[CandidatJuge] = []
        for element in _elements_conformes(contenu):
            if element["score"] < self.score_min:
                continue
            if MOTIF_PLACEHOLDER.fullmatch(element["segment"].strip()):
                # Déjà couvert par C1+C2 : le signaler serait du bruit pur.
                continue
            candidats.append(
                CandidatJuge(
                    segment=element["segment"],
                    type_candidat=element["type_candidat"],
                    justification=element["justification"],
                    score=float(element["score"]),
                )
            )
        return candidats


def executer_passe(
    juge: "JugeLLM | None",
    texte: str,
    *,
    journal: Journal,
    requete_id: str,
    dossier_id: str,
) -> dict[str, Any]:
    """Passe juge tolérante aux pannes, partagée par le proxy et l'UI.

    Le juge est optionnel et dégradable (REQ-014) : son échec est journalisé
    (type d'erreur seul) et n'interrompt jamais le flux ; la couverture est
    alors celle de C1+C2, ce que le bloc renvoyé documente.
    """
    bloc: dict[str, Any] = {"actif": juge is not None, "candidats": []}
    if juge is None:
        return bloc
    try:
        bloc["candidats"] = [asdict(candidat) for candidat in juge.signaler(texte)]
    except ErreurJuge as erreur:
        bloc["erreur_type"] = erreur.erreur_type
        journal.enregistrer(
            requete_id=requete_id,
            dossier_id=dossier_id,
            backend=type(juge.backend).__name__,
            modele=juge.modele,
            statut="erreur_juge",
            erreur_type=erreur.erreur_type,
        )
    return bloc


def _elements_conformes(contenu: str) -> list[dict[str, Any]]:
    """Valide strictement la sortie du juge : liste conforme ou rejet total."""
    epure = _MOTIF_RAISONNEMENT.sub("", contenu)
    barriere = _MOTIF_BARRIERE.match(epure)
    if barriere:
        epure = barriere.group(1)
    try:
        elements = json.loads(epure)
    except ValueError:
        raise ErreurJuge("SortieJugeInvalide", "sortie du juge non JSON, rejetée") from None
    if not isinstance(elements, list):
        raise ErreurJuge("SortieJugeInvalide", "sortie du juge non conforme (liste attendue)")
    for element in elements:
        if not isinstance(element, dict) or set(element) != _CLES_CANDIDAT:
            raise ErreurJuge(
                "SortieJugeInvalide",
                "sortie du juge non conforme (clés attendues : "
                "segment, type_candidat, justification, score)",
            )
        for cle in ("segment", "type_candidat", "justification"):
            if not isinstance(element[cle], str) or not element[cle].strip():
                raise ErreurJuge(
                    "SortieJugeInvalide", f"sortie du juge non conforme ({cle} invalide)"
                )
        score = element["score"]
        if isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= 1:
            raise ErreurJuge(
                "SortieJugeInvalide", "sortie du juge non conforme (score hors [0, 1])"
            )
    return elements
