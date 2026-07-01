"""Lot 8 : le journal aide la gouvernance sans devenir une fuite (REQ-003).

Métadonnées seulement : jamais de valeur brute, de prompt, de réponse, de
vault ni de secret dans les journaux.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.journal import Journal
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

from .test_corpus import CORPUS, charger_oracle


@pytest.fixture
def client():
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=BackendCapture(contenu_reponse="Réponse citant [EMAIL_001]."),
        modeles=["modele-de-test"],
        journal=Journal(),
    )
    return TestClient(application)


def envoyer_tout_le_corpus(client):
    for chemin in sorted(CORPUS.rglob("*.md")):
        if chemin.name == "README.md":
            continue
        client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [{"role": "user", "content": chemin.read_text(encoding="utf-8")}],
            },
            headers={"X-Dossier-Id": "dossier-journal"},
        )


def test_req_003_aucune_valeur_de_l_oracle_dans_les_logs(client, caplog):
    with caplog.at_level(logging.INFO):
        envoyer_tout_le_corpus(client)
    assert caplog.text, "aucun journal produit"
    fuites = [
        valeur
        for valeurs in charger_oracle().values()
        for valeur in valeurs
        if valeur in caplog.text
    ]
    assert not fuites, f"valeurs brutes dans les journaux : {fuites}"


def test_le_journal_ne_contient_ni_prompt_ni_reponse(client, caplog):
    with caplog.at_level(logging.INFO):
        client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [{"role": "user", "content": "PHRASE-SENTINELLE-DU-PROMPT"}],
            },
            headers={"X-Dossier-Id": "d1"},
        )
    assert "PHRASE-SENTINELLE-DU-PROMPT" not in caplog.text
    assert "Réponse citant" not in caplog.text


def dernier_evenement(caplog) -> dict:
    records = [r for r in caplog.records if r.name == "sas_confiance_ia.journal"]
    assert records, "aucun événement de journal émis"
    return json.loads(records[-1].message)


def test_le_journal_contient_les_metadonnees_utiles(client, caplog):
    with caplog.at_level(logging.INFO):
        client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [
                    {"role": "user", "content": "Écrire à jean.dupont@exemple.fr."}
                ],
            },
            headers={"X-Dossier-Id": "d1"},
        )
    evenement = dernier_evenement(caplog)
    assert evenement["dossier_id"] == "d1"
    assert evenement["modele"] == "modele-de-test"
    assert evenement["statut"] == "ok"
    assert evenement["entites_par_type"] == {"EMAIL": 1}
    assert evenement["integrite"] == "review_required" or evenement["integrite"] == "ok"
    assert "requete_id" in evenement and "horodatage" in evenement


def test_le_refus_du_streaming_est_journalise(client, caplog):
    with caplog.at_level(logging.INFO):
        client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [{"role": "user", "content": "Bonjour"}],
                "stream": True,
            },
            headers={"X-Dossier-Id": "d1"},
        )
    evenement = dernier_evenement(caplog)
    assert evenement["statut"] == "refus_streaming"
