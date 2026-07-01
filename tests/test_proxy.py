"""Lots 6 et 9 : proxy /v1/chat/completions sur faux backend de capture.

REQ-001 : le faux backend enregistre le payload JSON exactement tel qu'il
partirait sur le réseau ; aucune valeur détectable (types déterministes de la
Phase 0) ne doit y figurer. Avec le NER (Lot 9), la couverture s'étend au
périmètre complet de l'oracle : noms, lieux, organisations.
REQ-010 : stream=true est refusé explicitement.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

from .test_detection import ATTENDUS, CORPUS


@pytest.fixture
def backend():
    return BackendCapture(contenu_reponse="Réponse synthétique du modèle.")


@pytest.fixture
def client(backend):
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=backend,
        modeles=["modele-de-test"],
    )
    return TestClient(application)


def completion(client, texte, **headers):
    return client.post(
        "/v1/chat/completions",
        json={
            "model": "modele-de-test",
            "messages": [{"role": "user", "content": texte}],
        },
        headers={"X-Dossier-Id": "dossier-test", **headers},
    )


def test_health(client):
    assert client.get("/health").status_code == 200


def test_v1_models_au_format_openai(client):
    corps = client.get("/v1/models").json()
    assert corps["object"] == "list"
    assert corps["data"][0]["id"] == "modele-de-test"


def test_reponse_au_format_openai(client):
    reponse = completion(client, "Bonjour, résume ce texte.")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["object"] == "chat.completion"
    assert corps["choices"][0]["message"]["role"] == "assistant"
    assert isinstance(corps["choices"][0]["message"]["content"], str)


def test_req_001_aucune_valeur_detectable_dans_le_payload_capture(client, backend):
    # On envoie chaque document du corpus au proxy, puis on inspecte le
    # payload exact que le faux backend a reçu.
    for chemin in sorted(CORPUS.rglob("*.md")):
        if chemin.name == "README.md":
            continue
        completion(client, chemin.read_text(encoding="utf-8"))
    payloads = "\n".join(backend.payloads_bruts)
    assert payloads, "le faux backend n'a rien capturé"
    fuites = [valeur for _, valeur, _ in ATTENDUS if valeur in payloads]
    assert not fuites, f"valeurs présentes dans le payload sortant : {fuites}"


@pytest.mark.ner
def test_req_001_perimetre_complet_avec_ner(moteur_ner):
    # Lot 9 : la non-fuite passe du périmètre déterministe au périmètre
    # complet de l'oracle (personnes, lieux, organisations incluses).
    # 06-canaris.md reste exclu par construction : ses identifiants
    # indirects relèvent du juge LLM (02-AI-SPEC §4.3), pas du NER.
    backend = BackendCapture(contenu_reponse="Réponse synthétique du modèle.")
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire(), moteurs=[moteur_ner]),
        backend=backend,
        modeles=["modele-de-test"],
    )
    client = TestClient(application)
    oracle = json.loads((CORPUS / "valeurs-connues.json").read_text(encoding="utf-8"))
    documents = [
        doc for doc in oracle if not doc.startswith("_") and doc != "06-canaris.md"
    ]
    for doc in documents:
        completion(client, (CORPUS / doc).read_text(encoding="utf-8"))
    payloads = "\n".join(backend.payloads_bruts)
    assert payloads, "le faux backend n'a rien capturé"
    fuites = [
        (doc, valeur) for doc in documents for valeur in oracle[doc] if valeur in payloads
    ]
    assert not fuites, f"valeurs de l'oracle présentes dans le payload sortant : {fuites}"


def test_req_010_stream_est_refuse(client):
    reponse = client.post(
        "/v1/chat/completions",
        json={
            "model": "modele-de-test",
            "messages": [{"role": "user", "content": "Bonjour"}],
            "stream": True,
        },
        headers={"X-Dossier-Id": "dossier-test"},
    )
    assert reponse.status_code == 400
    assert "stream" in reponse.json()["detail"].lower()


def test_le_payload_contient_des_placeholders(client, backend):
    completion(client, "Écrire à marie.martin@exemple.fr au sujet du dossier.")
    assert "[EMAIL_001]" in backend.payloads_bruts[-1]
    assert "marie.martin@exemple.fr" not in backend.payloads_bruts[-1]


def test_chemin_absent(client):
    assert client.get("/inconnu").status_code == 404


@pytest.mark.parametrize("chemin_doc", ["04-dossier-usager/piece-1-courrier.md"])
def test_le_faux_backend_recoit_le_modele_demande(client, backend, chemin_doc):
    completion(client, (Path(CORPUS) / chemin_doc).read_text(encoding="utf-8"))
    assert '"model": "modele-de-test"' in backend.payloads_bruts[-1]
