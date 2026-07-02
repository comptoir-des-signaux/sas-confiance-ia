"""Lot 13 : éval du juge sur les canaris (02-AI-SPEC §4.3, REQ-014).

La mesure réelle se fait MANUELLEMENT contre un Ollama local (hors CI,
procédure documentée dans docs/eval/evaluation-juge.md). Ici on teste la
mécanique d'appariement et de mesure sur un juge simulé : aucun réseau.
"""

import json
from pathlib import Path

from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.evaluation_juge import (
    canari_signale,
    charger_canaris,
    evaluer_juge,
    tableau_markdown,
)
from sas_confiance_ia.juge import CandidatJuge, JugeLLM


def candidat(segment: str) -> CandidatJuge:
    return CandidatJuge(
        segment=segment, type_candidat="INDIRECT", justification="x", score=0.9
    )


def test_un_extrait_contenu_dans_le_segment_compte_signale():
    canari = {"id": "c", "description": "", "extraits": ["chef du service assainissement"]}
    assert canari_signale(
        canari, [candidat("le chef du service assainissement de la communauté")]
    )


def test_un_segment_contenu_dans_l_extrait_compte_signale():
    canari = {
        "id": "c",
        "description": "",
        "extraits": ["recruté en mars dernier au service urbanisme"],
    }
    assert canari_signale(canari, [candidat("recruté en mars dernier")])


def test_la_casse_n_empeche_pas_l_appariement():
    canari = {"id": "c", "description": "", "extraits": ["Jojo"]}
    assert canari_signale(canari, [candidat("JOJO")])


def test_un_recouvrement_majoritaire_de_mots_compte_signale():
    # Le juge cite rarement l'extrait mot pour mot : la majorité des mots
    # significatifs suffit (appariement souple, mesure honnête en revue).
    canari = {
        "id": "c",
        "description": "",
        "extraits": ["seul titulaire du permis poids lourd"],
    }
    assert canari_signale(
        canari, [candidat("le seul agent titulaire du permis poids lourd de l'équipe")]
    )


def test_un_candidat_sans_rapport_ne_compte_pas():
    canari = {"id": "c", "description": "", "extraits": ["chef du service assainissement"]}
    assert not canari_signale(canari, [candidat("la salle des fêtes")])


def test_charger_canaris_ignore_les_commentaires():
    canaris = charger_canaris(Path("corpus/synthetique/verite-terrain-canaris.json"))
    assert len(canaris) == 6
    assert all(not cle.startswith("_") for canari in canaris for cle in canari)


def test_evaluer_juge_mesure_la_fraction_signalee():
    canaris = charger_canaris(Path("corpus/synthetique/verite-terrain-canaris.json"))
    sortie = json.dumps(
        [
            {
                "segment": "chef du service assainissement",
                "type_candidat": "FONCTION_RARE",
                "justification": "Fonction unique.",
                "score": 0.9,
            },
            {
                "segment": "surnomment Jojo",
                "type_candidat": "SURNOM",
                "justification": "Surnom identifiant.",
                "score": 0.8,
            },
        ]
    )
    juge = JugeLLM(BackendCapture(contenu_reponse=sortie), modele="juge-test")
    resultat = evaluer_juge(juge, "texte pseudonymisé factice", canaris)
    assert resultat.signales == ["fonction-rare-epci", "surnom-jojo"]
    assert resultat.manques == [
        "elu-petite-commune",
        "professionnelle-unique",
        "predecesseur-mute",
        "matricule-atypique",
    ]
    assert resultat.taux == 2 / 6
    assert resultat.candidats_total == 2

    tableau = tableau_markdown(resultat)
    assert "2/6" in tableau
    assert "fonction-rare-epci" in tableau


def test_les_mots_outils_ne_comptent_pas_dans_l_appariement():
    # « dans », « plus », « même » dépassent 3 lettres mais ne discriminent
    # rien : sans ce filtre, la mesure F9 se gonfle par appariement croisé.
    canari = {"id": "c", "description": "", "extraits": ["muté dans le même bureau"]}
    assert not canari_signale(canari, [candidat("dans le même temps")])


def test_un_candidat_ne_valide_qu_un_seul_canari():
    canaris = [
        {"id": "a", "description": "", "extraits": ["la petite commune membre"]},
        {"id": "b", "description": "", "extraits": ["plus petite commune voisine"]},
    ]
    sortie = json.dumps(
        [
            {
                "segment": "la petite commune",
                "type_candidat": "LIEU_RARE",
                "justification": "x",
                "score": 0.9,
            }
        ]
    )
    juge = JugeLLM(BackendCapture(contenu_reponse=sortie), modele="juge-test")
    resultat = evaluer_juge(juge, "texte factice", canaris)
    # Un seul candidat émis : il ne peut pas couvrir deux canaris à la fois.
    assert len(resultat.signales) == 1
