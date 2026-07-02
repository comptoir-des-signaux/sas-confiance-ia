"""Lot 7 : intégrité des réponses IA (REQ-006) et ré-identification pilotée.

Cas du cadrage §14.6 : placeholder conservé, altéré, inventé, supprimé.
Lecture tolérante des placeholders altérés, blocage des inconnus.
"""

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.integrite import normaliser_placeholders
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire


def client_avec_reponse(contenu: str) -> TestClient:
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=BackendCapture(contenu_reponse=contenu),
        modeles=["modele-de-test"],
    )
    return TestClient(application)


def completion(client: TestClient, texte: str, **headers) -> dict:
    reponse = client.post(
        "/v1/chat/completions",
        json={"model": "modele-de-test", "messages": [{"role": "user", "content": texte}]},
        headers={"X-Dossier-Id": "dossier-test", **headers},
    )
    assert reponse.status_code == 200
    return reponse.json()


def test_placeholder_conserve_reidentifie_par_defaut():
    client = client_avec_reponse("Courrier rédigé pour [EMAIL_001], à relire.")
    corps = completion(client, "Écrire à jean.dupont@exemple.fr.")
    assert corps["choices"][0]["message"]["content"] == (
        "Courrier rédigé pour jean.dupont@exemple.fr, à relire."
    )
    rapport = corps["sas_confiance_ia"]["integrite"]
    assert rapport["integrite_ok"] is True
    assert rapport["action"] == "ok"
    assert corps["sas_confiance_ia"]["reidentifie"] is True


def test_reidentification_desactivable():
    client = client_avec_reponse("Courrier pour [EMAIL_001].")
    corps = completion(
        client, "Écrire à jean.dupont@exemple.fr.", **{"X-Reidentify-Response": "false"}
    )
    assert "[EMAIL_001]" in corps["choices"][0]["message"]["content"]
    assert corps["sas_confiance_ia"]["reidentifie"] is False


def test_placeholder_invente_bloque_la_reidentification():
    # REQ-006 : jamais de réponse finale silencieuse en présence d'un inconnu.
    client = client_avec_reponse("Réponse citant [EMAIL_001] et [PERSONNE_999].")
    corps = completion(client, "Écrire à jean.dupont@exemple.fr.")
    rapport = corps["sas_confiance_ia"]["integrite"]
    assert rapport["integrite_ok"] is False
    assert rapport["placeholders_inconnus"] == ["[PERSONNE_999]"]
    assert rapport["action"] == "review_required"
    # La réponse reste pseudonymisée : aucune valeur réelle n'est réinjectée.
    contenu = corps["choices"][0]["message"]["content"]
    assert "jean.dupont@exemple.fr" not in contenu
    assert corps["sas_confiance_ia"]["reidentifie"] is False


def test_placeholder_supprime_est_signale():
    client = client_avec_reponse("Résumé sans aucune coordonnée.")
    corps = completion(client, "Écrire à jean.dupont@exemple.fr.")
    rapport = corps["sas_confiance_ia"]["integrite"]
    assert rapport["placeholders_manquants"] == ["[EMAIL_001]"]
    assert rapport["integrite_ok"] is True


def test_placeholder_altere_est_lu_avec_tolerance():
    # F5 du 02-AI-SPEC : tolérant en lecture ([EMAIL_01], [EMAIL 001]),
    # bloquant si la normalisation ne retombe pas sur un placeholder connu.
    client = client_avec_reponse("Contact : [EMAIL_01] ou [EMAIL 001].")
    corps = completion(client, "Écrire à jean.dupont@exemple.fr.")
    contenu = corps["choices"][0]["message"]["content"]
    assert contenu == "Contact : jean.dupont@exemple.fr ou jean.dupont@exemple.fr."


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("[EMAIL_01]", "[EMAIL_001]"),
        ("[EMAIL 001]", "[EMAIL_001]"),
        ("[DATE_NAISSANCE_2]", "[DATE_NAISSANCE_002]"),
        ("[EMAIL_001]", "[EMAIL_001]"),
        ("texte sans jeton", "texte sans jeton"),
    ],
)
def test_normalisation_des_placeholders(brut, attendu):
    assert normaliser_placeholders(brut) == attendu


# Altérations constatées sur un vrai backend (mistral-small:24b via Ollama,
# 2026-07-02) : crochets perdus, casse changée, type mal orthographié.
@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("Bonjour Personne_001.", "Bonjour [PERSONNE_001]."),
        ("[personne 1] écrit à EMAIL_001", "[PERSONNE_001] écrit à [EMAIL_001]"),
        ("dossier REFERANCE_001 rejeté", "dossier [REFERENCE_001] rejeté"),
        ("[Référence_001]", "[REFERENCE_001]"),
        # Sans crochets, l'espace n'est pas un séparateur : « personne 1 »
        # peut être du français ordinaire.
        ("il n'y a personne 1 minute", "il n'y a personne 1 minute"),
        ("voir l'annexe 3 et l'article_12", "voir l'annexe 3 et l'article_12"),
    ],
)
def test_restauration_des_placeholders_alteres_connus(brut, attendu):
    connus = {"[PERSONNE_001]", "[EMAIL_001]", "[REFERENCE_001]"}
    assert normaliser_placeholders(brut, connus=connus) == attendu


def test_un_pseudo_placeholder_non_restaurable_bloque():
    # « PERSONNE_999 » sans crochets : type reconnaissable, numéro inconnu
    # du vault : impossible à restaurer, la réponse part en revue (REQ-006).
    from sas_confiance_ia.integrite import controler

    rapport = controler(
        "Voir PERSONNE_999 pour la suite.",
        placeholders_envoyes={"[PERSONNE_001]"},
        placeholders_connus={"[PERSONNE_001]"},
    )
    assert rapport.integrite_ok is False
    assert "[PERSONNE_999]" in rapport.placeholders_inconnus


def test_le_texte_ordinaire_ne_declenche_pas_le_controle():
    from sas_confiance_ia.integrite import controler

    rapport = controler(
        "Voir l'annexe 3, l'article_12 et le point 4.",
        placeholders_envoyes=set(),
        placeholders_connus={"[PERSONNE_001]"},
    )
    assert rapport.integrite_ok is True
    assert rapport.placeholders_inconnus == []


def test_bout_en_bout_placeholder_sans_crochets_reidentifie():
    client = client_avec_reponse("Merci d'écrire à Email_001 rapidement.")
    corps = completion(client, "Écrire à jean.dupont@exemple.fr.")
    assert corps["choices"][0]["message"]["content"] == (
        "Merci d'écrire à jean.dupont@exemple.fr rapidement."
    )
    assert corps["sas_confiance_ia"]["integrite"]["action"] == "ok"


def test_la_consigne_de_preservation_des_jetons_est_injectee():
    # Parade F5 (02-AI-SPEC §3) : consigne système demandant la préservation
    # exacte des jetons, injectée seulement quand il y a des placeholders.
    backend = BackendCapture(contenu_reponse="Bien reçu.")
    application = creer_application(
        pseudonymiseur=Pseudonymiseur(VaultMemoire()),
        backend=backend,
        modeles=["modele-de-test"],
    )
    client = TestClient(application)
    completion(client, "Écrire à jean.dupont@exemple.fr.")
    assert '"role": "system"' in backend.payloads_bruts[-1]
    assert "jetons" in backend.payloads_bruts[-1]

    completion(client, "Quelle est la capitale de la France ?")
    assert '"role": "system"' not in backend.payloads_bruts[-1]
