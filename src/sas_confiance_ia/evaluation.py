"""Évaluation de la couche NER sur le corpus synthétique (02-AI-SPEC §4.2).

Le rappel est la métrique reine : une mention non recouverte est une fuite
potentielle. Critère protecteur : une occurrence n'est comptée détectée que
si une entité du bon type la recouvre ENTIÈREMENT ; une détection partielle
compte pour la précision (elle recouvre du vrai) mais pas pour le rappel.

Usage : python -m sas_confiance_ia.evaluation [--moteur transformers|spacy]

L'option --ecrire-baseline ÉCRASE la référence de la porte 4.4 : à ne faire
qu'après un changement de modèle assumé et documenté, jamais pour « faire
passer » un test ; elle est refusée pour le moteur de repli.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .detection import Moteur

VERITE_TERRAIN = "verite-terrain-ner.json"
TYPES_EVALUES = ["PERSONNE", "ORGANISATION", "LIEU"]


@dataclass(frozen=True)
class MesureType:
    """Mesures d'un type d'entité ; rappel/precision valent None si sans objet."""

    rappel: float | None
    precision: float | None
    occurrences: int
    occurrences_couvertes: int
    detections: int
    detections_correctes: int


def _occurrences(texte: str, valeur: str) -> list[tuple[int, int]]:
    positions = []
    debut = texte.find(valeur)
    while debut >= 0:
        positions.append((debut, debut + len(valeur)))
        debut = texte.find(valeur, debut + len(valeur))
    return positions


def evaluer(
    moteur: Moteur,
    textes: dict[str, str],
    verite: dict[str, dict[str, list[str]]],
) -> dict[str, MesureType]:
    """Rappel et précision par type, au niveau des occurrences."""
    couvertes: dict[str, int] = dict.fromkeys(TYPES_EVALUES, 0)
    totales: dict[str, int] = dict.fromkeys(TYPES_EVALUES, 0)
    correctes: dict[str, int] = dict.fromkeys(TYPES_EVALUES, 0)
    detectees: dict[str, int] = dict.fromkeys(TYPES_EVALUES, 0)

    for doc, texte in textes.items():
        entites = [e for e in moteur.reconnaitre(texte) if e.type in TYPES_EVALUES]
        attendu = verite[doc]
        empans_verite: dict[str, list[tuple[int, int]]] = {t: [] for t in TYPES_EVALUES}
        for type_ in TYPES_EVALUES:
            for valeur in attendu.get(type_, []):
                empans_verite[type_].extend(_occurrences(texte, valeur))

        for type_ in TYPES_EVALUES:
            for debut, fin in empans_verite[type_]:
                totales[type_] += 1
                if any(e.type == type_ and e.debut <= debut and e.fin >= fin for e in entites):
                    couvertes[type_] += 1

        for entite in entites:
            detectees[entite.type] += 1
            if any(
                entite.debut < fin and entite.fin > debut
                for debut, fin in empans_verite[entite.type]
            ):
                correctes[entite.type] += 1

    return {
        type_: MesureType(
            rappel=couvertes[type_] / totales[type_] if totales[type_] else None,
            precision=correctes[type_] / detectees[type_] if detectees[type_] else None,
            occurrences=totales[type_],
            occurrences_couvertes=couvertes[type_],
            detections=detectees[type_],
            detections_correctes=correctes[type_],
        )
        for type_ in TYPES_EVALUES
    }


def charger_corpus(dossier: Path | str) -> tuple[dict[str, str], dict[str, dict[str, list[str]]]]:
    """Textes et vérité terrain du corpus ; seuls les documents annotés comptent."""
    dossier = Path(dossier)
    brut = json.loads((dossier / VERITE_TERRAIN).read_text(encoding="utf-8"))
    verite = {doc: annotations for doc, annotations in brut.items() if not doc.startswith("_")}
    textes = {doc: (dossier / doc).read_text(encoding="utf-8") for doc in verite}
    return textes, verite


def _formater_pourcent(valeur: float | None) -> str:
    return "sans objet" if valeur is None else f"{100 * valeur:.1f} %"


def _tableau_markdown(mesures: dict[str, MesureType]) -> str:
    lignes = [
        "| Type | Rappel | Précision | Mentions couvertes | Détections correctes |",
        "|---|---|---|---|---|",
    ]
    for type_, m in mesures.items():
        lignes.append(
            f"| {type_} | {_formater_pourcent(m.rappel)} | {_formater_pourcent(m.precision)} "
            f"| {m.occurrences_couvertes}/{m.occurrences} "
            f"| {m.detections_correctes}/{m.detections} |"
        )
    return "\n".join(lignes)


def ecrire_baseline(mesures: dict[str, MesureType], moteur: str, chemin: Path) -> None:
    """Écrase la baseline de la porte 4.4 ; réservé au moteur de référence."""
    if moteur != "transformers":
        raise ValueError(
            "la baseline de la porte 4.4 référence le moteur transformers "
            "(CamemBERT épinglé) : l'écrire depuis le repli spaCy rendrait "
            "la porte aveugle aux régressions"
        )
    from .ner import MODELE_TRANSFORMERS, REVISION_TRANSFORMERS

    contenu = {
        "moteur": moteur,
        "modele": MODELE_TRANSFORMERS,
        "revision": REVISION_TRANSFORMERS,
        "rappel": {t: m.rappel for t, m in mesures.items() if m.rappel is not None},
        "precision": {t: m.precision for t, m in mesures.items() if m.precision is not None},
    }
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _description_moteur(moteur: str) -> str:
    from .ner import MODELE_SPACY_REPLI, MODELE_TRANSFORMERS, REVISION_TRANSFORMERS

    if moteur == "spacy":
        return f"spacy ({MODELE_SPACY_REPLI}, repli hors porte 4.4)"
    return f"transformers ({MODELE_TRANSFORMERS} @ {REVISION_TRANSFORMERS[:12]})"


def _principal() -> None:
    import argparse

    from .ner import creer_moteur_ner

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--corpus", default="corpus/synthetique", type=Path)
    parseur.add_argument("--moteur", default="transformers", choices=["transformers", "spacy"])
    parseur.add_argument(
        "--ecrire-baseline",
        type=Path,
        default=None,
        metavar="CHEMIN",
        help="ÉCRASE la baseline de la porte 4.4 (réservé au moteur transformers, "
        "après changement de modèle assumé)",
    )
    options = parseur.parse_args()

    textes, verite = charger_corpus(options.corpus)
    mesures = evaluer(creer_moteur_ner(moteur=options.moteur), textes, verite)
    print(f"Moteur : {_description_moteur(options.moteur)}")
    print(_tableau_markdown(mesures))

    if options.ecrire_baseline is not None:
        ecrire_baseline(mesures, moteur=options.moteur, chemin=options.ecrire_baseline)
        print(f"Baseline écrite : {options.ecrire_baseline}")


if __name__ == "__main__":
    _principal()
