"""Backends IA : abstraction OpenAI-compatible et faux backend de capture.

Le faux backend (BackendCapture) est la pierre angulaire de REQ-001 : il
enregistre le payload JSON exactement tel qu'il serait écrit sur le réseau,
afin que les tests puissent prouver l'absence de valeurs brutes. Les tests
n'utilisent jamais de backend réel (HANDOFF, règle 1).
"""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ReponseBackend:
    contenu: str
    modele: str


class Backend(Protocol):
    """Un backend reçoit un payload au format OpenAI et renvoie la réponse."""

    def completer(self, payload: dict[str, Any]) -> ReponseBackend: ...


@dataclass
class BackendCapture:
    """Faux backend de test : capture le payload exact, renvoie un contenu fixe.

    `contenu_reponse` peut contenir des placeholders pour exercer la
    ré-identification et le contrôle d'intégrité (Lot 7).
    """

    contenu_reponse: str = "Réponse synthétique."
    payloads_bruts: list[str] = field(default_factory=list)

    def completer(self, payload: dict[str, Any]) -> ReponseBackend:
        # Sérialisation identique à ce qui partirait sur le réseau.
        self.payloads_bruts.append(json.dumps(payload, ensure_ascii=False))
        return ReponseBackend(contenu=self.contenu_reponse, modele=payload.get("model", ""))


class BackendOpenAICompatible:
    """Backend réel (Ollama, Infomaniak, Scaleway, ...) : Phase 1, Lot 10.

    Défini ici pour fixer l'interface ; volontairement non implémenté en
    Phase 0 (aucun appel externe, HANDOFF règle 1).
    """

    def __init__(self, base_url: str, cle_api: str | None = None) -> None:
        self.base_url = base_url
        self._cle_api = cle_api

    def completer(self, payload: dict[str, Any]) -> ReponseBackend:
        raise NotImplementedError("Backend réel : Lot 10 (Phase 1).")
