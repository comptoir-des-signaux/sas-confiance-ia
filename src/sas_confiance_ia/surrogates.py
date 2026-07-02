"""Surrogates réalistes fr_FR (Lot 14, REQ-012, arbitrage Q5).

Un surrogate est un nom factice cohérent en genre qui remplace le placeholder
[PERSONNE_NNN] dans le texte rendu. La correspondance placeholder → surrogate
vit dans le vault, avec les autres correspondances du dossier : la
réversibilité passe toujours par le placeholder, jamais par le texte.
Portée v1 : PERSONNE uniquement (l'acceptance de REQ-012 ne porte que sur le
genre des personnes) ; les autres types gardent leurs placeholders typés.
"""


class GenerateurSurrogates:
    """Tire des noms factices Faker fr_FR, genrés quand le genre est connu.

    `graine` fige le tirage (tests) ; en production, chaque instance tire
    ses propres noms, l'unicité par dossier est garantie par `interdits`.
    """

    def __init__(self, graine: int | None = None) -> None:
        from faker import Faker

        self._faker = Faker("fr_FR")
        if graine is not None:
            self._faker.seed_instance(graine)

    def nom_personne(self, genre: str | None, interdits: set[str]) -> str:
        """Un nom inédit : jamais un nom déjà vu dans le dossier (réel ou
        factice), sinon la ré-identification restituerait le mauvais nom."""
        for _ in range(100):
            if genre == "m":
                prenom = self._faker.first_name_male()
            elif genre == "f":
                prenom = self._faker.first_name_female()
            else:
                # Genre inconnu (aucune civilité vue) : tirage libre, limite
                # documentée dans QUESTIONS.md (Q5).
                prenom = self._faker.first_name()
            nom = f"{prenom} {self._faker.last_name()}"
            if nom not in interdits:
                return nom
        raise ValueError(
            "impossible de tirer un surrogate inédit après 100 essais "
            "(dossier aux interdits anormalement nombreux)"
        )
