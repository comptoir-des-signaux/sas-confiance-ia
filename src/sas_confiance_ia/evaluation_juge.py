"""Éval du juge LLM sur les canaris (02-AI-SPEC §4.3, REQ-014).

Les canaris (corpus/synthetique/06-canaris.md) sont des identifiants
indirects que C1 et C2 manquent par construction : fonction rare, petite
commune, surnom, périphrase, matricule. On mesure la fraction que le juge
signale, publiée sans seuil dur en v1 ; ce sous-corpus sert aussi de
non-régression au changement de modèle juge (F9).

La mesure se fait MANUELLEMENT contre un Ollama local, hors CI (les tests
n'appellent jamais le réseau). Procédure et mesure publiée :
docs/eval/evaluation-juge.md.

Usage :
  python -m sas_confiance_ia.evaluation_juge \
      --base-url http://127.0.0.1:11434/v1 --modele mistral-small:24b

L'appariement est volontairement souple (le juge cite rarement un extrait
mot pour mot) : inclusion dans un sens ou dans l'autre, ou majorité des
mots significatifs de l'extrait retrouvés dans le segment.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .juge import SCORE_MIN_DEFAUT, CandidatJuge, JugeLLM

CORPUS_CANARIS = Path("corpus/synthetique/06-canaris.md")
VERITE_CANARIS = Path("corpus/synthetique/verite-terrain-canaris.json")

_MOTS_COURTS = 3  # les mots de 3 lettres ou moins ne discriminent rien
# Mots-outils français de plus de 3 lettres : sans ce filtre, « dans le
# même bureau » apparie « dans le même temps » et la mesure F9 se gonfle.
_MOTS_VIDES = {
    "dans", "plus", "même", "meme", "pour", "avec", "sans", "sous", "chez",
    "tout", "tous", "toute", "toutes", "cette", "cettes", "leur", "leurs",
    "elle", "elles", "vous", "nous", "être", "etre", "avoir", "fait",
    "entre", "vers", "depuis", "dont", "aussi", "comme", "mais", "donc",
    "alors", "ainsi", "après", "apres", "avant", "encore", "était", "etait",
}


@dataclass(frozen=True)
class ResultatCanaris:
    signales: list[str]
    manques: list[str]
    taux: float
    candidats_total: int
    candidats: tuple[CandidatJuge, ...] = ()


def _normaliser(texte: str) -> str:
    return re.sub(r"\s+", " ", texte.casefold()).strip()


def _mots_significatifs(texte: str) -> set[str]:
    return {
        mot
        for mot in re.findall(r"\w+", _normaliser(texte))
        if len(mot) > _MOTS_COURTS and mot not in _MOTS_VIDES
    }


def _candidat_correspondant(
    canari: dict[str, Any],
    candidats: list[CandidatJuge],
    exclus: set[int],
) -> int | None:
    """Indice du premier candidat libre qui recouvre un extrait du canari.

    Deux passes : l'inclusion textuelle (forte) d'abord, la majorité de
    mots significatifs (souple) ensuite, pour qu'un appariement faible ne
    consomme pas un candidat qu'un autre canari apparie fortement.
    """
    extraits = [(_normaliser(e), _mots_significatifs(e)) for e in canari["extraits"]]
    for extrait_norme, _ in extraits:
        for i, candidat in enumerate(candidats):
            if i in exclus:
                continue
            segment_norme = _normaliser(candidat.segment)
            if extrait_norme in segment_norme or segment_norme in extrait_norme:
                return i
    for _, mots_extrait in extraits:
        if not mots_extrait:
            continue
        for i, candidat in enumerate(candidats):
            if i in exclus:
                continue
            communs = mots_extrait & _mots_significatifs(candidat.segment)
            if len(communs) * 2 >= len(mots_extrait):
                return i
    return None


def canari_signale(canari: dict[str, Any], candidats: list[CandidatJuge]) -> bool:
    """Vrai si un candidat du juge recouvre l'un des extraits du canari."""
    return _candidat_correspondant(canari, candidats, set()) is not None


def charger_canaris(chemin: Path) -> list[dict[str, Any]]:
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    # Les clés `_commentaire` des JSON du corpus ne sont pas des données.
    return [
        {cle: valeur for cle, valeur in canari.items() if not cle.startswith("_")}
        for canari in donnees["canaris"]
    ]


def evaluer_juge(
    juge: JugeLLM,
    texte_pseudonymise: str,
    canaris: list[dict[str, Any]],
) -> ResultatCanaris:
    candidats = juge.signaler(texte_pseudonymise)
    # Affectation 1:1 : un candidat ne valide qu'un seul canari, sinon un
    # signalement vague gonflerait la mesure par appariement croisé.
    exclus: set[int] = set()
    signales = []
    for canari in canaris:
        indice = _candidat_correspondant(canari, candidats, exclus)
        if indice is not None:
            exclus.add(indice)
            signales.append(canari["id"])
    manques = [c["id"] for c in canaris if c["id"] not in signales]
    return ResultatCanaris(
        signales=signales,
        manques=manques,
        taux=len(signales) / len(canaris) if canaris else 0.0,
        candidats_total=len(candidats),
        candidats=tuple(candidats),
    )


def tableau_markdown(resultat: ResultatCanaris) -> str:
    lignes = ["| Canari | Signalé |", "|---|---|"]
    lignes += [f"| {id_} | oui |" for id_ in resultat.signales]
    lignes += [f"| {id_} | non |" for id_ in resultat.manques]
    total = len(resultat.signales) + len(resultat.manques)
    lignes.append(
        f"\nSignalés : {len(resultat.signales)}/{total} "
        f"({resultat.taux:.0%}), {resultat.candidats_total} candidats émis."
    )
    return "\n".join(lignes)


def _principal() -> None:
    import argparse

    from .backends import BackendOpenAICompatible
    from .pseudonymiseur import Pseudonymiseur
    from .vault import VaultMemoire

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--base-url", required=True, help="endpoint OpenAI-compatible LOCAL")
    parseur.add_argument("--modele", required=True)
    parseur.add_argument("--score-min", type=float, default=SCORE_MIN_DEFAUT)
    parseur.add_argument(
        "--moteur",
        default="transformers",
        choices=["transformers", "spacy", "aucun"],
        help="couche C2 appliquée avant la passe juge (comme en production)",
    )
    parseur.add_argument("--corpus", default=CORPUS_CANARIS, type=Path)
    parseur.add_argument("--verite", default=VERITE_CANARIS, type=Path)
    arguments = parseur.parse_args()
    for chemin in (arguments.corpus, arguments.verite):
        if not chemin.exists():
            parseur.error(
                f"{chemin} introuvable : lancer depuis la racine du dépôt, "
                "ou passer --corpus et --verite explicitement"
            )

    moteurs = []
    if arguments.moteur != "aucun":
        from .ner import creer_moteur_ner

        moteurs = [creer_moteur_ner(moteur=arguments.moteur)]
    pseudonymiseur = Pseudonymiseur(VaultMemoire(), moteurs=moteurs)
    texte = pseudonymiseur.pseudonymiser(
        arguments.corpus.read_text(encoding="utf-8"), dossier_id="eval-canaris"
    ).texte

    juge = JugeLLM(
        BackendOpenAICompatible(base_url=arguments.base_url, timeout=600),
        modele=arguments.modele,
        score_min=arguments.score_min,
    )
    resultat = evaluer_juge(juge, texte, charger_canaris(arguments.verite))
    print(f"Juge : {arguments.modele} sur {arguments.base_url} (C2 : {arguments.moteur})")
    print(tableau_markdown(resultat))
    # Candidats en clair pour la vérification humaine de l'appariement :
    # sortie console locale, corpus canaris 100 % fictif.
    print("\nCandidats émis (à vérifier à la main, F9) :")
    for candidat in resultat.candidats:
        print(
            f"- [{candidat.type_candidat}] « {candidat.segment} » "
            f"(score {candidat.score:.2f}) : {candidat.justification}"
        )


if __name__ == "__main__":
    _principal()
