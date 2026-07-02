"""Politiques de remplacement par type d'entité (Lot 14, cadrage §9.5).

Quatre actions par type détecté :
- pseudonymiser (défaut) : placeholder réversible par le vault ;
- masquer : marqueur [TYPE] sans numéro, sans entrée vault, irréversible
  (le caviardage façon /mask de rbochet/amo-presidio) ;
- conserver : la valeur reste en clair, choix explicite journalisé ;
- revue : pseudonymisé ET signalé pour relecture humaine.

La politique vit avec les données : défauts d'instance par l'environnement
(SAS_POLITIQUES), surcharge par dossier stockée dans le vault, comme le mode
démo / sérieux (REQ-007). En cas d'ambiguïté, l'action la plus protectrice
reste le défaut : tout type détecté est pseudonymisé sauf choix contraire.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

ACTION_PSEUDONYMISER = "pseudonymiser"
ACTION_MASQUER = "masquer"
ACTION_CONSERVER = "conserver"
ACTION_REVUE = "revue"
ACTIONS = (ACTION_PSEUDONYMISER, ACTION_MASQUER, ACTION_CONSERVER, ACTION_REVUE)

# Défauts par type quand ni l'instance ni le dossier n'ont tranché. Tout type
# détecté est pseudonymisé, à une exception près, fixée par REQ-008 : les
# dates procédurales (décision, séance, accident) sont conservées par défaut,
# elles portent l'utilité métier du texte ; la date de naissance, elle, reste
# masquée par défaut comme tout le reste.
DEFAUTS: dict[str, str] = {"DATE_PROCEDURALE": ACTION_CONSERVER}


def _types_connus() -> list[str]:
    from .detection import PRIORITE

    return PRIORITE


def valider_actions(actions: Mapping[str, str]) -> None:
    """Refuse toute action ou type inconnu : une faute de frappe dans une
    politique ne doit jamais dégrader la couverture en silence."""
    types_connus = _types_connus()
    for type_, action in actions.items():
        if type_ not in types_connus:
            raise ValueError(
                f"type d'entité inconnu dans la politique : {type_!r} "
                f"(types connus : {', '.join(types_connus)})"
            )
        if action not in ACTIONS:
            raise ValueError(
                f"action inconnue pour {type_} : {action!r} "
                f"(actions : {', '.join(ACTIONS)})"
            )


def analyser_politiques(brut: str) -> dict[str, str]:
    """Analyse le format de SAS_POLITIQUES : « TYPE=action,TYPE=action »."""
    actions: dict[str, str] = {}
    for morceau in brut.split(","):
        morceau = morceau.strip()
        if not morceau:
            continue
        type_, egal, action = morceau.partition("=")
        if not egal:
            raise ValueError(
                f"entrée de politique illisible : {morceau!r} (attendu TYPE=action)"
            )
        actions[type_.strip()] = action.strip()
    valider_actions(actions)
    return actions


@dataclass(frozen=True)
class Politique:
    """Actions par type d'entité ; tout type absent est pseudonymisé."""

    actions: Mapping[str, str] = field(default_factory=dict)

    def action_pour(self, type_: str) -> str:
        return self.actions.get(type_) or DEFAUTS.get(type_, ACTION_PSEUDONYMISER)

    def surcharger(self, surcharge: "Politique") -> "Politique":
        return Politique(actions={**self.actions, **surcharge.actions})

    def en_dict(self) -> dict:
        return {"actions": dict(self.actions)}

    @classmethod
    def depuis_dict(cls, contenu: Mapping) -> "Politique":
        return cls(actions=dict(contenu.get("actions", {})))
