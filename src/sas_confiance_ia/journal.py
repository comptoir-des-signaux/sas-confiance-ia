"""Journal technique : gouvernance sans fuite (REQ-003, cadrage §9.8).

Le journal n'accepte que des métadonnées choisies une à une. Il n'existe
aucun chemin par lequel un prompt, une réponse, une valeur brute, un vault
ou un secret pourrait y entrer : l'API du module ne les accepte pas.
"""

import json
import logging
from datetime import UTC, datetime


class Journal:
    def __init__(self, nom: str = "sas_confiance_ia.journal") -> None:
        self._logger = logging.getLogger(nom)

    def enregistrer(
        self,
        *,
        requete_id: str,
        dossier_id: str,
        backend: str,
        modele: str,
        statut: str,
        entites_par_type: dict[str, int] | None = None,
        taille_approx: int | None = None,
        integrite: str | None = None,
        erreur_type: str | None = None,
        candidats_juge: int | None = None,
    ) -> None:
        evenement: dict[str, object] = {
            "horodatage": datetime.now(UTC).isoformat(timespec="seconds"),
            "requete_id": requete_id,
            "dossier_id": dossier_id,
            "backend": backend,
            "modele": modele,
            "statut": statut,
        }
        if entites_par_type is not None:
            evenement["entites_par_type"] = entites_par_type
        if taille_approx is not None:
            evenement["taille_approx"] = taille_approx
        if integrite is not None:
            evenement["integrite"] = integrite
        if erreur_type is not None:
            evenement["erreur_type"] = erreur_type
        if candidats_juge is not None:
            # Compte seul (REQ-003) : jamais les segments signalés par le juge.
            evenement["candidats_juge"] = candidats_juge
        self._logger.info(json.dumps(evenement, ensure_ascii=False))
