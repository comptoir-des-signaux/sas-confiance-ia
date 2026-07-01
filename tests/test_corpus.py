"""Lot 2 : cohérence du corpus synthétique et de son oracle (REQ-009).

L'oracle `valeurs-connues.json` alimente les tests de non-fuite (REQ-001,
REQ-003) : il doit rester exactement aligné sur les documents sources.
"""

import json
from pathlib import Path

CORPUS = Path(__file__).parent.parent / "corpus" / "synthetique"


def charger_oracle() -> dict[str, list[str]]:
    brut = json.loads((CORPUS / "valeurs-connues.json").read_text(encoding="utf-8"))
    return {doc: valeurs for doc, valeurs in brut.items() if not doc.startswith("_")}


def test_le_corpus_existe():
    assert CORPUS.is_dir()
    assert (CORPUS / "valeurs-connues.json").is_file()


def test_chaque_valeur_de_l_oracle_est_presente_verbatim():
    for doc, valeurs in charger_oracle().items():
        texte = (CORPUS / doc).read_text(encoding="utf-8")
        for valeur in valeurs:
            assert valeur in texte, f"{valeur!r} absent de {doc}"


def test_chaque_document_du_corpus_est_couvert_par_l_oracle():
    documents = {
        str(p.relative_to(CORPUS)).replace("\\", "/")
        for p in CORPUS.rglob("*.md")
        if p.name != "README.md"
    }
    assert documents == set(charger_oracle().keys())


def test_l_oracle_ne_contient_pas_de_doublon():
    for doc, valeurs in charger_oracle().items():
        assert len(valeurs) == len(set(valeurs)), f"doublon dans {doc}"
