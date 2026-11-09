# I5 — limites de trace et réserves littérales

État au 9 novembre 2026 : corrections de développement préparées après la fermeture
de la phase 6, avant gel de la phase 7 et avant ouverture du corpus réservé.
Ce rapport ne transforme pas les échecs de phase 6 en réussites.

## Cadre de page dans les fragments

H06, H08 et TMP117 ont terminé avec `trace_write_failed` en phase 6. Les traces
conservent le début de requête et son erreur, sans l'événement de recherche
complet. Le classement natif manquant n'a pas été reconstitué.

Un contrôle hors moteur utilise la base exacte de phase 6 en lecture seule, le
code immuable de cette phase et un ordre dense explicitement simulé. Les règles
réelles de recherche, de filtrage et de sélection restent actives. Répéter les
diagnostics OCR complets de la page dans chaque fragment fait dépasser la limite
logique d'un événement. Le second bras change uniquement `ScopeResolver` et le
nouveau helper de cadre de page ; il conserve le même classement simulé.

| Charge | Nœuds avant | Nœuds après | Octets avant | Octets après |
|---|---:|---:|---:|---:|
| H06, ordre simulé | 1 271 133 | 63 381 | 15 654 910 | 742 080 |
| H08, ordre simulé | 1 331 827 | 70 567 | 16 397 708 | 824 184 |

La limite reste **1 048 576 nœuds par événement**. Les charges avant correction
échouent au contrôle de structure ; les deux suivantes passent. L'identité de
tous les champs de source hors `block.page`, les effectifs de blocs et la base
avant/après sont vérifiés. Ce contrôle établit un mécanisme reproductible
compatible avec les erreurs observées. Il ne prouve pas leur classement exact
ni la réussite du prochain passage natif.

`source_page_geometry` expose les dimensions, boîtes, rotation, orientation,
index de page et marqueurs simples de provenance nécessaires à la localisation.
Quand des diagnostics supplémentaires existent, `stored_geometry_sha256`
identifie le JSON exact enregistré. Les tableaux de diagnostics OCR, régions
et couverture restent dans la base complète et dans l'accès de page ; ils ne
sont plus dupliqués avec chaque fragment. Aucun diagnostic n'est effacé de la
base. Le hash est un lien d'identité, jamais une preuve suffisante : qualité,
géométrie et conditions restent revalidées depuis les enregistrements complets.

Les anciens cadres ne contenant que les champs de localisation gardent leur
forme. Les textes, offsets, hashes de blocs et boîtes de fragments sont conservés.
Les valeurs invalides des champs retenus ne sont pas réparées silencieusement.
Les plafonds logiques, physiques et mémoire de trace restent identiques.

Un test reproduit l'échec avec 128 fragments d'une page contenant des diagnostics
volumineux. Les quatre cas dédiés donnent **1 échec / 3 réussites avant** ; le
groupe ciblé après correction donne **142 réussites**, dont ces quatre cas, avec
écriture et relecture réelles de trace. Le classement et la base utilisés dans
ces tests restent des doubles explicites ; aucune fidélité native n'en découle.

## Réserve attachée à un sujet répété

La revue Office de phase 6 détecte une régression L13 : la réponse conserve la
négation du nombre mais omet la phrase suivante, qui précise que le courant de
sortie n'est pas établi par le document. L'extrait original et S001 contiennent
bien les deux phrases. Les liaisons de source sont intactes ; le contrôle du
contenu publié est néanmoins incomplet. Le résultat de phase 6 reste **FAIL**.

L'enveloppe littérale conserve désormais une phrase suivante lorsque son sujet
nominal est explicitement répété et que son prédicat porte une négation ou une
restriction reconnue. La comparaison normalise uniquement casse et espaces ;
elle n'assimile pas deux composants, propriétés ou conditions. La reconnaissance
du sujet est bornée à 160 caractères. Une autre phrase, une autre propriété ou
un changement de paragraphe interrompt ce rattachement. Les connecteurs explicites
déjà pris en charge conservent leur comportement.

La restriction est publiée avec ses caractères et offsets originaux. Elle ne
devient ni une nouvelle valeur ni une paraphrase générée. Une affirmation suivie
d'une réserve négative ne peut pas servir de donnée positivement établie. Les
tests couvrent la publication complète, les citations, les offsets, la négation,
le français et l'anglais, les sujets concurrents et les limites de sélection.

Les 19 nouveaux cas donnent **9 échecs / 10 réussites avant**. Le groupe après
une première correction donne **113 réussites**, dont ces 19 cas. La revue
indépendante trouve ensuite un contre-exemple : une réserve à TA = 85 °C ne
doit pas invalider la valeur établie à TA = 25 °C. Un sujet identique peut aussi
porter deux composants distincts nommés dans les prédicats. Les douze cas ajoutés
portent le groupe dédié à **3 échecs / 28 réussites** avant raffinement.

La grammaire de points déjà utilisée par le contrat est déplacée sans changement
dans `point_conditions.py` et partagée avec l'enveloppe. L'identité de sa fonction
et de son expression régulière est vérifiée par AST contre l'instantané 6. Une
négation simple, explicitement limitée à un unique point final, peut être écartée
si ce point porte la même grandeur et le même symbole mais une valeur différente
après conversion décimale exacte. Les points équivalents en °C/K, les symboles
différents, les plages, alternatives, réserves globales et mots exclusifs comme
`only` ou `except` n'autorisent pas cette exclusion. Une négation limitée à un
autre composant explicitement nommé suit la même règle étroite. Il ne s'agit
pas d'une résolution générale des références en langue naturelle.

Le groupe après raffinement donne **214 réussites**, dont les 31 cas dédiés.
Une invocation intermédiaire avec un chemin de test inexistant est conservée
comme erreur de commande sans test exécuté. Ruff et Mypy passent sur les sources
concernées. Cela ne remplace ni le suivi Office natif ni les portes logicielles
complètes.

## Pièces de contrôle

Les reçus privés conservent les hashes des sources et journaux, les comparaisons
avant/après et les limites du contrôle :

- `source-boundaries-followup-review-1.json` : regroupement, sans moteur natif ;
- `source-boundaries-followup-review-2.json` : contre-exemples de condition et
  contexte nommé, partage exact du lecteur de points et raffinement ;
- `page-trace-frame-ablation-baseline.json` et
  `page-trace-frame-ablation-projected.json` : charge et identité des fragments ;
- `source-page-frame-before.log` et `source-page-frame-after-1.log` ;
- `repeated-subject-limits-before-1.log` et
  `repeated-subject-limits-after-1.log` ;
- `ingestion-source-geometry-review-r02.json` : revue indépendante du helper et
  de ses raccords API ; aucune réussite native n'en est déduite.

Les résultats natifs de phase 6 restent dans le
[bilan de développement](trust-4b-development-review-2026-11-09.md) et la
[revue Office](trust-4b-api-office-review-2026-11-09.md). Les critères de réception
du [protocole](trust-4b-protocol-2026-11-08.md) ne sont pas modifiés.
