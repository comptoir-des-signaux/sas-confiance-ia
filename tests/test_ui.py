"""Lot 12 : interface web minimale (REQ-007 côté UI).

Une page unique servie par le même FastAPI : coller un texte, choisir le
mode, voir le résumé des détections. En mode sérieux, la réponse ne
contient JAMAIS les valeurs détectées ni le vault : types, positions,
scores et comptes seulement. Le mode démo (données synthétiques, bandeau
distinct) peut montrer les valeurs, mais refuse de s'activer si le mode
sérieux a déjà des dossiers actifs dans l'instance (02-AI-SPEC §5).
"""

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

TEXTE = "Marie Martin, joignable à marie.martin@exemple.fr, demande une révision."


@pytest.fixture
def client():
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=BackendCapture(),
        modeles=["modele-de-test"],
    )
    return TestClient(application)


def pseudonymiser(client, mode="serieux", texte=TEXTE, dossier="d-ui"):
    return client.post(
        "/ui/pseudonymiser",
        json={"texte": texte, "dossier_id": dossier, "mode": mode},
    )


def test_la_page_d_accueil_est_servie(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "text/html" in reponse.headers["content-type"]
    page = reponse.text
    assert "Sas Confiance IA" in page
    assert "pseudonymisation" in page.lower()


def test_pseudonymisation_serieuse_sans_aucune_valeur(client):
    corps = pseudonymiser(client).json()
    assert "[EMAIL_001]" in corps["texte"]
    assert corps["comptes_par_type"] == {"EMAIL": 1}
    assert corps["mode"] == "serieux"
    # REQ-007 : types, positions et scores seulement, jamais la valeur.
    serialise = str(corps)
    assert "marie.martin@exemple.fr" not in serialise
    (detection,) = corps["detections"]
    assert set(detection) == {"type", "debut", "fin", "score"}


def test_le_mode_demo_montre_les_valeurs_et_s_affiche_comme_tel(client):
    corps = pseudonymiser(client, mode="demo").json()
    assert corps["mode"] == "demo"
    (detection,) = corps["detections"]
    assert detection["valeur"] == "marie.martin@exemple.fr"
    assert detection["placeholder"] == "[EMAIL_001]"


def test_le_mode_demo_refuse_si_un_dossier_serieux_est_actif(client):
    pseudonymiser(client, mode="serieux")
    reponse = pseudonymiser(client, mode="demo")
    assert reponse.status_code == 409
    assert "sérieux" in reponse.json()["detail"]


def test_le_proxy_compte_aussi_comme_activite_serieuse(client):
    client.post(
        "/v1/chat/completions",
        json={"model": "modele-de-test", "messages": [{"role": "user", "content": TEXTE}]},
        headers={"X-Dossier-Id": "d-proxy"},
    )
    reponse = pseudonymiser(client, mode="demo")
    assert reponse.status_code == 409


def test_un_dossier_demo_ne_peut_pas_devenir_serieux(client):
    pseudonymiser(client, mode="demo", dossier="d-mixte")
    reponse = pseudonymiser(client, mode="serieux", dossier="d-mixte")
    assert reponse.status_code == 409


def test_reidentification_depuis_l_ui(client):
    corps = pseudonymiser(client).json()
    reponse = client.post(
        "/ui/reidentifier", json={"texte": corps["texte"], "dossier_id": "d-ui"}
    )
    assert reponse.json()["texte"] == TEXTE


def test_mode_inconnu_refuse(client):
    assert pseudonymiser(client, mode="turbo").status_code == 422


def test_le_proxy_refuse_un_dossier_utilise_en_demo(client):
    # REQ-007 : le garde-fou vaut sur tous les chemins, pas seulement l'UI.
    pseudonymiser(client, mode="demo", dossier="d-demo")
    reponse = client.post(
        "/v1/chat/completions",
        json={"model": "modele-de-test", "messages": [{"role": "user", "content": TEXTE}]},
        headers={"X-Dossier-Id": "d-demo"},
    )
    assert reponse.status_code == 409


def test_la_separation_demo_serieux_survit_au_redemarrage(tmp_path):
    # Les modes des dossiers vivent avec le vault persistant, pas dans la
    # mémoire du processus (02-AI-SPEC §5).
    from sas_confiance_ia.vault import VaultChiffre, generer_cle

    chemin, cle = tmp_path / "vault.sas", generer_cle()

    def application_sur(vault):
        return TestClient(
            creer_application(
                pseudonymiseur=Pseudonymiseur(vault),
                backend=BackendCapture(),
                modeles=["modele-de-test"],
            )
        )

    client1 = application_sur(VaultChiffre(chemin, cle))
    assert pseudonymiser(client1, mode="serieux").status_code == 200

    client2 = application_sur(VaultChiffre(chemin, cle))
    assert pseudonymiser(client2, mode="demo").status_code == 409


def test_la_reidentification_ui_est_journalisee(client, caplog):
    import json
    import logging

    corps = pseudonymiser(client).json()
    with caplog.at_level(logging.INFO):
        client.post(
            "/ui/reidentifier", json={"texte": corps["texte"], "dossier_id": "d-ui"}
        )
    journaux = [r.message for r in caplog.records if r.name == "sas_confiance_ia.journal"]
    evenement = json.loads(journaux[-1])
    assert evenement["statut"] == "reidentification_ui"
    assert evenement["dossier_id"] == "d-ui"
    # Jamais de valeur ni de texte dans le journal (REQ-003).
    assert "marie.martin@exemple.fr" not in "\n".join(journaux)
    assert "[EMAIL_001]" not in "\n".join(journaux)


def test_la_page_echappe_les_valeurs_avant_insertion_html():
    # Parade XSS : tout contenu inséré via innerHTML passe par l'échappement.
    from sas_confiance_ia.ui import PAGE_HTML

    assert "function echapper" in PAGE_HTML
    assert "echapper(d.valeur)" in PAGE_HTML
