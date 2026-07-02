"""Coréférence par dossier (couche C4, Lot 11, REQ-011).

Rattache les mentions d'une même personne (nom complet, nom seul,
civilité + nom, initiale + nom, variations de casse) au même placeholder,
y compris entre plusieurs pièces d'un dossier. La restitution est la forme
canonique : la plus complète connue (arbitrage Q1, docs/specs/QUESTIONS.md).

Fusion uniquement sur règles sûres (F4 du 02-AI-SPEC) : même nom de
famille ET prénoms compatibles. Toute ambiguïté (plusieurs personnes
possibles) crée une entité distincte et est signalée pour revue.
"""

from collections import defaultdict

from .vault import Vault

TYPE_PERSONNE = "PERSONNE"

# Civilités et titres neutralisés pour la comparaison (point final toléré).
CIVILITES = {
    "m",
    "mr",
    "mme",
    "mlle",
    "monsieur",
    "madame",
    "mademoiselle",
    "dr",
    "docteur",
    "me",
    "maitre",
    "maître",
    "pr",
    "professeur",
}


CIVILITES_MASCULINES = {"m", "mr", "monsieur"}
CIVILITES_FEMININES = {"mme", "madame", "mlle", "mademoiselle"}


def _sans_civilite(mention: str) -> str:
    mots = mention.split()
    while mots and mots[0].lower().rstrip(".") in CIVILITES:
        mots = mots[1:]
    return " ".join(mots)


def _genre_civilite(mention: str) -> str | None:
    mots = mention.split()
    premier = mots[0].lower().rstrip(".") if mots else ""
    if premier in CIVILITES_MASCULINES:
        return "m"
    if premier in CIVILITES_FEMININES:
        return "f"
    return None


def _cle(mention: str) -> str:
    return _sans_civilite(mention).lower()


def _est_initiale(mot: str) -> bool:
    return len(mot.rstrip(".")) == 1


def _est_forme_reduite(mention: str) -> bool:
    """Une forme sujette à homonymie : nom seul ou prénom réduit à l'initiale."""
    mots = _cle(mention).split()
    return len(mots) < 2 or any(_est_initiale(m) for m in mots)


def _prenoms_compatibles(a: list[str], b: list[str]) -> bool:
    """Vrai si les prénoms ne contredisent pas l'hypothèse « même personne ».

    Comparaison position par position (F4 : « Jean Paul » et « Jean Marc »
    sont contradictoires) ; une liste plus courte reste compatible.
    """
    for mot_a, mot_b in zip(a, b, strict=False):
        plein_a, plein_b = mot_a.rstrip("."), mot_b.rstrip(".")
        if _est_initiale(mot_a) or _est_initiale(mot_b):
            if plein_a[:1] != plein_b[:1]:
                return False
        elif plein_a != plein_b:
            return False
    return True


def _completude(cle: str) -> tuple[int, int]:
    mots = cle.split()
    return (sum(1 for m in mots if not _est_initiale(m)), len(mots))


def _qualite_casse(forme: str) -> int:
    return sum(1 for mot in forme.split() if mot[:1].isupper())


class ResolveurCoreference:
    """Attribution de placeholders PERSONNE avec rattachement des alias."""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._ambiguites: dict[str, set[str]] = defaultdict(set)

    def ambiguites(self, dossier_id: str) -> set[str]:
        """Placeholders créés faute de rattachement sûr (à passer en revue)."""
        return set(self._ambiguites[dossier_id])

    def placeholder_pour(self, dossier_id: str, mention: str) -> str:
        connues = self._vault.valeurs_pour_type(dossier_id, TYPE_PERSONNE)
        if mention in connues:
            placeholder = connues[mention]
            # Une liaison sur forme réduite reste stable (cohérence REQ-011)
            # mais repasse en revue si un homonyme est apparu depuis (F4).
            if _est_forme_reduite(mention):
                candidats = self._candidats(dossier_id, connues, mention)
                if len(candidats) > 1:
                    self._ambiguites[dossier_id].add(placeholder)
            return placeholder

        cle_mention = _cle(mention)
        if not cle_mention:
            return self._vault.placeholder_pour(dossier_id, TYPE_PERSONNE, mention)

        # 1. Même clé qu'une forme déjà connue (casse, civilité) : alias
        #    direct, sauf contradiction de genre (M. / Mme, F4).
        for valeur, placeholder in connues.items():
            if _cle(valeur) == cle_mention and self._genres_compatibles(
                dossier_id, connues, placeholder, mention
            ):
                self._vault.associer_alias(dossier_id, TYPE_PERSONNE, mention, placeholder)
                self._retenir_forme_la_plus_complete(dossier_id, placeholder, mention)
                return placeholder

        # 2. Règles sûres sur les formes canoniques : même nom de famille,
        #    prénoms compatibles, genre non contradictoire.
        candidats = self._candidats(dossier_id, connues, mention)
        if len(candidats) == 1:
            (placeholder,) = candidats
            self._vault.associer_alias(dossier_id, TYPE_PERSONNE, mention, placeholder)
            self._retenir_forme_la_plus_complete(dossier_id, placeholder, mention)
            return placeholder

        # 3. Aucune correspondance sûre : nouvelle entité ; ambiguïté signalée
        #    si plusieurs personnes étaient possibles (F4 : pas de fusion hasardeuse).
        placeholder = self._vault.placeholder_pour(dossier_id, TYPE_PERSONNE, mention)
        if len(candidats) > 1:
            self._ambiguites[dossier_id].add(placeholder)
        return placeholder

    def _genres_compatibles(
        self, dossier_id: str, connues: dict[str, str], placeholder: str, mention: str
    ) -> bool:
        genre_mention = _genre_civilite(mention)
        if genre_mention is None:
            return True
        genres_entite = {
            g
            for valeur, ph in connues.items()
            if ph == placeholder
            for g in (_genre_civilite(valeur),)
            if g is not None
        }
        return not genres_entite or genre_mention in genres_entite

    def _candidats(
        self, dossier_id: str, connues: dict[str, str], mention: str
    ) -> set[str]:
        mots_mention = _cle(mention).split()
        nom_mention, prenoms_mention = mots_mention[-1], mots_mention[:-1]
        candidats = set()
        for placeholder in set(connues.values()):
            canonique = self._vault.valeur_pour(dossier_id, placeholder) or ""
            mots = _cle(canonique).split()
            if not mots or mots[-1] != nom_mention:
                continue
            if not _prenoms_compatibles(prenoms_mention, mots[:-1]):
                continue
            if self._genres_compatibles(dossier_id, connues, placeholder, mention):
                candidats.add(placeholder)
        return candidats

    def _retenir_forme_la_plus_complete(
        self, dossier_id: str, placeholder: str, mention: str
    ) -> None:
        canonique = self._vault.valeur_pour(dossier_id, placeholder) or ""
        forme = _sans_civilite(mention)
        completude_mention = _completude(_cle(mention))
        completude_canonique = _completude(_cle(canonique))
        # À complétude égale, une forme mieux casée améliore la restitution
        # (« jean dupont » ne doit pas rester canonique face à « Jean Dupont »).
        meilleure = completude_mention > completude_canonique or (
            completude_mention == completude_canonique
            and _qualite_casse(forme) > _qualite_casse(canonique)
        )
        if meilleure:
            self._vault.remplacer_valeur_canonique(
                dossier_id, TYPE_PERSONNE, placeholder, forme
            )
