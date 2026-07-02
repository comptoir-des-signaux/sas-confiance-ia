"""Lot 13 : juge LLM local (C3, REQ-014).

Le juge reçoit un texte DÉJÀ pseudonymisé par C1+C2 et signale des candidats
d'identifiants indirects pour revue humaine : jamais de remplacement direct
en v1 (02-AI-SPEC §2). Sortie JSON stricte : toute sortie non conforme est
rejetée, jamais interprétée (parade F7). Les tests n'utilisent que des
backends simulés : aucun appel réseau (HANDOFF, règle 1).
"""

import json

import httpx2
import pytest

from sas_confiance_ia.backends import (
    BackendCapture,
    BackendOpenAICompatible,
    ErreurBackend,
)
from sas_confiance_ia.juge import CONSIGNE_JUGE, CandidatJuge, ErreurJuge, JugeLLM

TEXTE = (
    "Le chef du service assainissement de la communauté de communes a signalé "
    "des tensions. L'agent surnommé Jojo n'a pas souhaité témoigner."
)

CANDIDATS_VALIDES = [
    {
        "segment": "chef du service assainissement",
        "type_candidat": "FONCTION_RARE",
        "justification": "Fonction unique dans une petite structure.",
        "score": 0.9,
    },
    {
        "segment": "Jojo",
        "type_candidat": "SURNOM",
        "justification": "Surnom qui identifie l'agent auprès des collègues.",
        "score": 0.8,
    },
]


def creer_juge(contenu: str, score_min: float = 0.5) -> tuple[JugeLLM, BackendCapture]:
    backend = BackendCapture(contenu_reponse=contenu)
    return JugeLLM(backend, modele="juge-test", score_min=score_min), backend


def test_le_juge_signale_des_candidats_types():
    juge, _ = creer_juge(json.dumps(CANDIDATS_VALIDES))
    candidats = juge.signaler(TEXTE)
    assert candidats == [
        CandidatJuge(
            segment="chef du service assainissement",
            type_candidat="FONCTION_RARE",
            justification="Fonction unique dans une petite structure.",
            score=0.9,
        ),
        CandidatJuge(
            segment="Jojo",
            type_candidat="SURNOM",
            justification="Surnom qui identifie l'agent auprès des collègues.",
            score=0.8,
        ),
    ]


def test_le_juge_envoie_la_consigne_puis_le_texte():
    juge, backend = creer_juge("[]")
    juge.signaler(TEXTE)
    (payload_brut,) = backend.payloads_bruts
    payload = json.loads(payload_brut)
    assert payload["model"] == "juge-test"
    assert payload["messages"][0] == {"role": "system", "content": CONSIGNE_JUGE}
    assert payload["messages"][1] == {"role": "user", "content": TEXTE}
    # Déterminisme maximal pour une passe d'audit.
    assert payload["temperature"] == 0


def test_une_liste_vide_est_une_sortie_conforme():
    juge, _ = creer_juge("[]")
    assert juge.signaler(TEXTE) == []


@pytest.mark.parametrize(
    "sortie",
    [
        "Voici les identifiants indirects que j'ai trouvés : Jojo.",
        '{"segment": "Jojo"}',  # objet au lieu d'une liste
        '[{"segment": "Jojo", "type_candidat": "SURNOM", "score": 0.8}]',  # clé manquante
        json.dumps(
            [dict(CANDIDATS_VALIDES[0], position=12)]  # clé inconnue
        ),
        json.dumps([dict(CANDIDATS_VALIDES[0], score=1.5)]),  # score hors bornes
        json.dumps([dict(CANDIDATS_VALIDES[0], score="fort")]),  # score non numérique
        json.dumps([dict(CANDIDATS_VALIDES[0], segment="")]),  # segment vide
        '[{"segment": "Jojo", "type_candidat": "SURNOM", '
        '"justification": "x", "score": 0.8},]',  # JSON invalide (virgule finale)
    ],
)
def test_toute_sortie_non_conforme_est_rejetee(sortie):
    juge, _ = creer_juge(sortie)
    with pytest.raises(ErreurJuge) as excinfo:
        juge.signaler(TEXTE)
    assert excinfo.value.erreur_type == "SortieJugeInvalide"
    # Jamais la sortie du modèle dans le message (elle peut citer le texte).
    assert "Jojo" not in str(excinfo.value)


def test_les_fioritures_deterministes_sont_epurees():
    # Cloture de raisonnement (qwen3) et barrière markdown : épuration
    # déterministe, pas une interprétation (le JSON reste strict ensuite).
    sortie = (
        "<think>Je repère un surnom et une fonction rare.</think>\n"
        "```json\n" + json.dumps(CANDIDATS_VALIDES) + "\n```"
    )
    juge, _ = creer_juge(sortie)
    assert len(juge.signaler(TEXTE)) == 2


def test_un_score_sous_le_seuil_est_filtre():
    juge, _ = creer_juge(
        json.dumps(CANDIDATS_VALIDES + [dict(CANDIDATS_VALIDES[0], score=0.2)]),
        score_min=0.5,
    )
    assert len(juge.signaler(TEXTE)) == 2


def test_un_placeholder_n_est_jamais_un_candidat():
    # Le texte reçu est déjà pseudonymisé : signaler [PERSONNE_001] serait
    # du bruit pur en revue (la valeur est déjà protégée).
    juge, _ = creer_juge(
        json.dumps(
            CANDIDATS_VALIDES
            + [
                {
                    "segment": "[PERSONNE_001]",
                    "type_candidat": "PERSONNE",
                    "justification": "Nom de personne.",
                    "score": 0.99,
                }
            ]
        )
    )
    candidats = juge.signaler(TEXTE)
    assert [c.segment for c in candidats] == ["chef du service assainissement", "Jojo"]


def test_une_erreur_backend_devient_une_erreur_juge():
    class BackendEnPanne:
        def completer(self, payload):
            raise ErreurBackend("ConnectError", "échec de l'appel au backend")

    juge = JugeLLM(BackendEnPanne(), modele="juge-test")
    with pytest.raises(ErreurJuge) as excinfo:
        juge.signaler(TEXTE)
    assert excinfo.value.erreur_type == "ConnectError"


def test_le_juge_fonctionne_sur_le_backend_http_sans_reseau():
    # Même classe HTTP que le backend applicatif (REQ-013), MockTransport :
    # le garde-fou réseau de conftest prouve qu'aucun appel ne sort.
    def repondre(requete: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "model": "juge-test",
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(CANDIDATS_VALIDES)}}
                ],
            },
        )

    backend = BackendOpenAICompatible(
        base_url="http://127.0.0.1:11434/v1",
        transport=httpx2.MockTransport(repondre),
    )
    juge = JugeLLM(backend, modele="juge-test")
    assert len(juge.signaler(TEXTE)) == 2
