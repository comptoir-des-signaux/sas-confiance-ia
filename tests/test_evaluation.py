"""Lot 9 : évaluation du NER (02-AI-SPEC §4.2 et porte 4.4).

Le rappel est la métrique reine (un faux négatif est une fuite) ; il est
mesuré et publié pour PERSONNE / ORGANISATION / LIEU sans cible
contractuelle, avec une porte de non-régression : pas de baisse de plus
de 2 points par rapport à la baseline committée.
"""

import json
from pathlib import Path

import pytest

from sas_confiance_ia.detection import EntiteDetectee

CORPUS = Path(__file__).parent.parent / "corpus" / "synthetique"
BASELINE = Path(__file__).parent.parent / "docs" / "eval" / "ner-baseline.json"


def test_chaque_valeur_de_la_verite_terrain_est_dans_son_document():
    # Même exigence de cohérence que pour l'oracle de non-fuite (REQ-009).
    verite = json.loads((CORPUS / "verite-terrain-ner.json").read_text(encoding="utf-8"))
    for doc, par_type in verite.items():
        if doc.startswith("_"):
            continue
        texte = (CORPUS / doc).read_text(encoding="utf-8")
        for type_, valeurs in par_type.items():
            for valeur in valeurs:
                assert valeur in texte, f"{valeur!r} ({type_}) absente de {doc}"


def test_les_canaris_sont_exclus_de_la_verite_terrain_ner():
    # 02-AI-SPEC §4.3 : les identifiants indirects relèvent du juge (C3).
    verite = json.loads((CORPUS / "verite-terrain-ner.json").read_text(encoding="utf-8"))
    assert "06-canaris.md" not in verite


class MoteurFactice:
    def __init__(self, entites_par_texte):
        self._entites = entites_par_texte

    def reconnaitre(self, texte):
        return self._entites.get(texte, [])


def _entite(type_, texte, valeur, occurrence=0):
    debut = -1
    for _ in range(occurrence + 1):
        debut = texte.index(valeur, debut + 1)
    return EntiteDetectee(
        type=type_, debut=debut, fin=debut + len(valeur), score=0.9, valeur=valeur
    )


def test_le_calcul_de_rappel_et_de_precision_est_exact():
    from sas_confiance_ia.evaluation import evaluer

    texte = "Alice Durand vit à Lyon. Lyon lui plaît énormément."
    textes = {"doc.md": texte}
    verite = {"doc.md": {"PERSONNE": ["Alice Durand"], "ORGANISATION": [], "LIEU": ["Lyon"]}}
    moteur = MoteurFactice(
        {
            texte: [
                _entite("PERSONNE", texte, "Alice Durand"),
                # Faux positif : « énormément » n'est pas une personne.
                _entite("PERSONNE", texte, "énormément"),
                # Une seule des deux occurrences de Lyon est trouvée.
                _entite("LIEU", texte, "Lyon", occurrence=0),
            ]
        }
    )
    mesures = evaluer(moteur, textes, verite)
    assert mesures["PERSONNE"].rappel == 1.0
    assert mesures["PERSONNE"].precision == 0.5
    assert mesures["LIEU"].rappel == 0.5
    assert mesures["LIEU"].precision == 1.0
    # Aucune organisation dans la vérité terrain : rappel sans objet (None).
    assert mesures["ORGANISATION"].rappel is None


def test_une_detection_partielle_ne_compte_pas_comme_rappel():
    # Critère protecteur : l'entité doit recouvrir TOUTE la mention ;
    # « Durand » seul laisserait fuir « Alice ».
    from sas_confiance_ia.evaluation import evaluer

    texte = "Alice Durand est venue."
    moteur = MoteurFactice({texte: [_entite("PERSONNE", texte, "Durand")]})
    mesures = evaluer(
        moteur,
        {"doc.md": texte},
        {"doc.md": {"PERSONNE": ["Alice Durand"], "ORGANISATION": [], "LIEU": []}},
    )
    assert mesures["PERSONNE"].rappel == 0.0
    # Le fragment recouvre bien une mention réelle : précision intacte.
    assert mesures["PERSONNE"].precision == 1.0


def test_charger_corpus_retourne_textes_et_verite():
    from sas_confiance_ia.evaluation import charger_corpus

    textes, verite = charger_corpus(CORPUS)
    assert set(textes) == set(verite)
    assert "01-courrier-usager.md" in textes
    assert "06-canaris.md" not in textes


@pytest.mark.ner
def test_porte_4_4_pas_de_regression_de_rappel_de_plus_de_2_points(moteur_ner):
    from sas_confiance_ia.evaluation import charger_corpus, evaluer

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    textes, verite = charger_corpus(CORPUS)
    mesures = evaluer(moteur_ner, textes, verite)
    regressions = []
    for type_, rappel_reference in baseline["rappel"].items():
        rappel = mesures[type_].rappel
        if rappel is not None and rappel < rappel_reference - 0.02:
            regressions.append((type_, rappel_reference, rappel))
    assert not regressions, f"régression de rappel au-delà de 2 points : {regressions}"
