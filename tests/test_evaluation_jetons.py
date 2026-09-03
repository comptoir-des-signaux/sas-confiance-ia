"""Mesure du surcoût en jetons de la pseudonymisation (02-AI-SPEC §4.2).

Question posée publiquement : pseudonymiser gonfle-t-il la facture de jetons
envoyée au backend ? La mesure est publiée dans
`docs/eval/evaluation-jetons.md`, cette suite couvre le calcul.

Le compteur de jetons est INJECTÉ : l'encodage réel (tiktoken) se télécharge
au premier usage, et aucun test n'a le droit de toucher le réseau
(AGENTS.md, interdiction 1). Les tests comptent donc les mots.
"""

from sas_confiance_ia.evaluation_jetons import (
    MesureJetons,
    cout_consigne,
    mesurer_documents,
    totaliser,
)


def compter_mots(texte: str) -> int:
    """Compteur de substitution, déterministe et hors ligne."""
    return len(texte.split())


class PseudonymiseurFactice:
    """Remplace chaque valeur connue par son placeholder, sans détection."""

    def __init__(self, correspondances: dict[str, str]):
        self._correspondances = correspondances

    def pseudonymiser(self, texte: str, dossier_id: str):
        comptes: dict[str, int] = {}
        for valeur, placeholder in self._correspondances.items():
            if valeur in texte:
                texte = texte.replace(valeur, placeholder)
                type_ = placeholder.strip("[]").rsplit("_", 1)[0]
                comptes[type_] = comptes.get(type_, 0) + 1
        return type("R", (), {"texte": texte, "comptes_par_type": comptes})()


def test_la_mesure_compare_le_clair_et_le_pseudonymise_document_par_document():
    pseudonymiseur = PseudonymiseurFactice({"Karim Benhaddou": "[PERSONNE_001]"})
    mesures = mesurer_documents(
        {"note.md": "Le dossier de Karim Benhaddou avance"},
        pseudonymiseur=pseudonymiseur,
        compter=compter_mots,
    )
    assert mesures == [
        MesureJetons(
            document="note.md",
            entites=1,
            jetons_clair=6,
            jetons_pseudonymise=5,
        )
    ]
    # Un nom en deux mots devient un jeton unique : l'écart est négatif.
    assert mesures[0].ecart == -1


def test_un_document_sans_entite_ne_change_pas_le_compte():
    pseudonymiseur = PseudonymiseurFactice({"Karim Benhaddou": "[PERSONNE_001]"})
    (mesure,) = mesurer_documents(
        {"vide.md": "Aucune valeur sensible ici"},
        pseudonymiseur=pseudonymiseur,
        compter=compter_mots,
    )
    assert mesure.entites == 0
    assert mesure.ecart == 0


def test_chaque_document_est_pseudonymise_dans_son_propre_dossier():
    # Sans cette isolation, les compteurs de placeholders se poursuivraient
    # d'un document à l'autre et la mesure ne serait pas reproductible.
    dossiers = []

    class Espion(PseudonymiseurFactice):
        def pseudonymiser(self, texte, dossier_id):
            dossiers.append(dossier_id)
            return super().pseudonymiser(texte, dossier_id)

    mesurer_documents(
        {"a.md": "texte a", "b.md": "texte b"},
        pseudonymiseur=Espion({}),
        compter=compter_mots,
    )
    assert len(set(dossiers)) == 2


def test_le_total_agrege_les_documents_et_ajoute_la_consigne():
    mesures = [
        MesureJetons(document="a.md", entites=2, jetons_clair=100, jetons_pseudonymise=90),
        MesureJetons(document="b.md", entites=3, jetons_clair=100, jetons_pseudonymise=110),
    ]
    total = totaliser(mesures, jetons_consigne=20)

    assert total.documents == 2
    assert total.entites == 5
    assert total.jetons_clair == 200
    assert total.jetons_pseudonymise == 200
    assert total.jetons_consigne == 20
    # Le texte seul ne coûte rien de plus ; la consigne, elle, se paie.
    assert total.taux_texte == 0.0
    assert total.taux_avec_consigne == 10.0


def test_la_consigne_systeme_est_celle_reellement_injectee_par_le_proxy():
    # La mesure doit suivre le proxy : pas de copie du texte de la consigne.
    from sas_confiance_ia.api import CONSIGNE_PRESERVATION_JETONS

    assert cout_consigne(compter_mots) == compter_mots(CONSIGNE_PRESERVATION_JETONS)
