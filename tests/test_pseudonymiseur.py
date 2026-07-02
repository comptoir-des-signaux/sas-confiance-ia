"""Lot 4 : pseudonymisation réversible et vault en mémoire (REQ-002, REQ-011 squelette)."""

import json
from pathlib import Path

from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

CORPUS = Path(__file__).parent.parent / "corpus" / "synthetique"


def nouveau() -> Pseudonymiseur:
    return Pseudonymiseur(VaultMemoire())


def test_aller_retour_exact_sur_tout_le_corpus():
    # REQ-002 : reidentifier(pseudonymiser(texte)) == texte.
    pseudo = nouveau()
    for chemin in sorted(CORPUS.rglob("*.md")):
        if chemin.name == "README.md":
            continue
        texte = chemin.read_text(encoding="utf-8")
        resultat = pseudo.pseudonymiser(texte, dossier_id="dossier-test")
        assert pseudo.reidentifier(resultat.texte, dossier_id="dossier-test") == texte


def test_les_valeurs_detectees_disparaissent_du_texte():
    pseudo = nouveau()
    oracle = json.loads((CORPUS / "valeurs-connues.json").read_text(encoding="utf-8"))
    doc = "01-courrier-usager.md"
    resultat = pseudo.pseudonymiser(
        (CORPUS / doc).read_text(encoding="utf-8"), dossier_id="d1"
    )
    for valeur in ["marie.martin@exemple.fr", "2 92 07 82 045 033 55", "06 12 34 56 78"]:
        assert valeur in oracle[doc]
        assert valeur not in resultat.texte


def test_meme_valeur_meme_placeholder_dans_un_dossier():
    # Squelette de REQ-011 : la cohérence vaut aussi entre deux textes
    # successifs du même dossier.
    pseudo = nouveau()
    r1 = pseudo.pseudonymiser("Écrire à jean.dupont@exemple.fr.", dossier_id="d1")
    r2 = pseudo.pseudonymiser("Relancer jean.dupont@exemple.fr lundi.", dossier_id="d1")
    (p1,) = [e.placeholder for e in r1.remplacements]
    (p2,) = [e.placeholder for e in r2.remplacements]
    assert p1 == p2 == "[EMAIL_001]"


def test_deux_dossiers_sont_isoles():
    pseudo = nouveau()
    pseudo.pseudonymiser("Écrire à jean.dupont@exemple.fr.", dossier_id="d1")
    r2 = pseudo.pseudonymiser("Écrire à marie.martin@exemple.fr.", dossier_id="d2")
    (p2,) = [e.placeholder for e in r2.remplacements]
    # Le dossier d2 démarre sa propre numérotation.
    assert p2 == "[EMAIL_001]"
    assert pseudo.reidentifier("[EMAIL_001]", dossier_id="d2") == "marie.martin@exemple.fr"
    assert pseudo.reidentifier("[EMAIL_001]", dossier_id="d1") == "jean.dupont@exemple.fr"


def test_deux_valeurs_distinctes_deux_placeholders():
    pseudo = nouveau()
    r = pseudo.pseudonymiser(
        "Contacter jean.dupont@exemple.fr et marie.martin@exemple.fr.", dossier_id="d1"
    )
    placeholders = [e.placeholder for e in r.remplacements]
    assert placeholders == ["[EMAIL_001]", "[EMAIL_002]"]


def test_pseudonymisation_avec_moteur_additionnel():
    # Lot 9 : les candidats d'un moteur (NER) sont pseudonymisés et réversibles
    # comme ceux de la couche déterministe.
    from sas_confiance_ia.detection import EntiteDetectee

    class MoteurFactice:
        def reconnaitre(self, texte: str):
            valeur = "Marie Martin"
            debut = texte.find(valeur)
            if debut < 0:
                return []
            return [
                EntiteDetectee(
                    type="PERSONNE", debut=debut, fin=debut + len(valeur), score=0.9, valeur=valeur
                )
            ]

    pseudo = Pseudonymiseur(VaultMemoire(), moteurs=[MoteurFactice()])
    texte = "Marie Martin, joignable à marie.martin@exemple.fr, est passée."
    resultat = pseudo.pseudonymiser(texte, dossier_id="d1")
    assert "[PERSONNE_001]" in resultat.texte
    assert "Marie Martin" not in resultat.texte
    assert resultat.comptes_par_type == {"PERSONNE": 1, "EMAIL": 1}
    assert pseudo.reidentifier(resultat.texte, dossier_id="d1") == texte


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


def test_req_011_meme_placeholder_entre_deux_pieces():
    # Acceptance REQ-011 : « Jean Dupont » (pièce 1) et « M. Dupont »
    # (pièce 2) reçoivent le même [PERSONNE_001] dans le même dossier.
    pseudo = Pseudonymiseur(
        VaultMemoire(), moteurs=[MoteurPersonnes("Jean Dupont", "M. Dupont")]
    )
    r1 = pseudo.pseudonymiser("Jean Dupont conteste la décision.", dossier_id="d1")
    r2 = pseudo.pseudonymiser("La réclamation de M. Dupont est fondée.", dossier_id="d1")
    assert "[PERSONNE_001]" in r1.texte
    assert "[PERSONNE_001]" in r2.texte
    assert "Dupont" not in r2.texte


def test_la_reidentification_restaure_la_forme_canonique():
    # Arbitrage Q1 (QUESTIONS.md) : la restitution est la forme la plus
    # complète connue, pas la forme de surface de chaque mention.
    pseudo = Pseudonymiseur(
        VaultMemoire(), moteurs=[MoteurPersonnes("Jean Dupont", "M. Dupont")]
    )
    pseudo.pseudonymiser("Jean Dupont conteste la décision.", dossier_id="d1")
    r2 = pseudo.pseudonymiser("La réclamation de M. Dupont est fondée.", dossier_id="d1")
    assert pseudo.reidentifier(r2.texte, dossier_id="d1") == (
        "La réclamation de Jean Dupont est fondée."
    )


def test_sans_coreference_l_aller_retour_reste_exact_au_caractere_pres():
    pseudo = Pseudonymiseur(
        VaultMemoire(),
        moteurs=[MoteurPersonnes("Jean Dupont", "M. Dupont")],
        coreference=False,
    )
    for texte in ["Jean Dupont conteste.", "La réclamation de M. Dupont est fondée."]:
        r = pseudo.pseudonymiser(texte, dossier_id="d1")
        assert pseudo.reidentifier(r.texte, dossier_id="d1") == texte


def test_les_ambiguites_sont_exposees():
    pseudo = Pseudonymiseur(
        VaultMemoire(),
        moteurs=[MoteurPersonnes("Jean Dupont", "Marie Dupont", "M. Dupont")],
    )
    pseudo.pseudonymiser("Jean Dupont et Marie Dupont sont présents.", dossier_id="d1")
    r = pseudo.pseudonymiser("M. Dupont a signé.", dossier_id="d1")
    assert r.ambiguites == ["[PERSONNE_003]"]


def test_les_ambiguites_sont_celles_de_l_appel_pas_du_dossier():
    pseudo = Pseudonymiseur(
        VaultMemoire(),
        moteurs=[MoteurPersonnes("Jean Dupont", "Marie Dupont", "M. Dupont", "Karim Haddad")],
    )
    pseudo.pseudonymiser("Jean Dupont et Marie Dupont sont présents.", dossier_id="d1")
    r2 = pseudo.pseudonymiser("M. Dupont a signé.", dossier_id="d1")
    assert r2.ambiguites == ["[PERSONNE_003]"]
    r3 = pseudo.pseudonymiser("Karim Haddad valide.", dossier_id="d1")
    assert r3.ambiguites == []


def test_les_ambiguites_remontent_dans_la_reponse_du_proxy():
    from fastapi.testclient import TestClient

    from sas_confiance_ia.api import creer_application
    from sas_confiance_ia.backends import BackendCapture

    application = creer_application(
        pseudonymiseur=Pseudonymiseur(
            VaultMemoire(),
            moteurs=[MoteurPersonnes("Jean Dupont", "Marie Dupont", "M. Dupont")],
        ),
        backend=BackendCapture(),
        modeles=["modele-de-test"],
    )
    client = TestClient(application)

    def completion(texte: str) -> dict:
        return client.post(
            "/v1/chat/completions",
            json={"model": "modele-de-test", "messages": [{"role": "user", "content": texte}]},
            headers={"X-Dossier-Id": "d1"},
        ).json()

    corps = completion("Jean Dupont et Marie Dupont sont présents.")
    assert corps["sas_confiance_ia"]["ambiguites_coreference"] == []
    corps = completion("M. Dupont a signé.")
    assert corps["sas_confiance_ia"]["ambiguites_coreference"] == ["[PERSONNE_003]"]


def test_comptes_par_type_pour_le_journal():
    # REQ-003 : le journal ne connaît que des comptes par type, jamais les valeurs.
    pseudo = nouveau()
    r = pseudo.pseudonymiser(
        "Marie Martin, NIR 2 92 07 82 045 033 55, joignable au 06 12 34 56 78 "
        "ou marie.martin@exemple.fr.",
        dossier_id="d1",
    )
    assert r.comptes_par_type == {"FR_NIR": 1, "TELEPHONE": 1, "EMAIL": 1}
