"""Configuration d'exécution par variables d'environnement (Lot 10, REQ-013).

Rien en dur : changer de backend (Ollama local, Infomaniak, Scaleway, tout
endpoint OpenAI-compatible) ne demande qu'un changement de configuration.

| Variable | Rôle | Défaut |
|---|---|---|
| SAS_BACKEND_BASE_URL | base URL OpenAI-compatible (requis) | aucun |
| SAS_BACKEND_CLE_API | clé API Bearer (optionnelle, via secret) | aucune |
| SAS_BACKEND_TIMEOUT_SECONDES | timeout d'appel backend | 120 |
| SAS_MODELES | modèles exposés par /v1/models, séparés par des virgules (requis) | aucun |
| SAS_NER | auto, transformers, spacy ou inactif | auto |
| SAS_VAULT_CHEMIN | fichier vault chiffré persistant | aucun (vault mémoire) |
| SAS_VAULT_CLE | clé Fernet du vault (via secret, jamais committée) | aucune |

Défauts protecteurs : sans chemin ET clé, le vault reste en mémoire (rien
n'est écrit sur disque) ; « auto » active le NER si le modèle épinglé est
présent, sinon la détection reste déterministe (couverture moindre,
journalisée au démarrage).
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from .api import creer_application
from .backends import DELAI_DEFAUT_SECONDES, BackendOpenAICompatible
from .pseudonymiseur import Pseudonymiseur
from .vault import Vault, VaultChiffre, VaultMemoire

MODES_NER = ("auto", "transformers", "spacy", "inactif")

_journal = logging.getLogger("sas_confiance_ia.configuration")


class ConfigurationInvalide(ValueError):
    """Variable d'environnement manquante ou invalide."""


@dataclass(frozen=True)
class Configuration:
    backend_base_url: str
    backend_cle_api: str | None
    backend_timeout: float
    modeles: list[str]
    ner: str
    vault_chemin: str | None
    vault_cle: str | None

    def creer_vault(self) -> Vault:
        if self.vault_chemin is not None and self.vault_cle is not None:
            return VaultChiffre(self.vault_chemin, self.vault_cle.encode())
        return VaultMemoire()

    def creer_moteurs(self) -> list:
        """Moteurs de détection additionnels selon SAS_NER."""
        if self.ner == "inactif":
            return []
        try:
            from .ner import creer_moteur_ner, modele_transformers_present
        except ImportError as exc:
            if self.ner == "auto":
                _journal.warning(
                    "NER indisponible (extra [ner] non installé) : "
                    "détection déterministe seule, couverture moindre."
                )
                return []
            raise ConfigurationInvalide(
                f"SAS_NER={self.ner} exige l'extra [ner] (voir README)"
            ) from exc
        if self.ner == "auto":
            if not modele_transformers_present():
                _journal.warning(
                    "Modèle NER absent du cache local : détection déterministe "
                    "seule. Exécuter python -m sas_confiance_ia.telechargement."
                )
                return []
            return [creer_moteur_ner()]
        return [creer_moteur_ner(moteur=self.ner)]


def charger_configuration(env: Mapping[str, str] | None = None) -> Configuration:
    env = os.environ if env is None else env

    base_url = env.get("SAS_BACKEND_BASE_URL", "").strip()
    if not base_url:
        raise ConfigurationInvalide(
            "SAS_BACKEND_BASE_URL est requise (ex. http://localhost:11434/v1)"
        )
    modeles = [m.strip() for m in env.get("SAS_MODELES", "").split(",") if m.strip()]
    if not modeles:
        raise ConfigurationInvalide(
            "SAS_MODELES est requise : liste de modèles séparés par des virgules"
        )
    ner = env.get("SAS_NER", "auto").strip()
    if ner not in MODES_NER:
        raise ConfigurationInvalide(f"SAS_NER={ner!r} invalide (attendu : {', '.join(MODES_NER)})")
    vault_chemin = env.get("SAS_VAULT_CHEMIN") or None
    vault_cle = env.get("SAS_VAULT_CLE") or None
    if vault_chemin is not None and vault_cle is None:
        raise ConfigurationInvalide(
            "SAS_VAULT_CHEMIN sans SAS_VAULT_CLE : le vault persistant est "
            "toujours chiffré (REQ-004), fournir la clé via un secret"
        )

    return Configuration(
        backend_base_url=base_url,
        backend_cle_api=env.get("SAS_BACKEND_CLE_API") or None,
        backend_timeout=float(
            env.get("SAS_BACKEND_TIMEOUT_SECONDES", str(DELAI_DEFAUT_SECONDES))
        ),
        modeles=modeles,
        ner=ner,
        vault_chemin=vault_chemin,
        vault_cle=vault_cle,
    )


def creer_application_depuis_environnement(env: Mapping[str, str] | None = None):
    """Assemble l'application FastAPI complète depuis l'environnement."""
    config = charger_configuration(env)
    backend = BackendOpenAICompatible(
        base_url=config.backend_base_url,
        cle_api=config.backend_cle_api,
        timeout=config.backend_timeout,
    )
    pseudonymiseur = Pseudonymiseur(config.creer_vault(), moteurs=config.creer_moteurs())
    return creer_application(
        pseudonymiseur=pseudonymiseur, backend=backend, modeles=config.modeles
    )
