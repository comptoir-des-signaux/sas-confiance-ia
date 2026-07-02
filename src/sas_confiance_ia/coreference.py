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


def _sans_civilite(mention: str) -> str:
    mots = mention.split()
    while mots and mots[0].lower().rstrip(".") in CIVILITES:
        mots = mots[1:]
    return " ".join(mots)


def _cle(mention: str) -> str:
    return _sans_civilite(mention).lower()


def _est_initiale(mot: str) -> bool:
    return len(mot.rstrip(".")) == 1


def _prenoms_compatibles(a: list[str], b: list[str]) -> bool:
    """Vrai si les prénoms ne contredisent pas l'hypothèse « même personne »."""
    if not a or not b:
        return True
    premier_a, premier_b = a[0].rstrip("."), b[0].rstrip(".")
    if _est_initiale(a[0]) or _est_initiale(b[0]):
        return premier_a[0] == premier_b[0]
    return premier_a == premier_b


def _completude(cle: str) -> tuple[int, int]:
    mots = cle.split()
    return (sum(1 for m in mots if not _est_initiale(m)), len(mots))


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
            return connues[mention]

        cle_mention = _cle(mention)
        if not cle_mention:
            return self._vault.placeholder_pour(dossier_id, TYPE_PERSONNE, mention)

        # 1. Même clé qu'une forme déjà connue (casse, civilité) : alias direct.
        for valeur, placeholder in connues.items():
            if _cle(valeur) == cle_mention:
                self._vault.associer_alias(dossier_id, TYPE_PERSONNE, mention, placeholder)
                return placeholder

        # 2. Règles sûres sur les formes canoniques : même nom de famille et
        #    prénoms compatibles.
        candidats = self._candidats(dossier_id, connues, cle_mention)
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

    def _candidats(
        self, dossier_id: str, connues: dict[str, str], cle_mention: str
    ) -> set[str]:
        mots_mention = cle_mention.split()
        nom_mention, prenoms_mention = mots_mention[-1], mots_mention[:-1]
        candidats = set()
        for placeholder in set(connues.values()):
            canonique = self._vault.valeur_pour(dossier_id, placeholder) or ""
            mots = _cle(canonique).split()
            if not mots or mots[-1] != nom_mention:
                continue
            if _prenoms_compatibles(prenoms_mention, mots[:-1]):
                candidats.add(placeholder)
        return candidats

    def _retenir_forme_la_plus_complete(
        self, dossier_id: str, placeholder: str, mention: str
    ) -> None:
        canonique = self._vault.valeur_pour(dossier_id, placeholder) or ""
        forme = _sans_civilite(mention)
        if _completude(_cle(mention)) > _completude(_cle(canonique)):
            self._vault.remplacer_valeur_canonique(
                dossier_id, TYPE_PERSONNE, placeholder, forme
            )
