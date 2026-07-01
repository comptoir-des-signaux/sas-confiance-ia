"""Lot 10 : backend OpenAI-compatible réel (REQ-013), sans réseau.

Le backend est exercé exclusivement à travers un MockTransport httpx2 :
la requête HTTP est construite pour de vrai (URL, en-têtes, corps) mais
rien ne part sur le réseau (HANDOFF, règle 1). Les erreurs réseau
deviennent une ErreurBackend qui ne transporte JAMAIS le contenu des
messages, et le proxy les convertit en HTTP 502 journalisé.
"""

import json
import logging

import httpx2
import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import (
    BackendOpenAICompatible,
    ErreurBackend,
)
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

PAYLOAD = {"model": "mistral", "messages": [{"role": "user", "content": "Bonjour [PERSONNE_001]"}]}


def reponse_openai(contenu="Bonjour !", modele="mistral"):
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "model": modele,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": contenu}}
        ],
    }


def backend_sur(reponse_ou_exception, requetes_capturees=None, **kwargs):
    def repondre(requete: httpx2.Request) -> httpx2.Response:
        if requetes_capturees is not None:
            requetes_capturees.append(requete)
        if isinstance(reponse_ou_exception, Exception):
            raise reponse_ou_exception
        return reponse_ou_exception

    transport = httpx2.MockTransport(repondre)
    return BackendOpenAICompatible(
        base_url="http://ollama.local:11434/v1", transport=transport, **kwargs
    )


def test_le_payload_part_tel_quel_vers_chat_completions():
    requetes = []
    backend = backend_sur(httpx2.Response(200, json=reponse_openai()), requetes)
    backend.completer(PAYLOAD)
    (requete,) = requetes
    assert str(requete.url) == "http://ollama.local:11434/v1/chat/completions"
    assert requete.method == "POST"
    assert json.loads(requete.content) == PAYLOAD


def test_la_reponse_est_analysee():
    backend = backend_sur(httpx2.Response(200, json=reponse_openai("Très bien.", "llama3")))
    reponse = backend.completer(PAYLOAD)
    assert reponse.contenu == "Très bien."
    assert reponse.modele == "llama3"


def test_cle_api_optionnelle_en_bearer():
    requetes = []
    backend = backend_sur(
        httpx2.Response(200, json=reponse_openai()), requetes, cle_api="cle-de-test"
    )
    backend.completer(PAYLOAD)
    assert requetes[0].headers["authorization"] == "Bearer cle-de-test"


def test_sans_cle_api_aucun_en_tete_authorization():
    requetes = []
    backend = backend_sur(httpx2.Response(200, json=reponse_openai()), requetes)
    backend.completer(PAYLOAD)
    assert "authorization" not in requetes[0].headers


def test_erreur_http_du_backend():
    backend = backend_sur(httpx2.Response(500, text="boum interne"))
    with pytest.raises(ErreurBackend) as exc:
        backend.completer(PAYLOAD)
    assert exc.value.erreur_type == "HTTPStatusError"


def test_erreur_reseau():
    backend = backend_sur(httpx2.ConnectError("connexion refusée"))
    with pytest.raises(ErreurBackend) as exc:
        backend.completer(PAYLOAD)
    assert exc.value.erreur_type == "ConnectError"


def test_reponse_hors_format_openai():
    backend = backend_sur(httpx2.Response(200, json={"inattendu": True}))
    with pytest.raises(ErreurBackend) as exc:
        backend.completer(PAYLOAD)
    assert exc.value.erreur_type == "FormatReponseInvalide"


def test_l_erreur_ne_transporte_jamais_le_contenu_des_messages():
    # Même en échec, ni le payload ni le corps de réponse ne fuient dans
    # l'exception (elle finit dans les logs du proxy).
    backend = backend_sur(httpx2.Response(500, text="détail interne du fournisseur"))
    with pytest.raises(ErreurBackend) as exc:
        backend.completer(PAYLOAD)
    texte_exception = str(exc.value) + repr(exc.value)
    assert "Bonjour [PERSONNE_001]" not in texte_exception
    assert "détail interne du fournisseur" not in texte_exception


def test_un_timeout_explicite_est_configure():
    backend = BackendOpenAICompatible(base_url="http://ollama.local:11434/v1")
    assert backend.timeout > 0


def test_le_proxy_convertit_l_erreur_backend_en_502(caplog):
    class BackendEnPanne:
        def completer(self, payload):
            raise ErreurBackend("ConnectError", "connexion refusée par le backend")

    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=BackendEnPanne(),
        modeles=["modele-de-test"],
    )
    client = TestClient(application)
    with caplog.at_level(logging.INFO):
        reponse = client.post(
            "/v1/chat/completions",
            json={
                "model": "modele-de-test",
                "messages": [{"role": "user", "content": "Écrire à marie.martin@exemple.fr"}],
            },
            headers={"X-Dossier-Id": "dossier-test"},
        )
    assert reponse.status_code == 502
    # Le détail renvoyé au client ne contient ni le message ni sa version
    # pseudonymisée, seulement le type d'erreur.
    assert "marie.martin@exemple.fr" not in reponse.text
    assert "ConnectError" in reponse.text
    journaux = [r.message for r in caplog.records if r.name == "sas_confiance_ia.journal"]
    evenement = json.loads(journaux[-1])
    assert evenement["statut"] == "erreur_backend"
    assert evenement["erreur_type"] == "ConnectError"
    assert "marie.martin@exemple.fr" not in "\n".join(journaux)
