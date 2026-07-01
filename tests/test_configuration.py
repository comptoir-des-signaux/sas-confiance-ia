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
    assert config.creer_moteurs() == []


def test_ner_mode_inconnu_refuse():
    with pytest.raises(ConfigurationInvalide, match="SAS_NER"):
        charger_configuration({**ENV_MINIMAL, "SAS_NER": "gpt4"})


def test_le_ner_est_actif_par_defaut_jamais_degrade_en_silence():
    # Interprétation protectrice (06-HANDOFF) : la couverture NER ne se perd
    # que par choix explicite (SAS_NER=inactif), jamais par oubli. Défaut
    # fail-closed : modèle absent = démarrage refusé avec message actionnable.
    config = charger_configuration(ENV_MINIMAL)
    assert config.ner == "transformers"


def test_ner_transformers_sans_modele_refuse_le_demarrage(monkeypatch):
    import sas_confiance_ia.configuration as module_config

    monkeypatch.setattr(module_config, "_dependances_ner_presentes", lambda: True)
    monkeypatch.setattr(module_config, "_modele_transformers_present", lambda: False)
    config = charger_configuration(ENV_MINIMAL)
    with pytest.raises(ConfigurationInvalide, match="telechargement"):
        config.creer_moteurs()


def test_ner_sans_extra_refuse_avec_message_actionnable(monkeypatch):
    import sas_confiance_ia.configuration as module_config

    monkeypatch.setattr(module_config, "_dependances_ner_presentes", lambda: False)
    config = charger_configuration(ENV_MINIMAL)
    with pytest.raises(ConfigurationInvalide, match=r"\[ner\]"):
        config.creer_moteurs()


def test_une_variable_vide_vaut_absente():
    # docker compose transmet ${VAR:-} : la chaîne vide ne doit pas être
    # traitée comme une valeur.
    config = charger_configuration(
        {
            **ENV_MINIMAL,
            "SAS_NER": "",
            "SAS_BACKEND_CLE_API": "",
            "SAS_VAULT_CHEMIN": "",
            "SAS_VAULT_CLE": "",
            "SAS_BACKEND_TIMEOUT_SECONDES": "",
        }
    )
    assert config.ner == "transformers"
    assert config.backend_cle_api is None
    assert config.vault_chemin is None
    assert config.backend_timeout > 0


def test_timeout_non_numerique_refuse():
    with pytest.raises(ConfigurationInvalide, match="SAS_BACKEND_TIMEOUT_SECONDES"):
        charger_configuration({**ENV_MINIMAL, "SAS_BACKEND_TIMEOUT_SECONDES": "deux minutes"})


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
