"""Configuration d'exécution par variables d'environnement (Lot 10, REQ-013).

Rien en dur : changer de backend (Ollama local, Infomaniak, Scaleway, tout
endpoint OpenAI-compatible) ne demande qu'un changement de configuration.

| Variable | Rôle | Défaut |
|---|---|---|
| SAS_BACKEND_BASE_URL | base URL OpenAI-compatible (requis) | aucun |
| SAS_BACKEND_CLE_API | clé API Bearer (optionnelle, via secret) | aucune |
| SAS_BACKEND_TIMEOUT_SECONDES | timeout d'appel backend | 120 |
| SAS_MODELES | modèles exposés par /v1/models, séparés par des virgules (requis) | aucun |
| SAS_NER | transformers, spacy ou inactif | transformers |
| SAS_VAULT_CHEMIN | fichier vault chiffré persistant | aucun (vault mémoire) |
| SAS_VAULT_CLE | clé Fernet du vault (via secret, jamais committée) | aucune |
| SAS_JUGE_BASE_URL | base URL OpenAI-compatible LOCALE du juge C3 | aucune (juge absent) |
| SAS_JUGE_MODELE | modèle du juge (requis si base URL fournie) | aucun |
| SAS_JUGE_SCORE_MIN | score minimal des candidats du juge | 0.5 |
| SAS_JUGE_TIMEOUT_SECONDES | timeout dédié de la passe juge | 60 |
| SAS_POLITIQUES | politiques par type « TYPE=action,... » (§9.5) | aucune (tout pseudonymisé) |

Défauts protecteurs : sans chemin ET clé, le vault reste en mémoire (rien
n'est écrit sur disque) ; le NER est actif par défaut et **fail-closed** :
modèle ou dépendances absents = démarrage refusé avec message actionnable.
La couverture ne se dégrade que par choix explicite (SAS_NER=inactif).
Le juge C3 est optionnel PAR CONCEPTION (REQ-014, contrairement au NER
fail-closed) : absent = sas fonctionnel documenté moins couvrant, journalisé.
Une variable vide vaut absente (docker compose transmet ${VAR:-}).
"""

import importlib.util
import ipaddress
import logging
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from .api import creer_application
from .backends import DELAI_DEFAUT_SECONDES, BackendOpenAICompatible
from .juge import SCORE_MIN_DEFAUT, JugeLLM
from .politique import ACTION_CONSERVER, Politique, analyser_politiques
from .pseudonymiseur import Pseudonymiseur
from .vault import Vault, VaultChiffre, VaultMemoire

MODES_NER = ("transformers", "spacy", "inactif")


def _dependances_ner_presentes() -> bool:
    return importlib.util.find_spec("presidio_analyzer") is not None


def _modele_transformers_present() -> bool:
    from .ner import modele_transformers_present

    return modele_transformers_present()


def _repli_spacy_present() -> bool:
    from .ner import MODELE_SPACY_REPLI

    return importlib.util.find_spec(MODELE_SPACY_REPLI) is not None

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
    juge_base_url: str | None
    juge_modele: str | None
    juge_score_min: float
    juge_timeout: float
    politiques: dict[str, str]

    def creer_juge(self) -> JugeLLM | None:
        """Juge C3 optionnel et dégradable (REQ-014) : absent = documenté.

        Garantie « le juge n'appelle jamais un service distant » tenue au
        démarrage, pas seulement dans la suite de tests : l'hôte du juge
        doit se résoudre en adresses locales ou privées, sinon refus.
        """
        if self.juge_base_url is None:
            _journal.info(
                "juge LLM absent (SAS_JUGE_BASE_URL non définie) : couverture "
                "C1+C2 seule, les identifiants indirects ne sont pas signalés "
                "(REQ-014, choix documenté)."
            )
            return None
        _verifier_hote_local(self.juge_base_url)
        backend = BackendOpenAICompatible(
            base_url=self.juge_base_url, timeout=self.juge_timeout
        )
        return JugeLLM(backend, modele=self.juge_modele, score_min=self.juge_score_min)

    def creer_vault(self) -> Vault:
        if self.vault_chemin is not None and self.vault_cle is not None:
            return VaultChiffre(self.vault_chemin, self.vault_cle.encode())
        return VaultMemoire()

    def creer_moteurs(self) -> list:
        """Moteurs de détection additionnels selon SAS_NER (fail-closed).

        La couverture NER ne se perd jamais en silence : toute impossibilité
        de charger le moteur demandé refuse le démarrage avec un message
        actionnable ; la désactivation est un choix explicite et journalisé.
        """
        if self.ner == "inactif":
            _journal.warning(
                "SAS_NER=inactif : détection déterministe seule, les noms, "
                "lieux et organisations ne sont PAS couverts (choix explicite)."
            )
            return []
        if not _dependances_ner_presentes():
            raise ConfigurationInvalide(
                f"SAS_NER={self.ner} exige l'extra [ner] "
                "(uv pip install -e '.[ner]', voir README) ; pour un sas sans "
                "NER, choisir explicitement SAS_NER=inactif"
            )
        if self.ner == "transformers" and not _modele_transformers_present():
            raise ConfigurationInvalide(
                "modèle NER absent du cache local : exécuter "
                "python -m sas_confiance_ia.telechargement (une seule fois), "
                "ou choisir explicitement SAS_NER=inactif"
            )
        if self.ner == "spacy" and not _repli_spacy_present():
            raise ConfigurationInvalide(
                "SAS_NER=spacy exige l'extra [ner-repli-spacy] "
                "(non embarqué dans l'image Docker de référence)"
            )
        from .ner import creer_moteur_ner

        return [creer_moteur_ner(moteur=self.ner)]


def _verifier_hote_local(base_url: str) -> None:
    """Refuse un juge dont l'hôte ne se résout pas en zone de confiance.

    Le texte soumis au juge contient précisément les identifiants indirects
    que C1+C2 ont manqués : il ne quitte JAMAIS la boucle locale ou le
    réseau privé (REQ-001, REQ-014). Vérification au démarrage ; un hôte
    non résoluble est refusé aussi (impossible de prouver qu'il est local).
    """
    hote = urlsplit(base_url).hostname
    if not hote:
        raise ConfigurationInvalide(f"SAS_JUGE_BASE_URL={base_url!r} : hôte illisible")
    try:
        adresses = {info[4][0] for info in socket.getaddrinfo(hote, None)}
    except OSError as exc:
        raise ConfigurationInvalide(
            f"SAS_JUGE_BASE_URL : hôte {hote!r} non résoluble, impossible de "
            "vérifier qu'il désigne une adresse locale (le juge n'appelle "
            "jamais un service distant, REQ-014). Si le juge tourne dans le "
            "réseau compose, démarrer aussi son service (profil ollama)."
        ) from exc
    for adresse in adresses:
        ip = ipaddress.ip_address(adresse.split("%")[0])
        if not (ip.is_loopback or ip.is_private or ip.is_link_local):
            raise ConfigurationInvalide(
                f"SAS_JUGE_BASE_URL : l'hôte {hote!r} se résout en {adresse}, "
                "une adresse publique. Le juge tourne exclusivement sur une "
                "adresse locale ou privée (REQ-014) : jamais de service distant."
            )


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
    ner = (env.get("SAS_NER") or "transformers").strip() or "transformers"
    if ner not in MODES_NER:
        raise ConfigurationInvalide(f"SAS_NER={ner!r} invalide (attendu : {', '.join(MODES_NER)})")
    vault_chemin = (env.get("SAS_VAULT_CHEMIN") or "").strip() or None
    vault_cle = (env.get("SAS_VAULT_CLE") or "").strip() or None
    if vault_chemin is not None and vault_cle is None:
        raise ConfigurationInvalide(
            "SAS_VAULT_CHEMIN sans SAS_VAULT_CLE : le vault persistant est "
            "toujours chiffré (REQ-004), fournir la clé via un secret"
        )
    juge_base_url = (env.get("SAS_JUGE_BASE_URL") or "").strip() or None
    juge_modele = (env.get("SAS_JUGE_MODELE") or "").strip() or None
    if juge_base_url is not None and juge_modele is None:
        raise ConfigurationInvalide(
            "SAS_JUGE_BASE_URL sans SAS_JUGE_MODELE : préciser le modèle du juge"
        )
    if juge_modele is not None and juge_base_url is None:
        raise ConfigurationInvalide(
            "SAS_JUGE_MODELE sans SAS_JUGE_BASE_URL : préciser l'endpoint "
            "OpenAI-compatible LOCAL du juge (ex. http://localhost:11434/v1)"
        )
    score_min_brut = (env.get("SAS_JUGE_SCORE_MIN") or "").strip()
    try:
        juge_score_min = float(score_min_brut) if score_min_brut else SCORE_MIN_DEFAUT
    except ValueError as exc:
        raise ConfigurationInvalide(
            f"SAS_JUGE_SCORE_MIN={score_min_brut!r} invalide : nombre entre 0 et 1 attendu"
        ) from exc
    if not 0 <= juge_score_min <= 1:
        raise ConfigurationInvalide(
            f"SAS_JUGE_SCORE_MIN={juge_score_min} invalide : nombre entre 0 et 1 attendu"
        )
    juge_timeout_brut = (env.get("SAS_JUGE_TIMEOUT_SECONDES") or "").strip()
    try:
        # Timeout DÉDIÉ, plus court que celui du backend applicatif : un
        # juge suspendu ne bloque pas le proxy pendant deux minutes.
        juge_timeout = float(juge_timeout_brut) if juge_timeout_brut else 60.0
    except ValueError as exc:
        raise ConfigurationInvalide(
            f"SAS_JUGE_TIMEOUT_SECONDES={juge_timeout_brut!r} invalide : "
            "nombre de secondes attendu"
        ) from exc
    politiques_brut = (env.get("SAS_POLITIQUES") or "").strip()
    try:
        politiques = analyser_politiques(politiques_brut)
    except ValueError as exc:
        raise ConfigurationInvalide(f"SAS_POLITIQUES : {exc}") from exc
    for type_, action in politiques.items():
        if action == ACTION_CONSERVER:
            # Couverture dégradée toujours explicite : conserver un type
            # détectable est un choix, il laisse une trace au démarrage.
            _journal.warning(
                "SAS_POLITIQUES : le type %s est configuré en « conserver », "
                "ses valeurs partiront EN CLAIR vers le backend (choix explicite).",
                type_,
            )
    timeout_brut = (env.get("SAS_BACKEND_TIMEOUT_SECONDES") or "").strip()
    try:
        backend_timeout = float(timeout_brut) if timeout_brut else DELAI_DEFAUT_SECONDES
    except ValueError as exc:
        raise ConfigurationInvalide(
            f"SAS_BACKEND_TIMEOUT_SECONDES={timeout_brut!r} invalide : nombre de secondes attendu"
        ) from exc

    return Configuration(
        backend_base_url=base_url,
        backend_cle_api=(env.get("SAS_BACKEND_CLE_API") or "").strip() or None,
        backend_timeout=backend_timeout,
        modeles=modeles,
        ner=ner,
        vault_chemin=vault_chemin,
        vault_cle=vault_cle,
        juge_base_url=juge_base_url,
        juge_modele=juge_modele,
        juge_score_min=juge_score_min,
        juge_timeout=juge_timeout,
        politiques=politiques,
    )


def creer_application_depuis_environnement(env: Mapping[str, str] | None = None):
    """Assemble l'application FastAPI complète depuis l'environnement."""
    config = charger_configuration(env)
    backend = BackendOpenAICompatible(
        base_url=config.backend_base_url,
        cle_api=config.backend_cle_api,
        timeout=config.backend_timeout,
    )
    pseudonymiseur = Pseudonymiseur(
        config.creer_vault(),
        moteurs=config.creer_moteurs(),
        politique=Politique(actions=config.politiques),
    )
    return creer_application(
        pseudonymiseur=pseudonymiseur,
        backend=backend,
        modeles=config.modeles,
        juge=config.creer_juge(),
    )
