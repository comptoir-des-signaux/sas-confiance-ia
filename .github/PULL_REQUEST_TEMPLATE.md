<!--
Merci pour cette contribution. Ce gabarit reprend la définition de « terminé »
du projet (CONTRIBUTING.md). Supprimez les sections sans objet.
-->

## Ce que fait cette pull request

<!-- Une phrase. Le besoin métier, pas la solution technique. -->

## Exigences touchées

<!-- REQ-001 à 016, ou « aucune ». Voir docs/specs/03-SPEC.md. -->

## Vérifications

- [ ] Le test arrive **avant** l'implémentation, et il échouait sans elle.
- [ ] `uv run pytest` : suite complète verte.
- [ ] `uv run ruff check src tests` : propre.
- [ ] Les tests de non-fuite (payload et journaux) passent sur toute la suite.
- [ ] **Aucun invariant de sécurité affaibli** (REQ-001 à 010). Si un test
      d'invariant me semblait faux, j'ai ouvert une issue au lieu de le modifier.
- [ ] **Aucune donnée personnelle réelle** : exemples, fixtures, docstrings et
      tests s'appuient sur `corpus/synthetique/` ou des valeurs inventées à
      clés valides.
- [ ] **Aucun appel réseau** ajouté dans la suite de tests.
- [ ] Pas de secret, pas de clé, pas de `.env` versionné.
- [ ] La documentation touchée est mise à jour **dans le même commit**.
- [ ] Commits atomiques, messages en français accentué, pas de tiret cadratin.
- [ ] Aucun `TODO` silencieux : tout report est tracé dans
      `docs/specs/QUESTIONS.md`.

## Nouvelle dépendance

<!--
S'il y en a une : nom, version, licence, et pourquoi elle est compatible
EUPL-1.2. Rappel : PyMuPDF (AGPL) a été écartée pour cette raison (Q6).
Si aucune : « aucune ».
-->

## Effet sur la couverture de détection

<!--
Cette PR modifie-t-elle le rappel ou la précision ? Si oui, joignez la mesure
mise à jour (docs/eval/). Une mesure qui baisse et qui est publiée vaut mieux
qu'une mesure tue.
-->
