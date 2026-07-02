"""Proxy OpenAI-compatible : /v1/chat/completions et /v1/models.

Flux (01-PRD §5) : réception → pseudonymisation → backend → réponse.
Le contrôle d'intégrité et la ré-identification de la réponse arrivent au
Lot 7 ; le streaming est refusé (REQ-010).
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .backends import Backend, ErreurBackend
from .integrite import controler, normaliser_placeholders
from .journal import Journal
from .juge import JugeLLM, executer_passe
from .pseudonymiseur import MOTIF_PLACEHOLDER, Pseudonymiseur

# Parade F5 (02-AI-SPEC §3) : le LLM applicatif altère volontiers les
# jetons (crochets perdus, casse, faute sur le type, constaté sur
# mistral-small:24b). Cette consigne est injectée en tête de conversation
# dès qu'un placeholder part dans le payload.
CONSIGNE_PRESERVATION_JETONS = (
    "Le texte de l'utilisateur contient des jetons de pseudonymisation au "
    "format [TYPE_NNN], par exemple [PERSONNE_001]. Recopie ces jetons "
    "EXACTEMENT à l'identique (crochets, majuscules, tiret bas, zéros) "
    "chaque fois que tu y fais référence. Ne les traduis pas, ne les "
    "reformule pas, n'en invente jamais de nouveaux."
)


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
    juge: JugeLLM | None = None,
) -> FastAPI:
    journal = journal or Journal()
    application = FastAPI(title="Sas Confiance IA", docs_url=None, redoc_url=None)

    # Séparation démo / sérieux (REQ-007) : portée par le vault, donc
    # persistante avec les données (un redémarrage ne la réinitialise pas).
    vault = pseudonymiseur.vault

    from .ui import creer_routeur_ui

    application.include_router(creer_routeur_ui(pseudonymiseur, journal, juge=juge))

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
        # Le proxy travaille toujours en mode sérieux (REQ-007) : un dossier
        # passé en démonstration est refusé sur ce chemin aussi.
        if vault.mode_dossier(dossier_id) == "demo":
            journal.enregistrer(
                requete_id=requete_id,
                dossier_id=dossier_id,
                backend=type(backend).__name__,
                modele=requete.model,
                statut="refus_dossier_demo",
            )
            raise HTTPException(
                status_code=409,
                detail="Ce dossier a été utilisé en mode démonstration : il ne "
                "peut plus servir en mode sérieux (séparation REQ-007).",
            )
        vault.marquer_dossier(dossier_id, "serieux")
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
        ambiguites_coreference: set[str] = set()
        entites_en_revue: set[str] = set()
        for message in requete.messages:
            resultat = pseudonymiseur.pseudonymiser(message.content, dossier_id=dossier_id)
            # Seuls les placeholders numérotés (réversibles) participent au
            # contrôle d'intégrité : un marqueur de masquage [TYPE] sans
            # numéro (Lot 14) n'a pas d'entrée vault et n'est jamais attendu
            # dans la réponse.
            placeholders_envoyes.update(
                r.placeholder
                for r in resultat.remplacements
                if MOTIF_PLACEHOLDER.fullmatch(r.placeholder)
            )
            for type_, compte in resultat.comptes_par_type.items():
                entites_par_type[type_] = entites_par_type.get(type_, 0) + compte
            ambiguites_coreference.update(resultat.ambiguites)
            entites_en_revue.update(resultat.en_revue)
            messages_pseudonymises.append({"role": message.role, "content": resultat.texte})

        # Passe juge (C3, REQ-014) sur le SEUL dernier message pseudonymisé :
        # le proxy est sans état, l'historique a été jugé aux tours
        # précédents (coût constant par tour, pas linéaire). Les positions se
        # lisent dans le message ORIGINAL correspondant, que l'appelant
        # possède (Q3 : jamais de segment en clair dans la réponse). En v1
        # les candidats partent en revue, jamais en remplacement : les
        # segments signalés sont donc déjà partis vers le backend au moment
        # où l'appelant les lit (limite documentée).
        index_dernier = len(requete.messages) - 1
        texte_juge = messages_pseudonymises[index_dernier]["content"]
        reference_juge = requete.messages[index_dernier].content

        if placeholders_envoyes:
            messages_pseudonymises.insert(
                0, {"role": "system", "content": CONSIGNE_PRESERVATION_JETONS}
            )
        payload: dict[str, Any] = {"model": requete.model, "messages": messages_pseudonymises}
        if requete.temperature is not None:
            payload["temperature"] = requete.temperature
        if requete.max_tokens is not None:
            payload["max_tokens"] = requete.max_tokens

        # La passe juge court en parallèle de l'appel au backend applicatif
        # (elles sont indépendantes) : la latence ajoutée est bornée par le
        # timeout DÉDIÉ du juge, pas cumulée à celle du backend.
        with ThreadPoolExecutor(max_workers=1) as executeur:
            futur_juge = executeur.submit(
                executer_passe,
                juge,
                texte_juge,
                texte_reference=reference_juge,
                journal=journal,
                requete_id=requete_id,
                dossier_id=dossier_id,
            )
            try:
                reponse = backend.completer(payload)
            except ErreurBackend as erreur:
                # Le détail ne contient que le type d'erreur : jamais le
                # message de l'usager ni la réponse du fournisseur (REQ-003).
                journal.enregistrer(
                    requete_id=requete_id,
                    dossier_id=dossier_id,
                    backend=type(backend).__name__,
                    modele=requete.model,
                    statut="erreur_backend",
                    erreur_type=erreur.erreur_type,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Backend indisponible ({erreur.erreur_type}).",
                ) from erreur
            bloc_juge = futur_juge.result()
        if juge is not None:
            bloc_juge["message_index"] = index_dernier

        # Contrôle d'intégrité (REQ-006) : lecture tolérante des placeholders
        # altérés, blocage de la ré-identification en présence d'un inconnu.
        placeholders_connus = pseudonymiseur.placeholders_connus(dossier_id)
        contenu = normaliser_placeholders(reponse.contenu, connus=placeholders_connus)
        rapport = controler(
            contenu,
            placeholders_envoyes=placeholders_envoyes,
            placeholders_connus=placeholders_connus,
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
            # Un échec du juge reste distinguable d'une passe sans candidat :
            # jamais un candidats_juge=0 trompeur (REQ-014, couverture
            # dégradée toujours explicite).
            juge_statut=(
                None
                if juge is None
                else ("erreur" if "erreur_type" in bloc_juge else "ok")
            ),
            candidats_juge=(
                len(bloc_juge["candidats"])
                if juge is not None and "erreur_type" not in bloc_juge
                else None
            ),
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
                # Placeholders PERSONNE créés faute de rattachement sûr
                # (REQ-011, F4) : à faire vérifier par un humain. Seuls les
                # placeholders sont exposés, jamais les valeurs.
                "ambiguites_coreference": sorted(ambiguites_coreference),
                # Placeholders masqués par une politique « revue » (Lot 14) :
                # partis pseudonymisés vers le backend, à faire relire.
                "entites_en_revue": sorted(entites_en_revue),
                # Candidats d'identifiants indirects signalés par le juge
                # LLM local (C3) : à revoir par un humain, jamais remplacés
                # automatiquement en v1 (REQ-014, parade F7).
                "juge": bloc_juge,
            },
        }

    return application
