"""Lot 11 : coréférence par dossier (C4, REQ-011).

Arbitrage Q1 de docs/specs/QUESTIONS.md : les alias d'une même personne
partagent le même placeholder ; la ré-identification restitue la forme
canonique (la plus complète connue du dossier). Fusion uniquement sur
règles sûres ; homonymes ambigus → placeholders distincts + signalement
(F4 : jamais de fusion hasardeuse).
"""

from pathlib import Path

from sas_confiance_ia.coreference import ResolveurCoreference
from sas_confiance_ia.vault import VaultChiffre, VaultMemoire, generer_cle

CORPUS = Path(__file__).parent.parent / "corpus" / "synthetique"


def resolveur() -> tuple[ResolveurCoreference, VaultMemoire]:
    vault = VaultMemoire()
    return ResolveurCoreference(vault), vault


def test_nom_complet_puis_civilite_et_nom_meme_placeholder():
    # Acceptance REQ-011 : « Jean Dupont » puis « M. Dupont ».
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Jean Dupont")
    p2 = r.placeholder_pour("d1", "M. Dupont")
    assert p1 == p2 == "[PERSONNE_001]"


def test_initiale_et_nom_rattachee():
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Jean Dupont")
    p2 = r.placeholder_pour("d1", "J. Dupont")
    assert p1 == p2


def test_nom_seul_rattache_si_une_seule_personne_correspond():
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Jean Dupont")
    p2 = r.placeholder_pour("d1", "Dupont")
    assert p1 == p2


def test_la_casse_ne_cree_pas_une_autre_personne():
    r, _ = resolveur()
    assert r.placeholder_pour("d1", "Jean Dupont") == r.placeholder_pour("d1", "JEAN DUPONT")


def test_les_civilites_usuelles_sont_neutralisees():
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Madame Marie Martin")
    p2 = r.placeholder_pour("d1", "Mme Martin")
    p3 = r.placeholder_pour("d1", "Marie Martin")
    assert p1 == p2 == p3


def test_deux_prenoms_differents_ne_fusionnent_jamais():
    # Règle sûre (F4) : même nom de famille, prénoms différents = deux personnes.
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Jean Dupont")
    p2 = r.placeholder_pour("d1", "Marie Dupont")
    assert p1 != p2


def test_homonymes_ambigus_placeholder_distinct_et_signalement():
    # « M. Dupont » alors que Jean ET Marie Dupont sont connus : ambigu,
    # jamais fusionné, signalé pour revue.
    r, _ = resolveur()
    r.placeholder_pour("d1", "Jean Dupont")
    r.placeholder_pour("d1", "Marie Dupont")
    p3 = r.placeholder_pour("d1", "M. Dupont")
    assert p3 == "[PERSONNE_003]"
    assert p3 in r.ambiguites("d1")


def test_la_reidentification_restaure_la_forme_canonique():
    r, vault = resolveur()
    p = r.placeholder_pour("d1", "Jean Dupont")
    r.placeholder_pour("d1", "M. Dupont")
    assert vault.valeur_pour("d1", p) == "Jean Dupont"


def test_la_forme_la_plus_complete_devient_canonique():
    # « M. Dupont » vu d'abord, « Jean Dupont » ensuite : rattaché, et la
    # restitution s'améliore vers la forme complète (arbitrage Q1).
    r, vault = resolveur()
    p1 = r.placeholder_pour("d1", "M. Dupont")
    p2 = r.placeholder_pour("d1", "Jean Dupont")
    assert p1 == p2
    assert vault.valeur_pour("d1", p1) == "Jean Dupont"


def test_les_dossiers_sont_isoles():
    r, _ = resolveur()
    r.placeholder_pour("d1", "Jean Dupont")
    p = r.placeholder_pour("d2", "M. Dupont")
    # d2 ne connaît aucun Dupont : nouvelle entité, numérotation propre.
    assert p == "[PERSONNE_001]"


def test_une_mention_inconnue_reste_une_nouvelle_entite():
    r, _ = resolveur()
    r.placeholder_pour("d1", "Jean Dupont")
    assert r.placeholder_pour("d1", "Nadia Benali") == "[PERSONNE_002]"


def test_les_alias_survivent_au_redemarrage(tmp_path):
    # REQ-005 étendu au Lot 11 : les alias persistent avec le vault chiffré.
    chemin, cle = tmp_path / "vault.sas", generer_cle()
    r1 = ResolveurCoreference(VaultChiffre(chemin, cle))
    p_avant = r1.placeholder_pour("d1", "Jean Dupont")
    r1.placeholder_pour("d1", "M. Dupont")

    vault2 = VaultChiffre(chemin, cle)
    r2 = ResolveurCoreference(vault2)
    assert r2.placeholder_pour("d1", "M. Dupont") == p_avant
    assert vault2.valeur_pour("d1", p_avant) == "Jean Dupont"


def test_deuxiemes_prenoms_contradictoires_ne_fusionnent_pas():
    # F4 : « Jean Paul Dupont » et « Jean Marc Dupont » sont deux personnes.
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Jean Paul Dupont")
    p2 = r.placeholder_pour("d1", "Jean Marc Dupont")
    assert p1 != p2


def test_civilites_de_genres_contradictoires_ne_fusionnent_pas():
    # F4 : « M. Dupont » puis « Mme Dupont » : deux personnes, jamais fusionnées.
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "M. Dupont")
    p2 = r.placeholder_pour("d1", "Mme Dupont")
    assert p1 != p2


def test_le_genre_contradictoire_bloque_aussi_le_rattachement_au_nom_complet():
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "M. Jean Dupont")
    p2 = r.placeholder_pour("d1", "Mme Dupont")
    assert p1 != p2


def test_une_liaison_reduite_repasse_en_revue_quand_un_homonyme_apparait():
    # F4 : « M. Dupont » lié à Jean Dupont, puis Pierre Dupont arrive dans le
    # dossier. La liaison reste stable (cohérence REQ-011) mais tout nouvel
    # usage de la forme réduite est signalé pour revue.
    r, _ = resolveur()
    p1 = r.placeholder_pour("d1", "Jean Dupont")
    assert r.placeholder_pour("d1", "M. Dupont") == p1
    assert r.ambiguites("d1") == set()
    r.placeholder_pour("d1", "Pierre Dupont")
    assert r.placeholder_pour("d1", "M. Dupont") == p1
    assert p1 in r.ambiguites("d1")


def test_a_completude_egale_la_forme_bien_casee_devient_canonique():
    r, vault = resolveur()
    p = r.placeholder_pour("d1", "jean dupont")
    r.placeholder_pour("d1", "Jean Dupont")
    assert vault.valeur_pour("d1", p) == "Jean Dupont"


def test_une_forme_moins_bien_casee_ne_degrade_pas_la_canonique():
    r, vault = resolveur()
    p = r.placeholder_pour("d1", "Jean Dupont")
    r.placeholder_pour("d1", "JEAN DUPONT")
    assert vault.valeur_pour("d1", p) == "Jean Dupont"


def test_le_vault_expose_les_valeurs_par_type():
    vault = VaultMemoire()
    vault.placeholder_pour("d1", "PERSONNE", "Jean Dupont")
    vault.placeholder_pour("d1", "EMAIL", "jean.dupont@exemple.fr")
    valeurs = vault.valeurs_pour_type("d1", "PERSONNE")
    assert valeurs == {"Jean Dupont": "[PERSONNE_001]"}
