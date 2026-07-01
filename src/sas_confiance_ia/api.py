"""Proxy OpenAI-compatible : /v1/chat/completions et /v1/models.

Flux (01-PRD §5) : réception → pseudonymisation → backend → réponse.
Le contrôle d'intégrité et la ré-identification de la réponse arrivent au
Lot 7 ; le streaming est refusé (REQ-010).
"""

import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .backends import Backend
from .pseudonymiseur import Pseudonymiseur


class MessageChat(BaseModel):
    role: str
    content: str


class RequeteChatCompletion(BaseModel):
    model: str
    messages: list[MessageChat]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


def creer_application(
    pseudonymiseur: Pseudonymiseur,
    backend: Backend,
    modeles: list[str],
) -> FastAPI:
    application = FastAPI(title="Sas Confiance IA", docs_url=None, redoc_url=None)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"statut": "ok"}

    @application.get("/v1/models")
    def lister_modeles() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": m, "object": "model", "owned_by": "sas-confiance-ia"} for m in modeles],
        }

    @application.post("/v1/chat/completions")
    def chat_completions(
        requete: RequeteChatCompletion,
        x_dossier_id: str | None = Header(default=None),
        x_reidentify_response: bool = Header(default=True),
    ) -> dict[str, Any]:
        if requete.stream:
            raise HTTPException(
                status_code=400,
                detail="Le streaming (stream=true) est refusé en v1 : les placeholders "
                "peuvent être coupés entre deux chunks (REQ-010).",
            )
        dossier_id = x_dossier_id or f"dossier-{uuid.uuid4()}"

        messages_pseudonymises = []
        placeholders_envoyes: set[str] = set()
        for message in requete.messages:
            resultat = pseudonymiseur.pseudonymiser(message.content, dossier_id=dossier_id)
            placeholders_envoyes.update(r.placeholder for r in resultat.remplacements)
            messages_pseudonymises.append({"role": message.role, "content": resultat.texte})

        payload: dict[str, Any] = {"model": requete.model, "messages": messages_pseudonymises}
        if requete.temperature is not None:
            payload["temperature"] = requete.temperature
        if requete.max_tokens is not None:
            payload["max_tokens"] = requete.max_tokens

        reponse = backend.completer(payload)

        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": reponse.modele,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reponse.contenu},
                    "finish_reason": "stop",
                }
            ],
        }

    return application
