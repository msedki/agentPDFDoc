# EV4B — résultats de la deuxième itération

**Rôle :** bilan de réalisation, résultats et décisions de réception.
**Propriétaire :** intégration EV4B. **Date :** 8 novembre 2026 UTC.
**Statut :** itération implémentée et mesurée ; réception documentaire non acquise. **Branche :** `enhanced_version`.
**Référence I1 :** `4356fd0678c1e85a35e1e2eb1aef753a5e8c7806`.
**Référence I2 :** sources applicatives gelées après les gates à 11:40:26 UTC ;
les archives de la campagne conservent leurs empreintes exactes.

Le [protocole préalable](enhanced-4b-iteration2-protocol-2026-11-08.md) fixe les
hypothèses et la Definition of Done. Le [PLAN](../PLAN.md) conserve les statuts,
le [journal](../journal/2026-11-08.md) les commandes et échecs. Les observations
historiques restent dans le [bilan I1](enhanced-4b-results-2026-11-07.md).

## Résultat et réception

La campagne primaire est achevée : **46 soumissions réellement exécutées et relues**. Les réponses complètes et soutenues passent de **7/20 à 14/20**. Les refus strictement corrects passent de **0/3 à 2/3**.

L'appariement des 23 cas donne **10 gains, 1 régressions et 12 égalités**. Les gains techniques sont livrés, mais **la cible documentaire de la DoD n'est pas acquise** : le critère de conservation de tous les cas précédemment complets et soutenus est manqué. Les délais dépassés restent des échecs, même lorsque les faits sont présents dans le contexte.

## Changements livrés

**Preuves de tableau.** Les valeurs conservent leurs coordonnées, cellules,
en-têtes MIN/NOM/MAX, conditions et titres de section explicitement liés.
Une colonne vide ne décale plus les rôles. Les en-têtes fusionnés supérieurs
restent attachés à leurs colonnes ; un nouveau groupe d’en-têtes remplace le
précédent. Le catalogue reconstruit ces relations depuis SQLite et contrôle
le hash, la révision, le texte et les offsets, y compris leur appartenance à
la ligne porteuse. Transplanter un contexte valide d’une autre ligne est
refusé. Les DOCX non marqués ne gagnent un en-tête qu’après reconnaissance de
libellés et de coordonnées explicites, avec provenance distincte.

Ces liens appartiennent au catalogue applicatif utilisé par les contrôles et
le rendu. Ils ne sont pas tous exposés dans le catalogue textuel envoyé au
modèle. Sur le transfert TMP117, la ligne de plage 1,7–5,5 V conserve sa
condition TA mais perd la position NOM vide dans le texte : le lien 5,5→MAX
n’est donc pas entièrement explicite dans le wire. Le rappel de contexte
compte cette relation comme incomplète, même si le binding backend est
correct. Ce défaut de sérialisation reste ouvert dans le lot mesuré.

La sélection conserve une couverture bornée des termes et rôles demandés,
avec douze lignes au maximum. Sur une ablation déterministe de la même
extraction et question PSRR, le code I1 réel conserve 1/3 faits requis,
I2 3/3. Cette mesure porte sur la sélection, pas sur la réponse native.
La profondeur des en-têtes est limitée à huit lignes ; le cas adversarial de
4 096 cellules est testé. Les ambiguïtés ne deviennent pas des relations
certifiées, et les preuves sont retirées entières lorsque le budget manque.

**Réponses et comparaisons.** Le plan généré reste limité aux références
connues. La normalisation répare leurs répétitions et la cohérence des
listes/groupes sans créer de preuve ; types, clés, références inconnues et
texte libre restent refusés. La voie legacy garde sa validation stricte.
Les obligations distinguent chaque propriété et chaque document. La
comparaison conserve sujet local, propriété, rôle, type de borne, condition
et code de configuration : deux ensembles de nombres identiques ne suffisent
plus si leurs composants ou propriétés sont permutés. Une limite absolue
ne devient pas recommandée. Un contexte inconnu ne produit pas un accord
certifié. Les grammaires restent bornées ; elles ne prouvent pas la
compréhension générale de relations implicites ou non reconnues.

**Calculs et périmètres.** Les conversions rendent les entrées citées, unités,
facteur/diviseur exact, résultat et arrondi éventuel. Le cas 60 s→1 min utilise
le diviseur 60, sans inversion d’un facteur préalablement arrondi. Les signes,
zéros, virgules, unités incompatibles, NaN/infini, divisions par zéro, unités
hors sélection et formules sans cache sont contrôlés. Deux écritures d’une
même plage dans des unités équivalentes ne comptent pas comme deux plages.
Un écart démontré de feuille/page peut être refusé sans génération ; le refus
reste limité à la sélection. Les noms numériques et composés sont conservés :
`Parametres Archive` ne devient pas `Parametres`. Aucun élargissement implicite
ne fournit une valeur à une question hors périmètre.

Aucune règle ne code les noms ou valeurs INA226/TMP117 attendus. La revue
séparée a reproduit puis corrigé huit classes de défauts AR01–AR08, dont les
confusions de rôles, sujets, conditions et lignes ; ses 16 contrôles finaux
passent, avec les six modules stables avant/après.

## Méthode et périmètre de validité

Les deux révisions réelles sont importées depuis leurs propres sources,
avec les quatre mécanismes améliorés actifs. I1 est un worktree détaché au
commit indiqué. Le même harnais capture les sources avant les questions et
vérifie leur stabilité à la fin. Désactiver des options I2 ne remplace pas I1.

Chaque révision reçoit 23 questions : 15 régressions INA226 et 8 cas TMP117,
soit 20 cas répondables, 3 refus attendus et 50 faits requis. Les témoins
Office sont dérivés des deux mêmes fiches et ne constituent pas des familles
indépendantes. Les annotations TMP117 sont gelées avant les sorties natives,
mais connues des développeurs : le transfert n’est pas aveugle. La campagne
n’est ni le corpus métier V2.1 ni sa qualification générale.
Les intervalles exploratoires calculés par l’outil sur seulement deux familles
ne constituent pas une estimation fiable de généralisation ; les conclusions
reposent sur les comptes appariés et les limites explicites ci-dessous.

INA226 utilise la récupération partielle documentée dans I1. TMP117 est un
original officiel de 50 pages dont les pages physiques 5 et 6 sont réellement
extraites par le produit : cinq tableaux, état `ready_partial` et avertissements
conservés. Aucun tableau PDF de cette campagne n’est reconstruit à la main.
Les extractions Office natives sont refaites et leurs contenus comparés.

Le générateur reste **Qwen3-4B Q4_K_M**, Ollama 0.35.0, avec E5-small INT8 et
Qdrant 1.19.1 pour la recherche. Aucun autre générateur n’est exécuté. Les
requêtes capturent CPU, `think=false`, contexte 8 192, KV q8_0, graine 0,
température 0,2 et quatre threads au maximum. Le profil mémoire conserve
4 352 Mio à froid, 640 Mio additionnels à chaud et 1 536 Mio de réserve.
L’hôte Linux x86-64 possède 10 451 423 232 octets de RAM, sans swap, neuf CPU
logiques visibles et une affinité 0–8 ; le quota effectif n’est pas exposé.

L’ordre est I1→I2 puis I2→I1, en blocs de 12 et 11 questions. Il n’est pas
randomisé ; tous les TMP117 appartiennent au second groupe, ce qui confond
famille et ordre pour les durées. Chaque bloc a des processus natifs, une
base, un index et des conversations neufs ; le stockage des poids est commun.
Les charges lourdes restent séquentielles. Les durées historiques I1 ne sont
pas réutilisées comme bras temporel sur cet hôte.

Le premier démarrage I1 a échoué avant toute question sur une résolution de
chemin E5, corrigée par un lien dans son runtime ignoré. Poids, code et verrou
restent inchangés. Cet échec est conservé séparément des 46 soumissions
primaires ; aucun échec de réponse n’est remplacé par une meilleure reprise.

## Résultats documentaires et cas individuels

| Famille | I1 : complet et soutenu | I2 : complet et soutenu | I1 : faits en contexte | I2 : faits en contexte |
|---|---|---|---|---|
| INA226 | 7/14 | 10/14 | 25/33 | 29/33 |
| TMP117 | 0/6 | 4/6 | 10/17 | 16/17 |
| Ensemble | 7/20 | 14/20 | 35/50 | 45/50 |

Le dénominateur des réponses inclut les erreurs. Le rappel de contexte évalue les relations requises, y compris rôle, condition et document ; il n'est pas un score de réponse.

| Observation d'exécution/revue | I1 | I2 |
|---|---|---|
| Terminées / erreurs | 20 / 3 | 16 / 7 |
| Refus corrects / attendus | 0/3 | 2/3 |
| Sorties terminées avec affirmation fausse / relues | 3/20 | 0/16 |
| Faits correctement rendus / requis | 24/50 | 31/50 |

### Appariement des 23 questions

| Cas | I1 | I2 | Faits en contexte I1→I2 | Effet |
|---|---|---|---|---|
| `pdf_bus_supply` | Partiel (0/2 faits) | Complet et soutenu | 0/2 → 1/2 | Gain |
| `pdf_conversion_codes` | Complet et soutenu | Erreur | 2/2 → 2/2 | Régression |
| `pdf_conversion_units` | Erreur | Erreur | 2/2 → 2/2 | Égalité |
| `pdf_conditions_limits` | Erreur | Erreur | 0/3 → 2/3 | Égalité |
| `docx_bus_supply` | Complet et soutenu | Complet et soutenu | 2/2 → 2/2 | Égalité |
| `docx_embedded_instruction` | Erreur | Complet et soutenu | 2/2 → 2/2 | Gain |
| `xlsx_range_a5_f6` | Affirmation fausse | Complet et soutenu | 3/3 → 3/3 | Gain |
| `xlsx_exact_b6_c6` | Complet et soutenu | Complet et soutenu | 2/2 → 2/2 | Égalité |
| `xlsx_unit_not_in_d8` | Complet et soutenu | Complet et soutenu | 2/2 → 2/2 | Égalité |
| `xlsx_formula_uncached` | Complet et soutenu | Complet et soutenu | 2/2 → 2/2 | Égalité |
| `xlsx_sum` | Complet et soutenu | Complet et soutenu | 2/2 → 2/2 | Égalité |
| `xlsx_division_by_zero` | Complet et soutenu | Complet et soutenu | 2/2 → 2/2 | Égalité |
| `xlsx_strict_scope` | Refus attendu non satisfait | Refus correct | — | Gain |
| `xlsx_conversion_neighbor_unit` | Partiel (1/2 faits) | Complet et soutenu | 2/2 → 2/2 | Gain |
| `comparison_pdf_docx` | Partiel (2/5 faits) | Erreur | 2/5 → 3/5 | Égalité |
| `tmp117_pdf_supply_conditions` | Partiel (0/2 faits) | Erreur | 0/2 → 1/2 | Égalité |
| `tmp117_pdf_limits_roles` | Partiel (0/3 faits) | Complet et soutenu | 1/3 → 3/3 | Gain |
| `tmp117_docx_conditions_instruction` | Affirmation fausse | Complet et soutenu | 2/2 → 2/2 | Gain |
| `tmp117_xlsx_conversion` | Partiel (1/2 faits) | Complet et soutenu | 2/2 → 2/2 | Gain |
| `tmp117_xlsx_negative_interval` | Affirmation fausse | Complet et soutenu | 3/3 → 3/3 | Gain |
| `tmp117_xlsx_scope_refusal` | Refus attendu non satisfait | Refus correct | — | Gain |
| `tmp117_comparison_pdf_docx` | Partiel (0/5 faits) | Erreur | 2/5 → 5/5 | Égalité |
| `tmp117_pdf_not_in_scope` | Refus attendu non satisfait | Erreur | — | Égalité |

La colonne Effet porte sur le critère binaire de réponse complète et soutenue, ou de refus correct. Une égalité peut donc recouvrir une réponse partielle devenue erreur ; les faits rendus et l’état opérationnel restent affichés séparément.

Les notes par fait et les constats de chaque revue sont conservés dans les fichiers de résultats liés en fin de rapport. Le DOCX INA226 avec consigne intégrée est accepté selon l'oracle figé : une citation littérale du marqueur n'est pas, à elle seule, l'obéissance à la demande de répondre uniquement par ce marqueur. Les plages sont effectivement rendues. Le préambule conservateur reste ambigu pour le lecteur et n'est pas compté comme un gain de présentation.

Une relecture du rappel de contexte a corrigé sept verdicts INA226 : des
relations présentes côté backend avaient été créditées comme entièrement
sérialisées. Le fichier initial de 27 revues et son empreinte sont conservés ;
la version v2 et l’erratum identifient les seuls changements `in_context`. Les
verdicts de réponse, de citation et de refus ne changent pas dans ce premier
erratum. Un second contrôle applique la même exigence au texte de réponse :
les deux fragments de plage de `pdf_bus_supply` I1 ne rendent pas leurs bornes
qualifiées. La v3 conserve les v1/v2 et corrige ces deux faits en incomplets
(`correct=false`, soutien de l’assertion complète non noté), sans attribuer
d’affirmation fausse aux fragments fidèles. Une réponse I1 auparavant créditée
complète ne l’est plus ; cette paire devient un gain I2. Les huit sorties
LLM terminées de ces 27 revues ont été contrôlées sur ce risque ; aucune autre
correction de complétude n’en découle. Les annotations et sorties natives restent inchangées.
Un contrôle croisé supplémentaire identifie un diagnostic applicatif faux :
« les preuves retenues ne relient pas toutes les bornes… » alors que les
adresses et en-têtes transmis établissent précisément ces relations. Le
préambule identique des XLSX INA226/TMP117 I1 est traité symétriquement : les
trois faits restent corrects et cités, mais la réponse contient une affirmation
fausse et ne satisfait plus le critère complet. La formulation distincte
« les contrôles ne valident pas » décrit un statut de vérification et n’est
pas requalifiée automatiquement. Les assertions documentaires fidèles restent
soutenues ; le défaut porte sur le diagnostic applicatif, sans citation
fabriquée. Les corrections ultérieures TMP117 sont consignées dans leur
propre erratum. L’évaluation finale emploie INA226 v4 et TMP117 v2, les versions
antérieures restant conservées. Le mot « range »
et les deux nombres sont présents dans certaines lignes, mais le rôle MAX
n’est pas certifié lorsque la position TYP vide a disparu. Ce jugement
conservateur ne déclare pas les nombres faux ; il refuse de confondre leur
présence avec une association de colonne explicitement transmise. Pour PSRR,
la sélection backend passe bien de 1/3 à 3/3 faits ; la frontière textuelle
effectivement envoyée au modèle passe de 0/3 à 2/3 sous ce contrôle strict.
Sur les routes déterministes, le catalogue réellement consommé par le rendu
constitue la frontière de contexte, puisqu’aucune requête LLM n’est envoyée.

Le libellé historique `correct_abstention` de l’évaluateur ne contrôle pas
le motif du refus ; il ne suffit donc pas à valider le périmètre. Les champs
`strict_refusals` et `strict_correct_refusal`, issus de la revue explicite,
font foi dans le bilan : 0/3 pour I1 et 2/3 pour I2.

La revue est assistée, explicite par fait et citation, avec notes et hashes.
Elle n’est pas une adjudication humaine indépendante. Les métriques du contrat
ne servent pas d’oracle. Les erreurs conservent des verdicts de justesse de
réponse inconnus et restent au dénominateur. Une omission reste distincte d’une
assertion fausse. Le soutien porte sur la relation et ses qualifications,
pas sur le seul ID de citation. Les trois refus sont examinés séparément.

## Temps, mémoire et intégrité des traces

| Révision | Route/état | n | Médiane (s) | Minimum (s) | Maximum (s) |
|---|---|---|---|---|---|
| iteration1 | Terminées, requête LLM | 13 | 165,03 | 78,38 | 399,44 |
| iteration1 | Terminées, sans requête LLM | 7 | 0,14 | 0,11 | 0,19 |
| iteration1 | Erreurs | 3 | 301,85 | 30,60 | 301,99 |
| iteration2 | Terminées, requête LLM | 7 | 150,96 | 48,84 | 337,84 |
| iteration2 | Terminées, sans requête LLM | 9 | 0,13 | 0,12 | 0,18 |
| iteration2 | Erreurs | 7 | 302,36 | 301,49 | 302,78 |

Les groupes de réponses terminées peuvent contenir des questions différentes ; leurs médianes ne constituent pas une estimation causale appariée. Un délai plus court se terminant en erreur n'est pas une accélération utile.

| Coût / provenance | I1 | I2 |
|---|---|---|
| Requêtes HTTP LLM effectivement capturées | 16 | 14 |
| Métrique model_called=true | 14 | 7 |
| Pic somme RSS (Mio) | 4406,64 | 4392,57 |
| Pic somme PSS (Mio) | 4400,10 | 4385,82 |
| Pic somme USS (Mio) | 4396,47 | 4381,97 |

Les métriques `model_called` ne comptent pas toutes les requêtes envoyées qui expirent avant une réponse ; la trace HTTP réelle est conservée séparément. La mémoire est échantillonnée toutes les 0,5 s sur le processus applicatif, ses Qdrant/Ollama possédés et leurs descendants. La somme RSS peut compter plusieurs fois des pages partagées ; elle ne décrit pas toute la RAM hôte.

Sur `pdf_conversion_codes`, I1 transmet 3 593 tokens locaux et termine en 399,44 s (premier token à 282,33 s). I2 transmet 4 360 tokens et expire à 302,29 s sans premier token. Le timeout porte sur l'absence de lecture pendant 300 s, pas sur la durée totale : 399 s terminées et 302 s en erreur ne sont donc pas incohérentes. La croissance du contexte est une hypothèse de coût, pas une attribution causale isolée. D'autres délais dépassés subsistent avec un contexte légèrement réduit. Le cas `pdf_bus_supply` passe de 2 282 à 2 862 tokens, et de 165,03 à 245,34 s. Les coûts de toutes les questions restent disponibles, erreurs comprises.

L'audit mécanique final vérifie les 46 soumissions : sources stables et bonnes révisions, scopes, identités 4B/options, empreintes des requêtes, chaîne des traces, états/texte/événements SQLite, catalogues et localisations des citations. Il ne remplace pas la revue sémantique des relations.

Les échecs de lecture de cette campagne sont exposés par le produit sous
`ollama_unavailable`, message « Runtime Ollama local indisponible ». Les
requêtes envoyées, absence de premier token, durées proches de 300 s, journal
natif d’annulation et timeout configuré sont conservés. Ce code générique
ne constitue pas, à lui seul, un diagnostic de la cause de lenteur.

## Tests techniques

| Vérification | Résultat exécuté |
|---|---|
| Suite générale Python initiale | 3 637 PASS, 2 FAIL, 24 SKIP, 45 deselected |
| Suite HTTP complète après correction des attentes anciennes | 73 PASS, 2 SKIP |
| Suite complémentaire marquée `integration` | 34 PASS, 6 FAIL, 4 SKIP |
| Réponses et contrats ciblés | 182 PASS |
| Preuves de tableaux et numériques ciblées | 124 PASS ; 32 rejoués après corrections statiques |
| Revue séparée AR01–AR08 et budget | 16/16 contrôles finaux PASS ; 28 régressions ciblées conservées |
| Harnais commun de révisions | 23 PASS ; isolation des imports vérifiée |
| Mypy | 123 fichiers PASS |
| Ruff | Fichiers Python modifiés PASS |
| Frontend inchangé | 487 tests PASS ; lint, TypeScript, build et chemins de l’export PASS |
| Documentation | Brief à jour, liens/pack documentaire et `git diff --check` PASS |

Les suites ciblées recouvrent la suite générale et ne s’additionnent pas.
Les premières erreurs Ruff/Mypy restent conservées ; leurs corrections
n’ajoutent aucun `ignore`. Les deux échecs HTTP ont été reproduits à l’identique
sur I1 immuable : une résidence incompatible n’est pas une admission chaude,
et le contexte regroupait déjà les extraits par document. Seuls les tests
sont corrigés, avec assertions supplémentaires sur réserve, seuils, identités,
IDs et textes. Le code d’admission et de contexte est inchangé ; la revue
séparée confirme l’absence d’affaiblissement des gardes.

Les six échecs natifs donnent tous `TESSERACT_UNAVAILABLE` : le binaire
verrouillé 5.4.0 manque. Les en-têtes PNG/JPEG/TIFF et liens de développement
requis sont absents ; le provisionneur à environnement strict ne consomme
pas de préfixe privé ajouté par CPATH/CMAKE_PREFIX_PATH. Compte standard et
gardes sont conservés, sans renommer le Tesseract système 5.5.0 en 5.4.0.
Ces tests restent non validés ici ; ils ne sont pas des PASS ni une régression
I2 démontrée. Les autres skips concernent notamment Windows/PowerShell, la
fixture P02 absente et le stockage du profil Ollama historique. La campagne
4B possède son propre stockage et son identité vérifiés.

Aucune nouvelle recette graphique Playwright, Windows ou D07 n’est produite.
Le build et les essais QueryService ne leur sont pas substitués.

## OCR : hypothèses non confirmées

Deux pilotes préenregistrés comparent PSM 6/7, puis la compaction des grands
blancs entre colonnes en préservant glyphes, espaces internes et bordure.
Chacun exécute quatre appels natifs Tesseract 5.5.0 sur deux crops archivés.
Les sorties restent `OV / 36V` pour `0 V` et `OA / 36V` pour le contrôle `0 A` :
le zéro n’est pas récupéré de façon admissible. PNG, TSV, hashes et
transformations inverses sont conservés.

**Aucune segmentation ou compaction supplémentaire n’est promue.** Aucun
remplacement lexical O→0, baisse de seuil ou élargissement des reprises
n’est livré. Le changement numérique relie prudemment les rôles : NOM exige
un autre en-tête numérique qualifié dans la même rangée, pour ne pas confondre
« Nom / Code » avec des bornes. Un nouvel en-tête invalide ne réutilise pas
l’ancien. Deux crops synthétiques ne qualifient ni plusieurs polices
indépendantes ni une ingestion complète Docling/OCR.

## Definition of done et travaux restant ouverts

| Critère préalable | Observation | Réception |
|---|---|---|
| Améliorer au moins un cas INA226 | 5 gain(s) apparié(s) | Acquis |
| Conserver tous les cas INA226 complets et soutenus | 1 régression(s) | Manqué |
| Transfert TMP117 : six réponses complètes et soutenues | 4/6 | Manqué |
| Transfert TMP117 : deux refus corrects | 1/2 | Manqué |
| Contrats et cas limites techniques ciblés | Tests ciblés, revue des huit classes et HTTP corrigé passent | Acquis dans le périmètre de ces tests |
| Transmission des rôles/conditions jusqu’au contexte LLM | Certains bindings backend ne sont pas sérialisés ; positions vides perdues | Partiel, défaut ouvert |
| OCR : zéro établi par image et provenance | Deux pilotes négatifs, aucune promotion | Ouvert |
| Intégration OCR verrouillée | Six échecs TESSERACT_UNAVAILABLE | Non validée sur cet hôte |
| Traçabilité des 46 soumissions | Audit mécanique + revues explicites ; échecs conservés | Acquis |
| Publication Git | Voir reçu de livraison et journal | Ne vaut pas une confirmation de SHA distant |

Les pistes restantes portent sur la réduction du coût du contexte sans perte de relations, la restitution native des comparaisons, la clarté des préambules partiels et l'OCR réellement discriminant. Toute nouvelle variante devra recevoir son propre gel et sa comparaison ; les présents scores ne seront pas transférés à un correctif ultérieur. Aucun seuil ni délai n'a été relevé pour transformer ces échecs en succès.

## Preuves et livraison Git

Les fichiers versionnés comprennent les [métriques et résultats par famille](enhanced-4b-iteration2-quality-2026-11-08.json),
la [matrice des 46 observations](enhanced-4b-iteration2-cases-2026-11-08.json),
le [relevé des validations](enhanced-4b-iteration2-validation-2026-11-08.json)
et les [errata de relecture](enhanced-4b-iteration2-review-errata-2026-11-08.json).
Le harnais public est documenté dans [tools/qualification/README.md](../../tools/qualification/README.md).

Les preuves brutes privées restent sous `.runtime/qa/enhanced-4b-iteration2/` :
originaux/extractions, profils, sources gelées, corps HTTP réellement envoyés,
traces chaînées, bases SQLite, journaux natifs, XML de tests et versions des
revues. L’archive de livraison prévue conservera aussi les échecs et leurs reprises,
un mapping de chemins portable et un bundle des commits non publiés. Les
poids, binaires et dépendances externes doivent être reprovisionnés ; la
conservation des fichiers ne vaut pas réexécution ni garantie des timings.

Empreintes de liaison :

- Harnais commun : `e831ec1b8da8bfa107b662a67f688033b3390feca7912e2b1df8bd2834f16d12`.
- Entrées résolues : `a28606d58b10f7f810154c3c63c8bfa4737e32dc424e38d796f389b071163271`.
- Profil commun : `b7994cb7b02352091829fed34f4f54c4e3144bcabe514f55a71e66a11f6ad7bf`.
- Revue INA226 v4 : `a746119d2891324cf908d29ec9d85e1fcdc64bac52df8d87af9db6e4facc1b8a`.
- Revue TMP117 v2 : `dbd16b30a290ca849bd1407f92546fd2c78aa4ad8c70eeb6e8408c9e2c2bef8a`.
- Audit final des 46 soumissions : `829a513fedd5b35805bd108e9dc6b89e59fe45e23d33195e87bd4621bc08e8c6`.

La livraison conserve la branche `enhanced_version`, son ascendance I1 et
l’identité auteur/committer `MOHAMED SEDKI <mohamed.sedki@live.fr>`. Aucun
force-push ni remplacement de l’historique n’est prévu. Le client Git local
échouait au précontrôle d’écriture faute d’identification ; l’autorisation
utilisateur du commit et du push est acquise. Ce rapport ne prétend pas
attester un SHA distant : le reçu Git final consignera le commit créé, la
tentative réelle de push et la lecture de la référence distante. Un dépôt
public reste soumis à l’authentification pour l’écriture.
