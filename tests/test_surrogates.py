"""Lot 14 : surrogates réalistes cohérents en genre (REQ-012, arbitrage Q5).

Le vault garde ses placeholders [PERSONNE_NNN] en interne (coréférence,
compteurs et forme canonique intacts) ; le mode surrogate est une couche de
rendu par dossier : le texte envoyé porte un nom factice Faker fr_FR, la
ré-identification et le contrôle d'intégrité repassent par le placeholder.
Portée v1 : PERSONNE uniquement, les autres types gardent leurs placeholders.
"""

import json

import pytest
from fastapi.testclient import TestClient

from sas_confiance_ia.api import creer_application
from sas_confiance_ia.backends import BackendCapture
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.surrogates import GenerateurSurrogates
from sas_confiance_ia.vault import VaultChiffre, VaultMemoire, generer_cle

TEXTE = (
    "Monsieur Karim Benhaddou, joignable à k.benhaddou@exemple-fictif.fr, "
    "et Madame Sophie Delmas demandent un rendez-vous."
)


class MoteurPersonnes:
    """Faux NER : détecte des mentions de personnes fixées à l'avance."""

    def __init__(self, *mentions: str) -> None:
        self._mentions = mentions

    def reconnaitre(self, texte: str):
        from sas_confiance_ia.detection import EntiteDetectee

        entites = []
        for mention in self._mentions:
            debut = texte.find(mention)
            if debut >= 0:
                entites.append(
                    EntiteDetectee(
                        type="PERSONNE",
                        debut=debut,
                        fin=debut + len(mention),
                        score=0.9,
                        valeur=mention,
                    )
                )
        return entites


def pseudonymiseur_surrogates(vault=None, graine: int = 42) -> Pseudonymiseur:
    vault = vault or VaultMemoire()
    vault.definir_politique("d1", {"surrogates": True})
    return Pseudonymiseur(
        vault,
        moteurs=[
            MoteurPersonnes("Monsieur Karim Benhaddou", "Madame Sophie Delmas", "M. Benhaddou")
        ],
        generateur_surrogates=GenerateurSurrogates(graine=graine),
    )


# --- Générateur --------------------------------------------------------------


def test_le_generateur_respecte_le_genre_demande():
    from faker.providers.person.fr_FR import Provider

    generateur = GenerateurSurrogates(graine=7)
    homme = generateur.nom_personne("m", interdits=set())
    femme = generateur.nom_personne("f", interdits=set())
    assert homme.split()[0] in Provider.first_names_male
    assert femme.split()[0] in Provider.first_names_female


def test_le_generateur_evite_les_noms_interdits():
    premier = GenerateurSurrogates(graine=7).nom_personne("m", interdits=set())
    second = GenerateurSurrogates(graine=7).nom_personne("m", interdits={premier})
    assert second != premier


# --- Pseudonymisation --------------------------------------------------------


def test_le_texte_surrogate_porte_des_noms_factices_pas_de_placeholders_personne():
    pseudo = pseudonymiseur_surrogates()
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert "Karim Benhaddou" not in resultat.texte
    assert "Sophie Delmas" not in resultat.texte
    assert "[PERSONNE" not in resultat.texte
    # Portée v1 : les autres types gardent leurs placeholders typés.
    assert "[EMAIL_001]" in resultat.texte


def test_le_genre_des_surrogates_correspond_aux_civilites():
    # Acceptance REQ-012 : sur le corpus de test, le genre grammatical des
    # substituts correspond à celui des originaux.
    from faker.providers.person.fr_FR import Provider

    pseudo = pseudonymiseur_surrogates()
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    surrogates = {
        r.entite.valeur: r.surrogate for r in resultat.remplacements if r.surrogate
    }
    assert surrogates["Monsieur Karim Benhaddou"].split()[0] in Provider.first_names_male
    assert surrogates["Madame Sophie Delmas"].split()[0] in Provider.first_names_female


def test_la_reversibilite_est_exacte_dans_les_deux_modes():
    # Acceptance REQ-012 : même corpus, réversibilité exacte avec et sans
    # surrogates (à la forme canonique près pour les alias, comme partout).
    avec = pseudonymiseur_surrogates()
    r_avec = avec.pseudonymiser(TEXTE, dossier_id="d1")
    assert avec.reidentifier(r_avec.texte, dossier_id="d1") == TEXTE

    sans = Pseudonymiseur(
        VaultMemoire(),
        moteurs=[MoteurPersonnes("Monsieur Karim Benhaddou", "Madame Sophie Delmas")],
    )
    r_sans = sans.pseudonymiser(TEXTE, dossier_id="d1")
    assert sans.reidentifier(r_sans.texte, dossier_id="d1") == TEXTE


def test_un_alias_coreference_recoit_le_meme_surrogate():
    pseudo = pseudonymiseur_surrogates()
    r1 = pseudo.pseudonymiser("Monsieur Karim Benhaddou conteste.", dossier_id="d1")
    r2 = pseudo.pseudonymiser("M. Benhaddou a signé.", dossier_id="d1")
    (s1,) = [r.surrogate for r in r1.remplacements]
    (s2,) = [r.surrogate for r in r2.remplacements]
    assert s1 == s2


def test_deux_personnes_deux_surrogates_distincts():
    pseudo = pseudonymiseur_surrogates()
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    surrogates = [r.surrogate for r in resultat.remplacements if r.surrogate]
    assert len(surrogates) == len(set(surrogates)) == 2


def test_un_surrogate_ne_reprend_jamais_un_nom_du_texte():
    # Sinon la ré-identification restituerait le mauvais nom à cet endroit.
    class GenerateurTetu:
        def __init__(self):
            self.appels = []

        def nom_personne(self, genre, interdits):
            self.appels.append(set(interdits))
            return "Nom Factice"

    vault = VaultMemoire()
    vault.definir_politique("d1", {"surrogates": True})
    pseudo = Pseudonymiseur(
        vault,
        moteurs=[MoteurPersonnes("Monsieur Karim Benhaddou")],
        generateur_surrogates=GenerateurTetu(),
    )
    pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    # Les valeurs réelles du dossier font partie des interdits transmis.
    assert any("Monsieur Karim Benhaddou" in interdits for interdits in pseudo_appels(pseudo))


def pseudo_appels(pseudo):
    return pseudo._generateur_surrogates.appels


def test_les_surrogates_survivent_au_redemarrage(tmp_path):
    chemin, cle = tmp_path / "vault.bin", generer_cle()
    vault = VaultChiffre(chemin, cle)
    pseudo = pseudonymiseur_surrogates(vault=vault)
    r1 = pseudo.pseudonymiser("Monsieur Karim Benhaddou conteste.", dossier_id="d1")
    (s1,) = [r.surrogate for r in r1.remplacements]

    recharge = VaultChiffre(chemin, cle)
    pseudo2 = Pseudonymiseur(
        recharge,
        moteurs=[MoteurPersonnes("M. Benhaddou")],
        generateur_surrogates=GenerateurSurrogates(graine=99),
    )
    r2 = pseudo2.pseudonymiser("M. Benhaddou a signé.", dossier_id="d1")
    (s2,) = [r.surrogate for r in r2.remplacements]
    assert s2 == s1
    # REQ-004 : le fichier ne contient ni la valeur ni le surrogate en clair.
    assert b"Benhaddou" not in chemin.read_bytes()
    assert s1.encode() not in chemin.read_bytes()


# --- Proxy : REQ-001 et intégrité (Q5) ---------------------------------------


@pytest.fixture
def application_surrogates():
    vault = VaultMemoire()
    vault.definir_politique("d-s", {"surrogates": True})
    backend = BackendCapture()
    pseudo = Pseudonymiseur(
        vault,
        moteurs=[MoteurPersonnes("Monsieur Karim Benhaddou")],
        generateur_surrogates=GenerateurSurrogates(graine=42),
    )
    application = creer_application(
        pseudonymiseur=pseudo, backend=backend, modeles=["modele-de-test"]
    )
    return application, backend, pseudo


def completion(application, texte: str, dossier: str = "d-s") -> dict:
    client = TestClient(application)
    return client.post(
        "/v1/chat/completions",
        json={"model": "modele-de-test", "messages": [{"role": "user", "content": texte}]},
        headers={"X-Dossier-Id": dossier},
    ).json()


def test_req_001_le_payload_porte_le_surrogate_jamais_la_valeur(application_surrogates):
    application, backend, pseudo = application_surrogates
    completion(application, "Monsieur Karim Benhaddou conteste la décision.")
    (payload,) = backend.payloads_bruts
    assert "Benhaddou" not in payload
    assert "[PERSONNE" not in payload
    surrogate = pseudo.vault.surrogates_dossier("d-s")["[PERSONNE_001]"]
    assert surrogate in payload
    # Aucun placeholder dans le payload : la consigne de préservation des
    # jetons n'a rien à protéger et n'est pas injectée.
    assert "jetons de pseudonymisation" not in payload


def test_la_reponse_qui_reprend_le_surrogate_est_reidentifiee(application_surrogates):
    application, backend, pseudo = application_surrogates
    # Amorce : le surrogate est créé au premier passage.
    completion(application, "Monsieur Karim Benhaddou conteste la décision.")
    surrogate = pseudo.vault.surrogates_dossier("d-s")["[PERSONNE_001]"]
    backend.contenu_reponse = f"Le recours de {surrogate} est recevable."
    corps = completion(application, "Monsieur Karim Benhaddou insiste.")
    assert corps["choices"][0]["message"]["content"] == (
        "Le recours de Monsieur Karim Benhaddou est recevable."
    )
    assert corps["sas_confiance_ia"]["integrite"]["integrite_ok"] is True


def test_un_surrogate_absent_de_la_reponse_est_signale_manquant(application_surrogates):
    application, backend, _ = application_surrogates
    backend.contenu_reponse = "Réponse qui ne cite personne."
    corps = completion(application, "Monsieur Karim Benhaddou conteste.")
    assert corps["sas_confiance_ia"]["integrite"]["placeholders_manquants"] == [
        "[PERSONNE_001]"
    ]


# --- UI ----------------------------------------------------------------------


def test_l_ui_active_les_surrogates_par_dossier():
    vault = VaultMemoire()
    pseudo = Pseudonymiseur(
        vault,
        moteurs=[MoteurPersonnes("Monsieur Karim Benhaddou")],
        generateur_surrogates=GenerateurSurrogates(graine=42),
    )
    application = creer_application(
        pseudonymiseur=pseudo, backend=BackendCapture(), modeles=["modele-de-test"]
    )
    client = TestClient(application)
    corps = client.post(
        "/ui/pseudonymiser",
        json={
            "texte": "Monsieur Karim Benhaddou conteste.",
            "dossier_id": "d-ui",
            "mode": "serieux",
            "surrogates": True,
        },
    ).json()
    assert "Benhaddou" not in json.dumps(corps["texte"])
    assert "[PERSONNE" not in corps["texte"]
    # Le choix vit dans le vault : l'appel suivant sans le champ le garde.
    corps2 = client.post(
        "/ui/pseudonymiser",
        json={
            "texte": "Monsieur Karim Benhaddou insiste.",
            "dossier_id": "d-ui",
            "mode": "serieux",
        },
    ).json()
    assert "[PERSONNE" not in corps2["texte"]
