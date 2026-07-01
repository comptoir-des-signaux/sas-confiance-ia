"""Lot 10 : configuration d'exécution par variables d'environnement (REQ-013).

Rien en dur : base URL, clé API, modèles, NER et vault viennent de
l'environnement. Les choix par défaut sont les plus protecteurs : vault en
mémoire (rien n'est écrit sans clé fournie), NER activé si disponible.
"""

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.configuration import (
    ConfigurationInvalide,
    charger_configuration,
    creer_application_depuis_environnement,
)
from sas_confiance_ia.vault import VaultChiffre, VaultMemoire, generer_cle

ENV_MINIMAL = {
    "SAS_BACKEND_BASE_URL": "http://localhost:11434/v1",
    "SAS_MODELES": "mistral-small",
}


def test_configuration_minimale():
    config = charger_configuration(ENV_MINIMAL)
    assert config.backend_base_url == "http://localhost:11434/v1"
    assert config.modeles == ["mistral-small"]
    assert config.backend_cle_api is None
    assert config.backend_timeout > 0


def test_base_url_est_requise():
    with pytest.raises(ConfigurationInvalide, match="SAS_BACKEND_BASE_URL"):
        charger_configuration({"SAS_MODELES": "mistral-small"})


def test_les_modeles_sont_requis():
    with pytest.raises(ConfigurationInvalide, match="SAS_MODELES"):
        charger_configuration({"SAS_BACKEND_BASE_URL": "http://localhost:11434/v1"})


def test_liste_de_modeles_separee_par_virgules():
    config = charger_configuration(
        {**ENV_MINIMAL, "SAS_MODELES": "mistral-small, qwen3:14b ,llama3"}
    )
    assert config.modeles == ["mistral-small", "qwen3:14b", "llama3"]


def test_cle_api_et_timeout():
    config = charger_configuration(
        {**ENV_MINIMAL, "SAS_BACKEND_CLE_API": "cle-x", "SAS_BACKEND_TIMEOUT_SECONDES": "30"}
    )
    assert config.backend_cle_api == "cle-x"
    assert config.backend_timeout == 30.0


def test_ner_inactif_explicite():
    config = charger_configuration({**ENV_MINIMAL, "SAS_NER": "inactif"})
    assert config.ner == "inactif"


def test_ner_mode_inconnu_refuse():
    with pytest.raises(ConfigurationInvalide, match="SAS_NER"):
        charger_configuration({**ENV_MINIMAL, "SAS_NER": "gpt4"})


def test_vault_memoire_par_defaut():
    # Défaut protecteur : rien n'est écrit sur disque sans chemin ET clé.
    config = charger_configuration(ENV_MINIMAL)
    assert isinstance(config.creer_vault(), VaultMemoire)
    assert not isinstance(config.creer_vault(), VaultChiffre)


def test_vault_chiffre_avec_chemin_et_cle(tmp_path):
    config = charger_configuration(
        {
            **ENV_MINIMAL,
            "SAS_VAULT_CHEMIN": str(tmp_path / "vault.sas"),
            "SAS_VAULT_CLE": generer_cle().decode(),
        }
    )
    assert isinstance(config.creer_vault(), VaultChiffre)


def test_vault_chemin_sans_cle_refuse(tmp_path):
    with pytest.raises(ConfigurationInvalide, match="SAS_VAULT_CLE"):
        charger_configuration({**ENV_MINIMAL, "SAS_VAULT_CHEMIN": str(tmp_path / "v.sas")})


def test_application_cablee_depuis_l_environnement():
    application = creer_application_depuis_environnement(
        {**ENV_MINIMAL, "SAS_NER": "inactif", "SAS_MODELES": "mistral-small,llama3"}
    )
    client = TestClient(application)
    assert client.get("/health").status_code == 200
    identifiants = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert identifiants == ["mistral-small", "llama3"]
