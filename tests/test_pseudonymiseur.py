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


def test_comptes_par_type_pour_le_journal():
    # REQ-003 : le journal ne connaît que des comptes par type, jamais les valeurs.
    pseudo = nouveau()
    r = pseudo.pseudonymiser(
        "Marie Martin, NIR 2 92 07 82 045 033 55, joignable au 06 12 34 56 78 "
        "ou marie.martin@exemple.fr.",
        dossier_id="d1",
    )
    assert r.comptes_par_type == {"FR_NIR": 1, "TELEPHONE": 1, "EMAIL": 1}
