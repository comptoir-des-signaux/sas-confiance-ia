"""Contrôle d'intégrité des réponses IA (REQ-006, cadrage §9.7 et §14.6).

Le LLM applicatif est une boîte noire non fiable (02-AI-SPEC) : il peut
conserver, altérer, inventer ou supprimer des placeholders. Lecture tolérante
pour les altérations bénignes, blocage pour les inconnus, signalement pour
les manquants.
"""

import re
import unicodedata
from collections.abc import Set
from dataclasses import dataclass, field

from .vault import ETIQUETTES

MOTIF_TOLERANT = re.compile(r"\[([A-Z_]+?)[ _](\d{1,4})\]")

# Altérations constatées sur backend réel (F5) : crochets perdus, casse
# changée, accents ou faute d'orthographe sur le type. Entre crochets,
# l'espace est accepté comme séparateur ; sans crochets, seuls _ et - le
# sont (« personne 1 » peut être du français ordinaire).
_MOTIF_PSEUDO_CROCHETS = re.compile(r"\[([A-Za-zÀ-ÖØ-öø-ÿ_]{2,25})[ _-]0*(\d{1,4})\]")
_MOTIF_PSEUDO_NU = re.compile(
    r"(?<!\[)\b([A-Za-zÀ-ÖØ-öø-ÿ_]{2,25})[_-]0*(\d{1,4})\b(?!\])"
)


def _epurer_type(brut: str) -> str:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", brut) if not unicodedata.combining(c)
    )
    return sans_accents.upper()


def _distance_au_plus_1(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    court, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = j = ecarts = 0
    while i < len(court):
        if j >= len(long_):
            return False
        if court[i] == long_[j]:
            i += 1
            j += 1
        else:
            ecarts += 1
            if ecarts > 1:
                return False
            j += 1
    return True


def _types_et_numeros(connus: Set[str]) -> dict[str, set[int]]:
    resultat: dict[str, set[int]] = {}
    for placeholder in connus:
        m = re.fullmatch(r"\[([A-Z_]+)_(\d+)\]", placeholder)
        if m:
            resultat.setdefault(m.group(1), set()).add(int(m.group(2)))
    return resultat


def normaliser_placeholders(texte: str, connus: Set[str] = frozenset()) -> str:
    """Ramène les placeholders altérés à la forme canonique [TYPE_NNN] (F5).

    Sans contexte, seules les variantes entre crochets sont normalisées.
    Avec les placeholders connus du dossier, la restauration s'étend aux
    jetons sans crochets, à la casse changée et aux types légèrement
    altérés (« REFERANCE_001 »), à condition qu'un seul placeholder connu
    corresponde sans ambiguïté ; sinon le jeton est laissé tel quel et le
    contrôle le signalera.
    """
    texte = MOTIF_TOLERANT.sub(lambda m: f"[{m.group(1)}_{int(m.group(2)):03d}]", texte)
    if not connus:
        return texte
    types_connus = _types_et_numeros(connus)

    def restaurer(m: re.Match[str]) -> str:
        type_brut, numero = _epurer_type(m.group(1)), int(m.group(2))
        candidats = [
            type_
            for type_, numeros in types_connus.items()
            if numero in numeros and _distance_au_plus_1(type_brut, type_)
        ]
        if len(candidats) == 1:
            return f"[{candidats[0]}_{numero:03d}]"
        return m.group(0)

    texte = _MOTIF_PSEUDO_CROCHETS.sub(restaurer, texte)
    return _MOTIF_PSEUDO_NU.sub(restaurer, texte)


def _pseudo_placeholders_suspects(texte: str, connus: Set[str]) -> set[str]:
    """Jetons ressemblant à un placeholder d'un type plausible, non restaurés.

    Un type est plausible s'il est à une faute près d'une étiquette du vault
    ou d'un type déjà présent dans le dossier : « PERSONNE_999 » est suspect,
    « article_12 » ne l'est pas.
    """
    types_plausibles = set(ETIQUETTES.values()) | set(_types_et_numeros(connus))
    suspects = set()
    for motif in (_MOTIF_PSEUDO_CROCHETS, _MOTIF_PSEUDO_NU):
        for m in motif.finditer(texte):
            type_brut, numero = _epurer_type(m.group(1)), int(m.group(2))
            proches = sorted(t for t in types_plausibles if _distance_au_plus_1(type_brut, t))
            if not proches:
                continue
            canonique = f"[{proches[0]}_{numero:03d}]"
            if canonique not in connus:
                suspects.add(canonique)
    return suspects


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
    inconnus = sorted(
        (presents_canoniques - placeholders_connus)
        | _pseudo_placeholders_suspects(texte_normalise, placeholders_connus)
    )
    manquants = sorted(placeholders_envoyes - presents_canoniques)
    return RapportIntegrite(
        integrite_ok=not inconnus,
        placeholders_inconnus=inconnus,
        placeholders_manquants=manquants,
    )
