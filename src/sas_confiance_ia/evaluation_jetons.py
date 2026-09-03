"""Surcoût en jetons de la pseudonymisation, mesuré sur le corpus synthétique.

Question posée publiquement : remplacer les valeurs sensibles par des jetons
gonfle-t-il la facture envoyée au backend ? Deux effets s'opposent. Un
identifiant en clair coûte cher à encoder (un NIR est une suite de chiffres
espacés) là où son placeholder est compact ; à l'inverse, le proxy ajoute une
consigne système à chaque requête portant des jetons (voir `api.py`).

Le compteur est un paramètre, jamais une dépendance cachée : le résultat
dépend du tokenizer du backend visé, et publier un chiffre sans dire lequel
n'aurait aucun sens. La ligne de commande câble tiktoken (extra `[jetons]`),
dont l'encodage se télécharge au premier usage : c'est pourquoi ce module ne
compte rien par lui-même et reste hors de la suite de tests.

Usage : python -m sas_confiance_ia.evaluation_jetons [--encodage cl100k_base]
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .api import CONSIGNE_PRESERVATION_JETONS

CORPUS_PAR_DEFAUT = Path("corpus/synthetique")


class PseudonymiseurLike(Protocol):
    def pseudonymiser(self, texte: str, dossier_id: str): ...


@dataclass(frozen=True)
class MesureJetons:
    """Coût d'un document, en clair puis pseudonymisé."""

    document: str
    entites: int
    jetons_clair: int
    jetons_pseudonymise: int

    @property
    def ecart(self) -> int:
        return self.jetons_pseudonymise - self.jetons_clair


@dataclass(frozen=True)
class TotalJetons:
    """Agrégat du corpus, consigne système comprise."""

    documents: int
    entites: int
    jetons_clair: int
    jetons_pseudonymise: int
    jetons_consigne: int

    @property
    def taux_texte(self) -> float:
        """Écart du texte seul, en pourcentage du clair."""
        if not self.jetons_clair:
            return 0.0
        return 100 * (self.jetons_pseudonymise - self.jetons_clair) / self.jetons_clair

    @property
    def taux_avec_consigne(self) -> float:
        """Écart réellement facturé : texte plus consigne, à chaque requête."""
        if not self.jetons_clair:
            return 0.0
        ecart = self.jetons_pseudonymise + self.jetons_consigne - self.jetons_clair
        return 100 * ecart / self.jetons_clair


def cout_consigne(compter: Callable[[str], int]) -> int:
    """Coût de la consigne injectée par le proxy, lue chez lui et pas recopiée."""
    return compter(CONSIGNE_PRESERVATION_JETONS)


def mesurer_documents(
    documents: Mapping[str, str],
    pseudonymiseur: PseudonymiseurLike,
    compter: Callable[[str], int],
) -> list[MesureJetons]:
    """Mesure chaque document dans un dossier distinct.

    L'isolation par dossier est nécessaire à la reproductibilité : des
    compteurs partagés feraient dépendre la numérotation des placeholders,
    donc leur coût, de l'ordre de lecture des fichiers.
    """
    mesures = []
    for nom, texte in documents.items():
        resultat = pseudonymiseur.pseudonymiser(texte, f"mesure-jetons-{nom}")
        mesures.append(
            MesureJetons(
                document=nom,
                entites=sum(resultat.comptes_par_type.values()),
                jetons_clair=compter(texte),
                jetons_pseudonymise=compter(resultat.texte),
            )
        )
    return mesures


def totaliser(mesures: Iterable[MesureJetons], jetons_consigne: int) -> TotalJetons:
    mesures = list(mesures)
    return TotalJetons(
        documents=len(mesures),
        entites=sum(m.entites for m in mesures),
        jetons_clair=sum(m.jetons_clair for m in mesures),
        jetons_pseudonymise=sum(m.jetons_pseudonymise for m in mesures),
        jetons_consigne=jetons_consigne,
    )


def charger_corpus(dossier: Path | str = CORPUS_PAR_DEFAUT) -> dict[str, str]:
    """Tous les documents du corpus synthétique, README exclu."""
    dossier = Path(dossier)
    fichiers = sorted(c for c in dossier.rglob("*.md") if c.name != "README.md")
    return {str(c.relative_to(dossier)): c.read_text(encoding="utf-8") for c in fichiers}


def _tableau_markdown(mesures: Iterable[MesureJetons]) -> str:
    lignes = [
        "| Document | Entités | Jetons en clair | Jetons pseudonymisé | Écart |",
        "|---|---|---|---|---|",
    ]
    for m in mesures:
        lignes.append(
            f"| `{m.document}` | {m.entites} | {m.jetons_clair} "
            f"| {m.jetons_pseudonymise} | {m.ecart:+d} |"
        )
    return "\n".join(lignes)


def _principal() -> None:
    import argparse

    import tiktoken

    from .ner import creer_moteur_ner
    from .pseudonymiseur import Pseudonymiseur
    from .vault import VaultMemoire

    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--corpus", default=CORPUS_PAR_DEFAUT, type=Path)
    parseur.add_argument("--moteur", default="transformers", choices=["transformers", "spacy"])
    parseur.add_argument(
        "--encodage",
        default="cl100k_base",
        help="encodage tiktoken ; un backend Mistral ou Llama découpe autrement",
    )
    options = parseur.parse_args()

    encodeur = tiktoken.get_encoding(options.encodage)

    def compter(texte: str) -> int:
        return len(encodeur.encode(texte))

    pseudonymiseur = Pseudonymiseur(
        vault=VaultMemoire(), moteurs=[creer_moteur_ner(moteur=options.moteur)]
    )
    documents = charger_corpus(options.corpus)
    mesures = mesurer_documents(documents, pseudonymiseur=pseudonymiseur, compter=compter)
    total = totaliser(mesures, jetons_consigne=cout_consigne(compter))

    print(f"Encodage : {options.encodage} (tiktoken)")
    print(_tableau_markdown(mesures))
    print(
        f"\nTotal : {total.documents} documents, {total.entites} entités, "
        f"{total.jetons_clair} jetons en clair contre {total.jetons_pseudonymise} "
        f"pseudonymisés ({total.taux_texte:+.1f} %)."
    )
    print(
        f"Consigne système : {total.jetons_consigne} jetons à chaque requête, "
        f"soit {total.taux_avec_consigne:+.1f} % sur ce corpus."
    )


if __name__ == "__main__":
    _principal()
