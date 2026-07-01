"""Lots 3 et 9 : détection déterministe (C1) et entrée des candidats NER (C2).

Exigence de vert du Lot 3 : rappel 1,0 sur les types déterministes du corpus,
et résolution des chevauchements selon la priorité du 03-SPEC (REQ-016).
Le Lot 9 ajoute l'interface `moteurs` : toute couche supplémentaire (NER,
juge) fournit des candidats qui passent par la même résolution, sans jamais
dégrader ce qu'une couche plus fiable a établi (02-AI-SPEC §1).
"""

from pathlib import Path

from sas_confiance_ia.detection import EntiteDetectee, detecter

CORPUS = Path(__file__).parent.parent / "corpus" / "synthetique"

# Vérité terrain déterministe : (document, valeur exacte, type attendu).
ATTENDUS = [
    ("01-courrier-usager.md", "marie.martin@exemple.fr", "EMAIL"),
    ("01-courrier-usager.md", "06 12 34 56 78", "TELEPHONE"),
    ("01-courrier-usager.md", "2 92 07 82 045 033 55", "FR_NIR"),
    ("01-courrier-usager.md", "ALL-2026-0457", "REFERENCE_DOSSIER"),
    ("01-courrier-usager.md", "14 juillet 1992", "DATE_NAISSANCE"),
    ("02-note-rh.md", "RH-4521", "REFERENCE_DOSSIER"),
    ("02-note-rh.md", "3 mars 1988", "DATE_NAISSANCE"),
    ("03-contrat-prestation.md", "824 750 004", "FR_SIREN"),
    ("03-contrat-prestation.md", "824 750 004 00007", "FR_SIRET"),
    ("03-contrat-prestation.md", "FR11 3000 3000 1100 0987 6543 185", "IBAN"),
    ("03-contrat-prestation.md", "07 65 43 21 09", "TELEPHONE"),
    ("03-contrat-prestation.md", "contact@nettoyage-occitan.exemple.fr", "EMAIL"),
    ("04-dossier-usager/piece-1-courrier.md", "jean.dupont@exemple.fr", "EMAIL"),
    ("04-dossier-usager/piece-1-courrier.md", "07 89 01 23 45", "TELEPHONE"),
    ("04-dossier-usager/piece-1-courrier.md", "1 80 03 74 118 218 22", "FR_NIR"),
    ("04-dossier-usager/piece-1-courrier.md", "12 mars 1980", "DATE_NAISSANCE"),
    ("05-compte-rendu-reunion.md", "2 février 1962", "DATE_NAISSANCE"),
]


def test_rappel_total_sur_les_types_deterministes_du_corpus():
    manques = []
    for doc, valeur, type_attendu in ATTENDUS:
        texte = (CORPUS / doc).read_text(encoding="utf-8")
        entites = detecter(texte)
        if not any(e.valeur == valeur and e.type == type_attendu for e in entites):
            manques.append((doc, valeur, type_attendu))
    assert not manques, f"non détectés : {manques}"


def test_le_siret_l_emporte_sur_la_carte_bancaire():
    # Un SIRET (14 chiffres Luhn-valides) ressemble à une carte bancaire :
    # la priorité REQ-016 doit trancher en faveur de FR_SIRET.
    entites = detecter("Le prestataire porte le numéro 82475000400007 au registre.")
    types = {e.type for e in entites if e.valeur == "82475000400007"}
    assert types == {"FR_SIRET"}


def test_le_siren_contenu_dans_un_siret_n_est_pas_double_compte():
    entites = detecter("SIRET : 824 750 004 00007.")
    assert [e.type for e in entites] == ["FR_SIRET"]


def test_un_nir_a_cle_fausse_n_est_pas_detecte():
    entites = detecter("Numéro de sécurité sociale 1 80 03 74 118 218 23.")
    assert not [e for e in entites if e.type == "FR_NIR"]


def test_un_iban_a_cle_fausse_n_est_pas_detecte():
    entites = detecter("IBAN : FR12 3000 3000 1100 0987 6543 185.")
    assert not [e for e in entites if e.type == "IBAN"]


def test_une_date_hors_contexte_naissance_n_est_pas_une_date_de_naissance():
    entites = detecter("La commission se réunit le 8 juillet 2026 en mairie.")
    assert not [e for e in entites if e.type == "DATE_NAISSANCE"]


def test_plaque_d_immatriculation():
    entites = detecter("Le véhicule immatriculé AB-123-CD a été verbalisé.")
    assert any(e.type == "PLAQUE" and e.valeur == "AB-123-CD" for e in entites)


def test_les_positions_correspondent_au_texte():
    texte = "Écrire à marie.martin@exemple.fr avant vendredi."
    (entite,) = detecter(texte)
    assert texte[entite.debut : entite.fin] == entite.valeur


class MoteurFactice:
    """Simule une couche probabiliste (C2 ou C3) : renvoie des candidats fixes."""

    def __init__(self, entites: list[EntiteDetectee]) -> None:
        self._entites = entites

    def reconnaitre(self, texte: str) -> list[EntiteDetectee]:
        return [e for e in self._entites if texte[e.debut : e.fin] == e.valeur]


def _entite(type_: str, texte: str, valeur: str, score: float = 0.8) -> EntiteDetectee:
    debut = texte.index(valeur)
    return EntiteDetectee(
        type=type_, debut=debut, fin=debut + len(valeur), score=score, valeur=valeur
    )


def test_un_moteur_additionnel_ajoute_ses_candidats():
    texte = "Marie Martin est venue en mairie ce matin."
    moteur = MoteurFactice([_entite("PERSONNE", texte, "Marie Martin")])
    entites = detecter(texte, moteurs=[moteur])
    assert any(e.type == "PERSONNE" and e.valeur == "Marie Martin" for e in entites)


def test_sans_moteur_le_comportement_c1_est_inchange():
    texte = "Marie Martin est venue en mairie ce matin."
    assert detecter(texte) == []


def test_un_type_deterministe_gagne_sur_un_candidat_ner():
    # REQ-016 : EMAIL (C1, validé) prime sur PERSONNE (C2, probabiliste),
    # même si le NER propose un empan qui recouvre l'adresse.
    texte = "Écrire à marie.martin@exemple.fr rapidement."
    moteur = MoteurFactice([_entite("PERSONNE", texte, "marie.martin@exemple.fr", score=0.99)])
    entites = detecter(texte, moteurs=[moteur])
    assert [e.type for e in entites] == ["EMAIL"]


def test_personne_gagne_sur_organisation_et_lieu():
    # Ordre REQ-016 : PERSON > ORGANIZATION > LOCATION sur l'empan contesté ;
    # le débord de l'entité moins prioritaire est rogné, pas abandonné.
    texte = "Le cabinet Martin conseille la commune."
    moteur = MoteurFactice(
        [
            _entite("ORGANISATION", texte, "cabinet Martin"),
            _entite("PERSONNE", texte, "Martin", score=0.7),
            _entite("LIEU", texte, "cabinet Martin", score=0.9),
        ]
    )
    entites = detecter(texte, moteurs=[moteur])
    (sur_martin,) = [e for e in entites if e.debut <= texte.index("Martin") < e.fin]
    assert sur_martin.type == "PERSONNE"
    assert all(e.type in {"PERSONNE", "ORGANISATION"} for e in entites)


def test_un_chevauchement_partiel_est_rogne_pas_rejete():
    # REQ-001 : si un empan NER large chevauche une entité déterministe
    # retenue, son résidu ne doit JAMAIS rester en clair : l'empan est
    # rogné à la partie non couverte, pas écarté en bloc.
    texte = "Contacter Marie Martin, marie.martin@exemple.fr au plus vite."
    moteur = MoteurFactice(
        [_entite("PERSONNE", texte, "Marie Martin, marie.martin@exemple.fr", score=0.9)]
    )
    entites = detecter(texte, moteurs=[moteur])
    assert any(e.type == "EMAIL" and e.valeur == "marie.martin@exemple.fr" for e in entites)
    debut_nom, fin_nom = texte.index("Marie Martin"), texte.index("Marie Martin") + 12
    assert any(
        e.type == "PERSONNE" and e.debut <= debut_nom and e.fin >= fin_nom for e in entites
    ), f"le résidu « Marie Martin » reste en clair : {entites}"


def test_un_chevauchement_total_reste_ecarte():
    # Le rognage ne réintroduit pas de doublon : un candidat entièrement
    # couvert (SIREN dans SIRET) disparaît sans résidu.
    entites = detecter("SIRET : 824 750 004 00007.")
    assert [e.type for e in entites] == ["FR_SIRET"]


def test_les_positions_d_un_residu_correspondent_au_texte():
    texte = "Voir Marie Martin, marie.martin@exemple.fr, pour suite."
    moteur = MoteurFactice(
        [_entite("PERSONNE", texte, "Marie Martin, marie.martin@exemple.fr", score=0.9)]
    )
    for entite in detecter(texte, moteurs=[moteur]):
        assert texte[entite.debut : entite.fin] == entite.valeur


def test_deux_moteurs_cumulent_leurs_candidats():
    texte = "Marie Martin travaille chez Nettoyage Occitan."
    ner = MoteurFactice([_entite("PERSONNE", texte, "Marie Martin")])
    juge = MoteurFactice([_entite("ORGANISATION", texte, "Nettoyage Occitan")])
    entites = detecter(texte, moteurs=[ner, juge])
    assert {e.type for e in entites} == {"PERSONNE", "ORGANISATION"}
