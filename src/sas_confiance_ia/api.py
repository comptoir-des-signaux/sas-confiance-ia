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
from .integrite import controler, normaliser_placeholders
from .journal import Journal
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
    journal: Journal | None = None,
) -> FastAPI:
    journal = journal or Journal()
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
        requete_id = str(uuid.uuid4())
        dossier_id = x_dossier_id or f"dossier-{uuid.uuid4()}"
        if requete.stream:
            journal.enregistrer(
                requete_id=requete_id,
                dossier_id=dossier_id,
                backend=type(backend).__name__,
                modele=requete.model,
                statut="refus_streaming",
            )
            raise HTTPException(
                status_code=400,
                detail="Le streaming (stream=true) est refusé en v1 : les placeholders "
                "peuvent être coupés entre deux chunks (REQ-010).",
            )

        messages_pseudonymises = []
        placeholders_envoyes: set[str] = set()
        entites_par_type: dict[str, int] = {}
        for message in requete.messages:
            resultat = pseudonymiseur.pseudonymiser(message.content, dossier_id=dossier_id)
            placeholders_envoyes.update(r.placeholder for r in resultat.remplacements)
            for type_, compte in resultat.comptes_par_type.items():
                entites_par_type[type_] = entites_par_type.get(type_, 0) + compte
            messages_pseudonymises.append({"role": message.role, "content": resultat.texte})

        payload: dict[str, Any] = {"model": requete.model, "messages": messages_pseudonymises}
        if requete.temperature is not None:
            payload["temperature"] = requete.temperature
        if requete.max_tokens is not None:
            payload["max_tokens"] = requete.max_tokens

        reponse = backend.completer(payload)

        # Contrôle d'intégrité (REQ-006) : lecture tolérante des placeholders
        # altérés, blocage de la ré-identification en présence d'un inconnu.
        contenu = normaliser_placeholders(reponse.contenu)
        rapport = controler(
            contenu,
            placeholders_envoyes=placeholders_envoyes,
            placeholders_connus=pseudonymiseur.placeholders_connus(dossier_id),
        )
        reidentifie = False
        if rapport.integrite_ok and x_reidentify_response:
            contenu = pseudonymiseur.reidentifier(contenu, dossier_id=dossier_id)
            reidentifie = True

        journal.enregistrer(
            requete_id=requete_id,
            dossier_id=dossier_id,
            backend=type(backend).__name__,
            modele=requete.model,
            statut="ok",
            entites_par_type=entites_par_type,
            taille_approx=sum(len(m["content"]) for m in messages_pseudonymises),
            integrite=rapport.action,
        )

        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": reponse.modele,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": contenu},
                    "finish_reason": "stop",
                }
            ],
            "sas_confiance_ia": {
                "dossier_id": dossier_id,
                "integrite": rapport.en_dict(),
                "reidentifie": reidentifie,
            },
        }

    return application
