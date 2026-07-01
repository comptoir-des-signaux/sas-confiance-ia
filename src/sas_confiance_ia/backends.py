"""Backends IA : abstraction OpenAI-compatible et faux backend de capture.

Le faux backend (BackendCapture) est la pierre angulaire de REQ-001 : il
enregistre le payload JSON exactement tel qu'il serait écrit sur le réseau,
afin que les tests puissent prouver l'absence de valeurs brutes. Les tests
n'utilisent jamais de backend réel (HANDOFF, règle 1).
"""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx2


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


class ErreurBackend(Exception):
    """Échec d'appel au backend réel.

    Ne transporte JAMAIS le payload ni le corps de la réponse : son message
    finit dans le détail HTTP et le journal (REQ-003), seul le type d'erreur
    et un message technique neutre y ont leur place.
    """

    def __init__(self, erreur_type: str, message: str) -> None:
        super().__init__(message)
        self.erreur_type = erreur_type


DELAI_DEFAUT_SECONDES = 120.0


class BackendOpenAICompatible:
    """Backend réel OpenAI-compatible (Ollama, Infomaniak, Scaleway, ...).

    Aucun code spécifique par fournisseur (REQ-013) : une base URL, une clé
    API optionnelle (Bearer), un timeout explicite. Le paramètre `transport`
    n'existe que pour les tests (MockTransport) : la suite ne parle jamais
    au réseau (HANDOFF, règle 1).
    """

    def __init__(
        self,
        base_url: str,
        cle_api: str | None = None,
        timeout: float = DELAI_DEFAUT_SECONDES,
        transport: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cle_api = cle_api
        self._client = httpx2.Client(
            base_url=self.base_url, timeout=timeout, transport=transport
        )

    def completer(self, payload: dict[str, Any]) -> ReponseBackend:
        en_tetes = {}
        if self._cle_api:
            en_tetes["Authorization"] = f"Bearer {self._cle_api}"
        try:
            reponse = self._client.post("/chat/completions", json=payload, headers=en_tetes)
            reponse.raise_for_status()
            corps = reponse.json()
        except httpx2.HTTPStatusError as exc:
            raise ErreurBackend(
                "HTTPStatusError",
                f"le backend a répondu {exc.response.status_code}",
            ) from exc
        except httpx2.HTTPError as exc:
            raise ErreurBackend(type(exc).__name__, "échec de l'appel au backend") from exc
        except ValueError as exc:
            raise ErreurBackend("FormatReponseInvalide", "réponse non JSON du backend") from exc

        try:
            contenu = corps["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ErreurBackend(
                "FormatReponseInvalide", "réponse JSON hors format OpenAI"
            ) from exc
        if not isinstance(contenu, str):
            # content: null (réponse à tool_calls par exemple) : le sas ne
            # gère pas les outils, un None casserait l'intégrité en aval.
            raise ErreurBackend("FormatReponseInvalide", "contenu de réponse non textuel")
        return ReponseBackend(
            contenu=contenu, modele=corps.get("model", payload.get("model", ""))
        )
