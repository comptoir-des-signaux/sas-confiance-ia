"""Lot 9 : NER français CamemBERT (couche C2), REQ-016 complet.

Ces tests exigent l'extra [ner] et le modèle téléchargé localement
(python -m sas_confiance_ia.telechargement). Ils sont sautés proprement si
le modèle est absent, mais la CI publique les exécute (job dédié) : sans
eux, le rappel PERSONNE / ORGANISATION / LIEU n'est pas prouvé.

Aucun téléchargement au moment du test : le moteur charge le modèle épinglé
depuis le cache local uniquement (HANDOFF, règle 1 ; garde-fou réseau du
conftest en vigueur).
"""

from pathlib import Path

import pytest

from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

from .conftest import moteur_ner_disponible

CORPUS = Path(__file__).parent.parent / "corpus" / "synthetique"

pytestmark = [
    pytest.mark.ner,
    pytest.mark.skipif(
        not moteur_ner_disponible(),
        reason="modèle NER absent : installer l'extra [ner] puis "
        "python -m sas_confiance_ia.telechargement",
    ),
]


# Personnes de l'oracle que la couche C2 doit reconnaître (vérité terrain
# du corpus synthétique ; les canaris 06 sont hors périmètre NER par
# construction, 02-AI-SPEC §4.3).
PERSONNES_ATTENDUES = [
    ("01-courrier-usager.md", "Marie Martin"),
    ("02-note-rh.md", "Sophie Robert"),
    ("02-note-rh.md", "Paul Bernard"),
    ("02-note-rh.md", "Isabelle Costa"),
    ("03-contrat-prestation.md", "Karim Haddad"),
    ("04-dossier-usager/piece-1-courrier.md", "Jean Dupont"),
    ("05-compte-rendu-reunion.md", "Claude Fabre"),
    ("05-compte-rendu-reunion.md", "Nadia Benali"),
    ("05-compte-rendu-reunion.md", "Lucienne Vergnes"),
    ("05-compte-rendu-reunion.md", "Thierry Lacoste"),
]


def _couvert(entites, texte: str, valeur: str, types: set[str]) -> bool:
    """Vrai si chaque occurrence de `valeur` est recouverte par une entité des types donnés."""
    debut = texte.find(valeur)
    while debut >= 0:
        fin = debut + len(valeur)
        if not any(e.debut <= debut and e.fin >= fin and e.type in types for e in entites):
            return False
        debut = texte.find(valeur, debut + 1)
    return True


def test_les_personnes_du_corpus_sont_reconnues(moteur_ner):
    manques = []
    for doc, nom in PERSONNES_ATTENDUES:
        texte = (CORPUS / doc).read_text(encoding="utf-8")
        entites = moteur_ner.reconnaitre(texte)
        if not _couvert(entites, texte, nom, {"PERSONNE"}):
            manques.append((doc, nom))
    assert not manques, f"personnes non reconnues par le NER : {manques}"


def test_une_organisation_du_corpus_est_reconnue(moteur_ner):
    texte = (CORPUS / "03-contrat-prestation.md").read_text(encoding="utf-8")
    entites = moteur_ner.reconnaitre(texte)
    assert _couvert(entites, texte, "Nettoyage Occitan", {"ORGANISATION", "PERSONNE", "LIEU"}), (
        "« Nettoyage Occitan » n'est recouvert par aucune entité NER"
    )


def test_des_lieux_du_corpus_sont_reconnus(moteur_ner):
    texte = (CORPUS / "04-dossier-usager/piece-1-courrier.md").read_text(encoding="utf-8")
    entites = moteur_ner.reconnaitre(texte)
    assert _couvert(entites, texte, "Annecy", {"LIEU"})


def test_les_types_retournes_sont_ceux_du_sas(moteur_ner):
    texte = (CORPUS / "05-compte-rendu-reunion.md").read_text(encoding="utf-8")
    types = {e.type for e in moteur_ner.reconnaitre(texte)}
    assert types <= {"PERSONNE", "ORGANISATION", "LIEU"}
    assert "PERSONNE" in types


def test_les_positions_ner_correspondent_au_texte(moteur_ner):
    texte = (CORPUS / "01-courrier-usager.md").read_text(encoding="utf-8")
    for entite in moteur_ner.reconnaitre(texte):
        assert texte[entite.debut : entite.fin] == entite.valeur


def test_le_nir_reste_prioritaire_sur_le_ner(moteur_ner):
    # REQ-016 : un empan NER ne dégrade jamais une détection déterministe.
    from sas_confiance_ia.detection import detecter

    texte = (CORPUS / "01-courrier-usager.md").read_text(encoding="utf-8")
    entites = detecter(texte, moteurs=[moteur_ner])
    assert any(e.type == "FR_NIR" and e.valeur == "2 92 07 82 045 033 55" for e in entites)


def test_aller_retour_exact_avec_ner_sur_tout_le_corpus(moteur_ner):
    # REQ-002 tenue au périmètre complet : la réversibilité au caractère
    # près survit au NER. Coréférence désactivée ici : avec elle, la
    # restitution est la forme canonique (arbitrage Q1, QUESTIONS.md),
    # vérifiée par test_req_011_coreference_sur_le_dossier_multi_pieces.
    pseudo = Pseudonymiseur(VaultMemoire(), moteurs=[moteur_ner], coreference=False)
    for chemin in sorted(CORPUS.rglob("*.md")):
        if chemin.name == "README.md":
            continue
        texte = chemin.read_text(encoding="utf-8")
        resultat = pseudo.pseudonymiser(texte, dossier_id="dossier-ner")
        assert pseudo.reidentifier(resultat.texte, dossier_id="dossier-ner") == texte


def test_req_011_coreference_sur_le_dossier_multi_pieces(moteur_ner):
    # Acceptance REQ-011 sur le corpus réel : « Jean Dupont » (pièce 1) et
    # « M. Dupont » (pièce 2) reçoivent le même placeholder ; plus aucun
    # « Dupont » ne subsiste dans les textes pseudonymisés.
    pseudo = Pseudonymiseur(VaultMemoire(), moteurs=[moteur_ner])
    r1 = pseudo.pseudonymiser(
        (CORPUS / "04-dossier-usager/piece-1-courrier.md").read_text(encoding="utf-8"),
        dossier_id="dossier-011",
    )
    r2 = pseudo.pseudonymiser(
        (CORPUS / "04-dossier-usager/piece-2-note-interne.md").read_text(encoding="utf-8"),
        dossier_id="dossier-011",
    )
    assert "Dupont" not in r1.texte
    assert "Dupont" not in r2.texte
    (placeholder_jean,) = {
        r.placeholder for r in r1.remplacements if "Dupont" in r.entite.valeur
    }
    placeholders_piece_2 = {
        r.placeholder for r in r2.remplacements if "Dupont" in r.entite.valeur
    }
    assert placeholders_piece_2 == {placeholder_jean}


def test_pseudonymisation_efface_les_noms(moteur_ner):
    pseudo = Pseudonymiseur(VaultMemoire(), moteurs=[moteur_ner])
    texte = (CORPUS / "01-courrier-usager.md").read_text(encoding="utf-8")
    resultat = pseudo.pseudonymiser(texte, dossier_id="d-ner")
    assert "Marie Martin" not in resultat.texte
    assert "[PERSONNE_001]" in resultat.texte


def test_un_moteur_inconnu_est_refuse():
    from sas_confiance_ia.ner import creer_moteur_ner

    with pytest.raises(ValueError, match="transformers ou spacy"):
        creer_moteur_ner(moteur="ollama")


def _repli_spacy_disponible() -> bool:
    import importlib.util

    from sas_confiance_ia.ner import MODELE_SPACY_REPLI

    return importlib.util.find_spec(MODELE_SPACY_REPLI) is not None


@pytest.mark.skipif(
    not _repli_spacy_disponible(),
    reason="repli spaCy absent : installer l'extra [ner-repli-spacy]",
)
def test_le_repli_spacy_reconnait_les_personnes():
    # 02-AI-SPEC §1 : repli configurable pour machine modeste, même interface.
    from sas_confiance_ia.ner import creer_moteur_ner

    moteur = creer_moteur_ner(moteur="spacy")
    texte = (CORPUS / "04-dossier-usager/piece-1-courrier.md").read_text(encoding="utf-8")
    entites = moteur.reconnaitre(texte)
    assert _couvert(entites, texte, "Jean Dupont", {"PERSONNE"})
    assert {e.type for e in entites} <= {"PERSONNE", "ORGANISATION", "LIEU"}
