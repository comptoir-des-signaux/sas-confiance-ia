# Évaluation de la couche NER (C2)

**Mesure du 2026-07-02** sur le corpus synthétique (`corpus/synthetique/`),
moteur transformers de Presidio, modèle `Jean-Baptiste/camembert-ner`
épinglé à la révision `ef35fe7767c1dad71f5c853838cdd80d0b3441ed`,
seuil de score 0,5.

Conformément au 02-AI-SPEC §4.2, ces types n'ont **pas de cible
contractuelle** : la mesure est publiée telle quelle. La porte de qualité 4.4
interdit toute régression de rappel de plus de 2 points (test
`test_porte_4_4_pas_de_regression_de_rappel_de_plus_de_2_points`, baseline
committée dans [`ner-baseline.json`](ner-baseline.json)).

## Résultats

| Type | Rappel | Précision | Mentions couvertes | Détections correctes |
|---|---|---|---|---|
| PERSONNE | 95,8 % | 92,3 % | 23/24 | 24/26 |
| ORGANISATION | 100,0 % | 25,0 % | 1/1 | 1/4 |
| LIEU | 82,6 % | 100,0 % | 19/23 | 24/24 |

## Méthodologie

- Vérité terrain : `corpus/synthetique/verite-terrain-ner.json` (mentions
  annotées à la main ; `06-canaris.md` exclu par construction, ses
  identifiants indirects relèvent du juge LLM, 02-AI-SPEC §4.3).
- **Rappel** (critère protecteur) : une mention n'est comptée couverte que si
  une entité du bon type la recouvre entièrement. Une détection partielle
  (« Benali » pour « Mme Benali ») compte comme un manqué.
- **Précision** : une détection est correcte si elle recouvre, même
  partiellement, une mention de la vérité terrain du même type.
- Reproduire : `uv run python -m sas_confiance_ia.evaluation`.

## Lecture honnête des chiffres

- **Les manqués de rappel sont tous des recouvrements partiels**, pas des
  absences : « avenue de l'Industrie » détectée en deux fragments,
  « Mme Benali » sans la civilité, « place des Cornières » et « chemin du
  Moulin » réduits au nom propre. En pratique, la pseudonymisation brise
  quand même la valeur complète : la simulation de non-fuite sur l'oracle
  (`test_req_001_perimetre_complet`, tests/test_proxy.py) passe à zéro fuite.
- **La précision ORGANISATION (25 %) traduit du sur-masquage bénin** (F2 du
  02-AI-SPEC) : « Prestataire » et « Madame, Monsieur » pris pour des
  entités. Coût d'utilité, pas de sécurité ; la politique par type (Lot 14)
  et les seuils par type en sont les leviers.
- Une seule organisation réelle dans le corpus : la mesure ORGANISATION est
  fragile par construction (échantillon minuscule) ; étoffer le corpus est
  préférable à toute conclusion.
- Le repli spaCy (`fr_core_news_lg`, extra `[ner-repli-spacy]`) est couvert
  par un test fonctionnel mais pas par cette mesure : sa couverture est
  attendue moindre que CamemBERT.
