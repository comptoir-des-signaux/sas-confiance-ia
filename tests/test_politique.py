"""Lot 14 : politiques de remplacement par type d'entité (cadrage §9.5).

Quatre actions par type : pseudonymiser (défaut, réversible par le vault),
masquer (sans coffre, irréversible, [TYPE] sans numéro), conserver (choix
explicite, journalisé) et revue (pseudonymiser et signaler pour relecture).
Défauts protecteurs par l'environnement (SAS_POLITIQUES), surcharge par
dossier stockée dans le vault, comme le mode démo / sérieux.
"""

import json

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.politique import Politique, analyser_politiques
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultChiffre, VaultMemoire, generer_cle

NIR = "2 92 07 82 045 033 55"
TELEPHONE = "06 12 34 56 78"
TEXTE = f"Dossier de Marie Martin, NIR {NIR}, joignable au {TELEPHONE}."


def pseudonymiseur(politique: Politique | None = None, vault=None) -> Pseudonymiseur:
    return Pseudonymiseur(vault or VaultMemoire(), politique=politique)


# --- Actions ---------------------------------------------------------------


def test_par_defaut_tout_type_detecte_est_pseudonymise():
    resultat = pseudonymiseur().pseudonymiser(TEXTE, dossier_id="d1")
    assert "[NIR_001]" in resultat.texte
    assert "[TELEPHONE_001]" in resultat.texte
    assert resultat.en_revue == []


def test_masquer_est_sans_coffre_et_irreversible():
    pseudo = pseudonymiseur(Politique(actions={"FR_NIR": "masquer"}))
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert NIR not in resultat.texte
    assert "[NIR]" in resultat.texte
    assert "[NIR_001]" not in resultat.texte
    # Aucune entrée vault : la ré-identification laisse le marqueur tel quel.
    assert not any("NIR" in p for p in pseudo.placeholders_connus("d1"))
    assert NIR not in pseudo.reidentifier(resultat.texte, dossier_id="d1")


def test_conserver_laisse_la_valeur_en_clair_sans_vault():
    pseudo = pseudonymiseur(Politique(actions={"TELEPHONE": "conserver"}))
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert TELEPHONE in resultat.texte
    assert "[TELEPHONE" not in resultat.texte
    assert not any("TELEPHONE" in p for p in pseudo.placeholders_connus("d1"))
    # La détection reste comptée : le journal documente ce qui a été vu.
    assert resultat.comptes_par_type["TELEPHONE"] == 1


def test_revue_pseudonymise_et_signale():
    pseudo = pseudonymiseur(Politique(actions={"TELEPHONE": "revue"}))
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert TELEPHONE not in resultat.texte
    assert "[TELEPHONE_001]" in resultat.texte
    assert resultat.en_revue == ["[TELEPHONE_001]"]
    # Réversible comme une pseudonymisation ordinaire.
    assert TELEPHONE in pseudo.reidentifier(resultat.texte, dossier_id="d1")


def test_l_aller_retour_reste_exact_avec_conserver_et_revue():
    pseudo = pseudonymiseur(
        Politique(actions={"TELEPHONE": "conserver", "EMAIL": "revue"})
    )
    texte = f"Appeler le {TELEPHONE} ou écrire à marie.martin@exemple.fr."
    resultat = pseudo.pseudonymiser(texte, dossier_id="d1")
    assert pseudo.reidentifier(resultat.texte, dossier_id="d1") == texte


# --- Validation ------------------------------------------------------------


def test_une_action_inconnue_est_refusee():
    with pytest.raises(ValueError, match="caviarder"):
        analyser_politiques("FR_NIR=caviarder")


def test_un_type_inconnu_est_refuse():
    with pytest.raises(ValueError, match="FR_NIRR"):
        analyser_politiques("FR_NIRR=masquer")


def test_analyse_de_la_variable_d_environnement():
    assert analyser_politiques("FR_NIR=masquer, TELEPHONE=conserver") == {
        "FR_NIR": "masquer",
        "TELEPHONE": "conserver",
    }
    assert analyser_politiques("") == {}


# --- Politique par dossier (vault) ------------------------------------------


def test_la_politique_du_dossier_prime_sur_le_defaut_d_instance():
    vault = VaultMemoire()
    vault.definir_politique("d1", {"actions": {"FR_NIR": "pseudonymiser"}})
    pseudo = pseudonymiseur(Politique(actions={"FR_NIR": "masquer"}), vault=vault)
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert "[NIR_001]" in resultat.texte
    # Un autre dossier suit le défaut d'instance.
    resultat2 = pseudo.pseudonymiser(TEXTE, dossier_id="d2")
    assert "[NIR]" in resultat2.texte


def test_la_politique_du_dossier_survit_au_redemarrage(tmp_path):
    chemin, cle = tmp_path / "vault.bin", generer_cle()
    vault = VaultChiffre(chemin, cle)
    vault.definir_politique("d1", {"actions": {"TELEPHONE": "conserver"}})
    rechargee = VaultChiffre(chemin, cle)
    assert rechargee.politique_dossier("d1") == {"actions": {"TELEPHONE": "conserver"}}


def test_le_fichier_vault_ne_contient_pas_la_politique_en_clair(tmp_path):
    # REQ-004 : tout le contenu du vault est chiffré, politique comprise.
    chemin, cle = tmp_path / "vault.bin", generer_cle()
    VaultChiffre(chemin, cle).definir_politique("d1", {"actions": {"FR_NIR": "masquer"}})
    assert b"masquer" not in chemin.read_bytes()


# --- Configuration par l'environnement --------------------------------------


def test_sas_politiques_invalide_refuse_le_demarrage():
    from sas_confiance_ia.configuration import ConfigurationInvalide, charger_configuration

    with pytest.raises(ConfigurationInvalide, match="SAS_POLITIQUES"):
        charger_configuration(
            {
                "SAS_BACKEND_BASE_URL": "http://localhost:11434/v1",
                "SAS_MODELES": "m",
                "SAS_POLITIQUES": "FR_NIR=nimporte",
            }
        )


def test_sas_politiques_est_chargee():
    from sas_confiance_ia.configuration import charger_configuration

    config = charger_configuration(
        {
            "SAS_BACKEND_BASE_URL": "http://localhost:11434/v1",
            "SAS_MODELES": "m",
            "SAS_POLITIQUES": "TELEPHONE=conserver",
        }
    )
    assert config.politiques == {"TELEPHONE": "conserver"}


def test_conserver_est_un_choix_journalise(caplog):
    # Couverture dégradée toujours explicite : conserver un type détectable
    # laisse une trace au démarrage.
    from sas_confiance_ia.configuration import charger_configuration

    with caplog.at_level("WARNING", logger="sas_confiance_ia.configuration"):
        charger_configuration(
            {
                "SAS_BACKEND_BASE_URL": "http://localhost:11434/v1",
                "SAS_MODELES": "m",
                "SAS_POLITIQUES": "TELEPHONE=conserver",
            }
        )
    assert any("conserver" in m and "TELEPHONE" in m for m in caplog.messages)


# --- UI et proxy -------------------------------------------------------------


@pytest.fixture
def application():
    return creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=BackendCapture(),
        modeles=["modele-de-test"],
    )


def test_l_ui_definit_la_politique_du_dossier(application):
    client = TestClient(application)
    corps = client.post(
        "/ui/pseudonymiser",
        json={
            "texte": TEXTE,
            "dossier_id": "d-ui",
            "mode": "serieux",
            "politiques": {"FR_NIR": "masquer"},
        },
    ).json()
    assert "[NIR]" in corps["texte"]
    # La politique est désormais celle du dossier : un appel suivant sans le
    # champ la conserve.
    corps2 = client.post(
        "/ui/pseudonymiser",
        json={"texte": TEXTE, "dossier_id": "d-ui", "mode": "serieux"},
    ).json()
    assert "[NIR]" in corps2["texte"]


def test_l_ui_refuse_une_politique_invalide(application):
    client = TestClient(application)
    reponse = client.post(
        "/ui/pseudonymiser",
        json={
            "texte": TEXTE,
            "dossier_id": "d-ui",
            "mode": "serieux",
            "politiques": {"FR_NIR": "caviarder"},
        },
    )
    assert reponse.status_code == 422
    assert "caviarder" in json.dumps(reponse.json())


def test_les_entites_en_revue_remontent_dans_l_ui(application):
    client = TestClient(application)
    corps = client.post(
        "/ui/pseudonymiser",
        json={
            "texte": TEXTE,
            "dossier_id": "d-ui",
            "mode": "serieux",
            "politiques": {"TELEPHONE": "revue"},
        },
    ).json()
    assert corps["entites_en_revue"] == ["[TELEPHONE_001]"]


def test_le_proxy_suit_la_politique_du_dossier_et_expose_la_revue():
    backend = BackendCapture()
    pseudo = Pseudonymiseur(VaultMemoire())
    application = creer_application(
        pseudonymiseur=pseudo, backend=backend, modeles=["modele-de-test"]
    )
    pseudo.vault.definir_politique(
        "d-proxy", {"actions": {"FR_NIR": "masquer", "TELEPHONE": "revue"}}
    )
    client = TestClient(application)
    corps = client.post(
        "/v1/chat/completions",
        json={"model": "modele-de-test", "messages": [{"role": "user", "content": TEXTE}]},
        headers={"X-Dossier-Id": "d-proxy"},
    ).json()
    (payload,) = backend.payloads_bruts
    # REQ-001 tenu sous toutes les actions : masqué et revue ne partent pas.
    assert NIR not in payload
    assert TELEPHONE not in payload
    assert "[NIR]" in payload
    assert corps["sas_confiance_ia"]["entites_en_revue"] == ["[TELEPHONE_001]"]
