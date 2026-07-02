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


# --- Intégration dans le flux (proxy et UI) ---------------------------------


def creer_client(juge=None):
    from fastapi.testclient import TestClient

    from sas_confiance_ia.api import creer_application
    from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
    from sas_confiance_ia.vault import VaultMemoire

    backend_applicatif = BackendCapture()
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=backend_applicatif,
        modeles=["modele-de-test"],
        juge=juge,
    )
    return TestClient(application), backend_applicatif


TEXTE_AVEC_EMAIL = (
    "Marie Martin, joignable à marie.martin@exemple.fr, surnommée Jojo au bureau."
)


def test_le_proxy_expose_les_candidats_du_juge():
    juge, backend_juge = creer_juge(json.dumps(CANDIDATS_VALIDES))
    client, _ = creer_client(juge=juge)
    reponse = client.post(
        "/v1/chat/completions",
        json={
            "model": "modele-de-test",
            "messages": [{"role": "user", "content": TEXTE_AVEC_EMAIL}],
        },
    )
    bloc = reponse.json()["sas_confiance_ia"]["juge"]
    assert bloc["actif"] is True
    assert [c["segment"] for c in bloc["candidats"]] == [
        "chef du service assainissement",
        "Jojo",
    ]
    assert set(bloc["candidats"][0]) == {"segment", "type_candidat", "justification", "score"}


def test_le_juge_recoit_le_texte_deja_pseudonymise():
    # 02-AI-SPEC §2 : le juge ne voit les valeurs brutes que pour les
    # segments encore non couverts ; ce que C1 a détecté est déjà protégé.
    juge, backend_juge = creer_juge("[]")
    client, _ = creer_client(juge=juge)
    client.post(
        "/v1/chat/completions",
        json={
            "model": "modele-de-test",
            "messages": [{"role": "user", "content": TEXTE_AVEC_EMAIL}],
        },
    )
    (payload_juge,) = backend_juge.payloads_bruts
    assert "marie.martin@exemple.fr" not in payload_juge
    assert "[EMAIL_001]" in payload_juge


def test_sans_juge_le_sas_reste_fonctionnel():
    # REQ-014 : le juge est optionnel par conception, absent = documenté
    # moins couvrant, jamais une erreur.
    client, _ = creer_client(juge=None)
    reponse = client.post(
        "/v1/chat/completions",
        json={
            "model": "modele-de-test",
            "messages": [{"role": "user", "content": TEXTE_AVEC_EMAIL}],
        },
    )
    assert reponse.status_code == 200
    assert reponse.json()["sas_confiance_ia"]["juge"] == {"actif": False, "candidats": []}


def test_une_erreur_du_juge_n_empeche_pas_le_flux(caplog):
    import logging

    juge, _ = creer_juge("sortie qui n'est pas du JSON")
    client, _ = creer_client(juge=juge)
    with caplog.at_level(logging.INFO):
        reponse = client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [{"role": "user", "content": TEXTE_AVEC_EMAIL}],
            },
        )
    assert reponse.status_code == 200
    bloc = reponse.json()["sas_confiance_ia"]["juge"]
    assert bloc == {"actif": True, "candidats": [], "erreur_type": "SortieJugeInvalide"}
    enregistrements = [r for r in caplog.records if r.name == "sas_confiance_ia.journal"]
    assert any("erreur_juge" in r.getMessage() for r in enregistrements)


def test_le_journal_ne_contient_jamais_les_segments_du_juge(caplog):
    import logging

    juge, _ = creer_juge(json.dumps(CANDIDATS_VALIDES))
    client, _ = creer_client(juge=juge)
    with caplog.at_level(logging.INFO):
        client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [{"role": "user", "content": TEXTE_AVEC_EMAIL}],
            },
        )
    texte_journal = "\n".join(
        r.getMessage() for r in caplog.records if r.name == "sas_confiance_ia.journal"
    )
    assert "chef du service assainissement" not in texte_journal
    assert "Jojo" not in texte_journal
    # Le compte, lui, est une métadonnée de gouvernance légitime (REQ-003).
    assert '"candidats_juge": 2' in texte_journal


def test_l_ui_expose_les_candidats_du_juge():
    juge, backend_juge = creer_juge(json.dumps(CANDIDATS_VALIDES))
    client, _ = creer_client(juge=juge)
    reponse = client.post(
        "/ui/pseudonymiser",
        json={"texte": TEXTE_AVEC_EMAIL, "dossier_id": "d-juge", "mode": "serieux"},
    )
    corps = reponse.json()
    assert corps["juge"]["actif"] is True
    assert [c["segment"] for c in corps["juge"]["candidats"]] == [
        "chef du service assainissement",
        "Jojo",
    ]
    (payload_juge,) = backend_juge.payloads_bruts
    assert "marie.martin@exemple.fr" not in payload_juge


def test_la_page_affiche_la_section_juge():
    from sas_confiance_ia.ui import PAGE_HTML

    assert "candidats" in PAGE_HTML
    assert "Identifiants indirects" in PAGE_HTML
