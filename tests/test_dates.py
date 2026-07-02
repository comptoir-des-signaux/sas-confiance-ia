"""Lot 14 : politique de dates différenciée (REQ-008).

La date de naissance est masquée par défaut ; les dates procédurales
(décision, séance, accident) sont conservées par défaut et suivent la
politique du dossier (conserver, revue ou pseudonymiser). Le type
DATE_PROCEDURALE est le moins prioritaire de tous : une date happée par une
interprétation plus sensible (naissance, personne, adresse) reste masquée.
"""

from sas_confiance_ia.detection import detecter
from sas_confiance_ia.politique import Politique
from sas_confiance_ia.pseudonymiseur import Pseudonymiseur
from sas_confiance_ia.vault import VaultMemoire

# Corpus d'acceptance REQ-008 : une date de naissance et une date de décision.
TEXTE = (
    "Monsieur Karim Benhaddou, né le 14 mars 1979 à Valence, conteste la "
    "décision du 12/02/2026 notifiée par la commission du 1er juillet 2025."
)


def types_detectes(texte: str) -> dict[str, str]:
    return {e.valeur: e.type for e in detecter(texte)}


# --- Détection ---------------------------------------------------------------


def test_les_dates_procedurales_sont_detectees_textuelles_et_numeriques():
    types = types_detectes(TEXTE)
    assert types["12/02/2026"] == "DATE_PROCEDURALE"
    assert types["1er juillet 2025"] == "DATE_PROCEDURALE"


def test_la_date_de_naissance_prime_sur_la_date_procedurale():
    assert types_detectes(TEXTE)["14 mars 1979"] == "DATE_NAISSANCE"


def test_la_date_de_naissance_numerique_est_reconnue():
    types = types_detectes("Agent née le 28/09/1986 à Montélimar.")
    assert types["28/09/1986"] == "DATE_NAISSANCE"


def test_la_date_de_naissance_est_reconnue_par_le_libelle():
    # Formulaires administratifs : le libellé porte le contexte, pas « né le ».
    types = types_detectes("Date de naissance : 3 juillet 1967\nLieu : Valence")
    assert types["3 juillet 1967"] == "DATE_NAISSANCE"


def test_le_libelle_naissance_ne_deteint_pas_sur_les_sections_suivantes():
    # Une ligne vide coupe le contexte (même règle que les types suspects Q4).
    types = types_detectes("Date de naissance : 3 juillet 1967\n\nAudience du 12/02/2026.")
    assert types["12/02/2026"] == "DATE_PROCEDURALE"


def test_une_date_happee_par_une_entite_plus_sensible_reste_a_l_entite():
    # DATE_PROCEDURALE est le type le moins prioritaire : un empan NER qui
    # recouvre la date la garde (elle sera masquée avec lui).
    from sas_confiance_ia.detection import EntiteDetectee

    class MoteurEnglobant:
        def reconnaitre(self, texte: str):
            valeur = "séance du 11 juin 2026"
            debut = texte.find(valeur)
            return [
                EntiteDetectee(
                    type="ORGANISATION",
                    debut=debut,
                    fin=debut + len(valeur),
                    score=0.9,
                    valeur=valeur,
                )
            ]

    entites = detecter("PV de la séance du 11 juin 2026.", moteurs=[MoteurEnglobant()])
    assert [e.type for e in entites] == ["ORGANISATION"]


# --- Acceptance REQ-008 ------------------------------------------------------


def test_par_defaut_naissance_masquee_dates_procedurales_conservees():
    pseudo = Pseudonymiseur(VaultMemoire())
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert "14 mars 1979" not in resultat.texte
    assert "[DATE_NAISSANCE_001]" in resultat.texte
    assert "12/02/2026" in resultat.texte
    assert "1er juillet 2025" in resultat.texte
    # Conservées mais comptées : le journal documente ce qui a été vu.
    assert resultat.comptes_par_type["DATE_PROCEDURALE"] == 2
    assert pseudo.reidentifier(resultat.texte, dossier_id="d1") == TEXTE


def test_la_politique_du_dossier_passe_les_dates_procedurales_en_revue():
    vault = VaultMemoire()
    vault.definir_politique("d1", {"actions": {"DATE_PROCEDURALE": "revue"}})
    pseudo = Pseudonymiseur(vault)
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert "12/02/2026" not in resultat.texte
    assert "[DATE_PROCEDURALE_001]" in resultat.texte
    assert "[DATE_PROCEDURALE_001]" in resultat.en_revue
    assert pseudo.reidentifier(resultat.texte, dossier_id="d1") == TEXTE


def test_la_politique_peut_pseudonymiser_toutes_les_dates():
    pseudo = Pseudonymiseur(
        VaultMemoire(), politique=Politique(actions={"DATE_PROCEDURALE": "pseudonymiser"})
    )
    resultat = pseudo.pseudonymiser(TEXTE, dossier_id="d1")
    assert "12/02/2026" not in resultat.texte
    assert resultat.en_revue == []
    assert pseudo.reidentifier(resultat.texte, dossier_id="d1") == TEXTE
