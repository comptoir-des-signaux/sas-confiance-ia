"""Couche C2 : NER français via Presidio in-process (ADR-009, Lot 9).

Le modèle transformers est épinglé par révision exacte (parade F9 du
02-AI-SPEC : pas de dérive silencieuse) et chargé exclusivement depuis le
cache local : le téléchargement se fait à l'installation
(python -m sas_confiance_ia.telechargement), jamais au premier appel.

Repli spaCy configurable (fr_core_news_lg) pour machine modeste, derrière
la même interface Moteur. Les dépendances lourdes restent optionnelles :
ce module s'importe sans elles, seules les fabriques les exigent.
"""

from .detection import EntiteDetectee

# Modèle NER français de référence (MIT, compatible EUPL-1.2).
MODELE_TRANSFORMERS = "Jean-Baptiste/camembert-ner"
REVISION_TRANSFORMERS = "ef35fe7767c1dad71f5c853838cdd80d0b3441ed"
# spaCy sert de tokeniseur à Presidio autour du modèle transformers.
MODELE_SPACY_TOKENISATION = "fr_core_news_sm"
# Repli NER complet sans transformers (extra [ner-repli-spacy]).
MODELE_SPACY_REPLI = "fr_core_news_lg"

SEUIL_SCORE_DEFAUT = 0.5

# Types Presidio -> types du sas (étiquettes du vault, priorité REQ-016).
CORRESPONDANCE_PRESIDIO = {
    "PERSON": "PERSONNE",
    "ORGANIZATION": "ORGANISATION",
    "LOCATION": "LIEU",
}


def chemin_modele_transformers(telechargement_autorise: bool = False) -> str:
    """Chemin local du modèle épinglé ; sans téléchargement par défaut."""
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=MODELE_TRANSFORMERS,
        revision=REVISION_TRANSFORMERS,
        local_files_only=not telechargement_autorise,
    )


def modele_transformers_present() -> bool:
    try:
        chemin_modele_transformers()
        return True
    except Exception:
        return False


class MoteurNER:
    """Adapte l'AnalyzerEngine de Presidio au protocole Moteur du sas."""

    def __init__(self, analyseur, seuil: float = SEUIL_SCORE_DEFAUT) -> None:
        self._analyseur = analyseur
        self._seuil = seuil

    def reconnaitre(self, texte: str) -> list[EntiteDetectee]:
        resultats = self._analyseur.analyze(
            text=texte,
            language="fr",
            entities=list(CORRESPONDANCE_PRESIDIO),
            score_threshold=self._seuil,
        )
        entites = []
        for r in resultats:
            valeur = texte[r.start : r.end]
            # Les modes d'alignement peuvent inclure des blancs de bordure :
            # on resserre l'empan sur la valeur utile.
            depouille = valeur.strip()
            if not depouille:
                continue
            debut = r.start + valeur.index(depouille)
            entites.append(
                EntiteDetectee(
                    type=CORRESPONDANCE_PRESIDIO[r.entity_type],
                    debut=debut,
                    fin=debut + len(depouille),
                    score=r.score,
                    valeur=depouille,
                )
            )
        return entites


def _configuration_ner(correspondance: dict[str, str]):
    from presidio_analyzer.nlp_engine import NerModelConfiguration

    return NerModelConfiguration(
        model_to_presidio_entity_mapping=correspondance,
        labels_to_ignore=["O", "MISC"],
        aggregation_strategy="simple",
        alignment_mode="expand",
        default_score=SEUIL_SCORE_DEFAUT,
    )


def creer_moteur_ner(moteur: str = "transformers", seuil: float = SEUIL_SCORE_DEFAUT) -> MoteurNER:
    """Fabrique le moteur NER : « transformers » (défaut) ou « spacy » (repli).

    Le registre Presidio est réduit au seul reconnaisseur NER : les types
    déterministes français (NIR, SIRET, IBAN...) restent portés par la
    couche C1 du sas (detection.py), pas par les reconnaisseurs Presidio.
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.predefined_recognizers import SpacyRecognizer, TransformersRecognizer

    # Étiquettes des modèles (camembert-ner et spaCy fr) -> types Presidio.
    correspondance = {"PER": "PERSON", "ORG": "ORGANIZATION", "LOC": "LOCATION"}

    if moteur == "transformers":
        from presidio_analyzer.nlp_engine import TransformersNlpEngine

        nlp_engine = TransformersNlpEngine(
            models=[
                {
                    "lang_code": "fr",
                    "model_name": {
                        "spacy": MODELE_SPACY_TOKENISATION,
                        # Chemin local du modèle épinglé : jamais de
                        # téléchargement au chargement (HANDOFF, règle 1).
                        "transformers": chemin_modele_transformers(),
                    },
                }
            ],
            ner_model_configuration=_configuration_ner(correspondance),
        )
        reconnaisseur = TransformersRecognizer(
            supported_language="fr", supported_entities=list(CORRESPONDANCE_PRESIDIO)
        )
    elif moteur == "spacy":
        from presidio_analyzer.nlp_engine import SpacyNlpEngine

        nlp_engine = SpacyNlpEngine(
            models=[{"lang_code": "fr", "model_name": MODELE_SPACY_REPLI}],
            ner_model_configuration=_configuration_ner(correspondance),
        )
        reconnaisseur = SpacyRecognizer(
            supported_language="fr", supported_entities=list(CORRESPONDANCE_PRESIDIO)
        )
    else:
        raise ValueError(f"Moteur NER inconnu : {moteur!r} (attendu : transformers ou spacy)")

    registre = RecognizerRegistry(supported_languages=["fr"])
    registre.add_recognizer(reconnaisseur)
    analyseur = AnalyzerEngine(
        nlp_engine=nlp_engine, registry=registre, supported_languages=["fr"]
    )
    return MoteurNER(analyseur, seuil=seuil)
