"""Contrôle d'intégrité des réponses IA (REQ-006, cadrage §9.7 et §14.6).

Le LLM applicatif est une boîte noire non fiable (02-AI-SPEC) : il peut
conserver, altérer, inventer ou supprimer des placeholders. Lecture tolérante
pour les altérations bénignes, blocage pour les inconnus, signalement pour
les manquants.
"""

import re
from dataclasses import dataclass, field

MOTIF_TOLERANT = re.compile(r"\[([A-Z_]+?)[ _](\d{1,4})\]")


def normaliser_placeholders(texte: str) -> str:
    """Ramène les placeholders altérés à la forme canonique [TYPE_NNN] (F5)."""
    return MOTIF_TOLERANT.sub(lambda m: f"[{m.group(1)}_{int(m.group(2)):03d}]", texte)


@dataclass(frozen=True)
class RapportIntegrite:
    integrite_ok: bool
    placeholders_inconnus: list[str] = field(default_factory=list)
    placeholders_manquants: list[str] = field(default_factory=list)

    @property
    def action(self) -> str:
        return "ok" if self.integrite_ok else "review_required"

    def en_dict(self) -> dict:
        return {
            "integrite_ok": self.integrite_ok,
            "placeholders_inconnus": self.placeholders_inconnus,
            "placeholders_manquants": self.placeholders_manquants,
            "action": self.action,
        }


def controler(
    texte_normalise: str,
    placeholders_envoyes: set[str],
    placeholders_connus: set[str],
) -> RapportIntegrite:
    """Compare les placeholders de la réponse au vault et à ce qui a été envoyé.

    Un placeholder inconnu du vault bloque (REQ-006). Un placeholder envoyé
    mais absent de la réponse est signalé sans bloquer : un résumé peut
    légitimement ne pas reprendre toutes les coordonnées.
    """
    presents = set(MOTIF_TOLERANT.findall(texte_normalise))
    presents_canoniques = {f"[{nom}_{int(num):03d}]" for nom, num in presents}
    inconnus = sorted(presents_canoniques - placeholders_connus)
    manquants = sorted(placeholders_envoyes - presents_canoniques)
    return RapportIntegrite(
        integrite_ok=not inconnus,
        placeholders_inconnus=inconnus,
        placeholders_manquants=manquants,
    )
