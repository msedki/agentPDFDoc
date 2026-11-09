# I5 — complément contrôlé de la frontière du générateur

**Statut :** six parcours exécutés et relus le 8 novembre 2026 ; aucun appel modèle réel. **Responsabilité :** exécution par le rôle principal, relecture des rapports et des bases par le rôle validation, auteur du vérificateur. Cette séparation n'est pas un audit aveugle. **Périmètre :** plan valide, ajout de prose dans le plan, référence inconnue ; même document, même question et mêmes conditions d'exécution dans deux révisions applicatives distinctes.

## Conclusion bornée

Les **trois cas passent dans la référence I4 et les trois dans le candidat I5 snapshot 4**. Chaque cas a effectivement appelé une fois le double du sélecteur, avec un catalogue non vide. Le plan valide rend l'extrait avec sa réserve ; les deux plans invalides produisent une erreur contrôlée, sans réponse publiée ni message assistant persistant.

Ce complément démontre les six frontières exercées. Il ne relève pas le résultat historique du candidat sur les trente cas primaires : **12/12 positifs et 16/18 contrôles** restent inchangés. Les deux échecs L11/L12 de la [revue primaire](trust-4b-controlled-review-2026-11-08.md) n'avaient pas appelé le sélecteur et ne sont pas reclassés après coup. Le supplément ne mesure pas l'inférence 4B, le RAG natif ni une qualité sémantique générale.

## Protocole fixé avant les requêtes

La [fixture versionnée](../../tests/fixtures/trust_i5_formatter_boundaries.json) est gelée à `2026-11-08T22:26:34.852787+00:00`, SHA-256 `e721fef074f76fd70f86bc71b7808a984c0c8f0bc241b5dc22e376e98de236e5`. Elle dérive le document et la question de L01 : le document établit **10 mA à TA = 25 °C**, tandis que la question demande le courant à **85 °C**. La source ne justifie pas cette transposition.

Les trois variantes ne changent que le mode de `ControlledSelectorDouble` : sélection autorisée `R001`, ajout du champ de prose interdit, puis sélection d'une référence inexistante. Les cas manquants, erreurs et dépassements de durée restent au dénominateur de six. Le témoin valide est une restitution prudente d'une information partielle ; il ne compte pas comme une réponse complète au courant à 85 °C.

Le harnais `grounded_campaign.py` est inchangé, SHA-256 `a9ff2e5470a6fda376623b68c88ff804da8185b8ce3cc5b48ab691af2f258237`. Les deux bras partagent le profil enhanced SHA-256 `092da8f90103654027cee93ce0edcc9a312f45b70078047cfe4c1eeebdcf5716`, Python 3.12.14, les mêmes versions de bibliothèques, le même ordre et les mêmes doubles. Le profil désigne exclusivement le générateur Qwen3-4B renforcé, mais son moteur n'est pas lancé dans cette expérience.

Office, SQLite, FTS et QueryService sont réels. `ConstantEmbeddingDouble`, `LexicalOnlyVectorDouble`, `ControlledSelectorDouble` et `CharacterCounterDouble` remplacent explicitement embeddings, vecteurs, sélecteur et comptage de tokens. Ollama, E5, Qdrant, ingestion PDF, OCR, HTTP, navigateur et gouverneur de ressources ne sont pas exercés par ces six requêtes.

## Résultats des six parcours

| Bras | Cas | Appels / entrées du catalogue | Terminal | Deltas publics | Citations finales | Messages assistant persistants |
|---|---|---:|---|---:|---:|---:|
| Référence I4 | F01, plan valide | 1 / 1 | `done`, réponse partielle avec réserve | 1 | 1 | 1 |
| Référence I4 | F02, champ de prose ajouté | 1 / 1 | `structured_answer_invalid` | 0 | 0 | 0 |
| Référence I4 | F03, référence inconnue | 1 / 1 | `structured_answer_invalid` | 0 | 0 | 0 |
| Candidat I5 snapshot 4 | F01, plan valide | 1 / 1 | `done`, réponse partielle avec réserve | 1 | 1 | 1 |
| Candidat I5 snapshot 4 | F02, champ de prose ajouté | 1 / 1 | `structured_answer_invalid` | 0 | 0 | 0 |
| Candidat I5 snapshot 4 | F03, référence inconnue | 1 / 1 | `structured_answer_invalid` | 0 | 0 | 0 |

Les deux réponses F01 sont identiques octet par octet. Elles signalent que les conditions demandées ne sont pas établies et conservent le passage avec ses 25 °C. Aucun courant à 85 °C n'est affirmé. Les citations portent le document, sa version réellement importée et son élément DOCX ; aucune page inexistante n'est inventée.

Les quatre erreurs sont terminales, avec un seul appel : aucune reprise du modèle ne masque le premier rejet. La prose inventée et la référence inconnue n'apparaissent ni dans les deltas publics, ni dans la réponse, ni dans les messages assistant ou sources servables conservées. Les plans rejetés restent dans les événements d'audit internes. Le filtre de la route SSE excluant `structured_delta` et `structured_answer` a été relu dans `services/api/main.py` ; aucune requête HTTP supplémentaire n'a été exécutée pour cette revue.

Les durées de requête contrôlée ont pour médiane 107,59 ms dans la référence et 115,07 ms dans le candidat, avec respectivement 121,13 et 164,65 ms au maximum. Chaque bras ne contient que trois cas et aucun moteur modèle : ces chiffres ne démontrent pas une variation de performance de l'inférence.

## Racines, provenance et persistance relues

Les applications sont deux racines distinctes : le checkout de référence `agentPDFDoc-i5-baseline` et l'instantané isolé `agentPDFDoc-i5-diagnostic-snapshot-4`. Leur `git_head` est le même commit de départ, ce qui ne suffit pas à les distinguer avant commit. La relecture s'appuie donc sur les manifestes réels de **76 fichiers Python de services dans la référence et 82 dans le candidat**, différents et conformes aux fichiers présents. Les deux campagnes déclarent zéro source modifiée pendant leur exécution.

La revue indépendante a aussi constaté six identifiants de requête différents, six fichiers SQLite distincts et six DOCX originaux identiques, SHA-256 `398a72104746614b27b5eb49fb2db9c799ba57a4a397578cf6948a1f71bab866`. Elle a relu le XML de chaque DOCX et les tables SQLite en `mode=ro` avec `query_only=ON`, sans importer le produit ni relancer le vérificateur.

Les questions, états, réponses, événements, nombres de messages et identités de document/version ont été recoupés. Les blocs sources, leurs empreintes, offsets, révisions d'extraction, générations d'index et localisateurs ont été vérifiés contre les données stockées et les originaux. Les fichiers SQLite gardent la même empreinte avant et après cette lecture.

**Distinction entre source d'audit et citation finale :** la table SQLite nommée `citations` conserve un passage réel `S001` dans chacun des six cas, car les sources récupérées sont préparées avant génération. Dans les quatre rejets, le terminal contient zéro citation finale, la réponse est vide et aucun message assistant n'est enregistré. La conservation du passage justificatif réel n'est pas la publication d'une réponse fabriquée.

La première lecture auxiliaire avait supposé à tort qu'un rejet impliquait zéro ligne dans cette table SQLite. Cette assertion a échoué et son reçu est conservé. Le lecteur auxiliaire a été corrigé pour vérifier la légitimité des sources stockées et compter séparément les citations finales. Les oracles gelés exigeaient déjà zéro citation **terminale** et zéro message assistant ; ils n'imposaient pas d'effacer les sources d'audit. Aucun produit, oracle, résultat ou seuil n'a changé, et les six requêtes n'ont pas été rejouées.

## Contrôle du vérificateur

Une revue statique avant les essais a fermé les risques de compter deux fois le même bras et de se fier à des résumés incohérents avec les événements. Le [vérificateur](../../tools/qualification/verify_formatter_boundaries.py) exige des chemins résolus distincts, des manifestes conformes, un catalogue effectivement transmis, un appel unique, le code du terminal, les vrais deltas et la persistance SQLite. Un rapport incomplet ne retire pas de cas du dénominateur.

Ses [quinze contre-tests](../../tests/unit/test_i5_formatter_boundaries.py) passent en 0,32 s. Ils utilisent des rapports explicitement synthétiques et de vraies bases SQLite ; ils ne sont ni quinze requêtes supplémentaires ni une mesure native. Ils couvrent notamment la réutilisation de bras et les alias, un arbre source modifié, un code terminal contradictoire, un delta caché dans le résumé, du texte dans un terminal d'erreur, une mauvaise question, un message assistant indu et un cas manquant.

## Reproduction et reçus

Les trois commandes ci-dessous ont été exécutées séquentiellement depuis la racine du dépôt. Utiliser des dossiers neufs pour une reproduction ; les cibles originales doivent être conservées.

```sh
.venv/bin/python tools/qualification/grounded_campaign.py --application-root ../agentPDFDoc-i5-baseline --profile ../agentPDFDoc-i5-baseline/config/enhanced-4b.yaml --fixtures tests/fixtures/trust_i5_formatter_boundaries.json --work-dir .runtime/qa/production-i5-20261108/formatter-baseline --output .runtime/qa/production-i5-20261108/formatter-baseline.json
.venv/bin/python tools/qualification/grounded_campaign.py --application-root ../agentPDFDoc-i5-diagnostic-snapshot-4 --profile ../agentPDFDoc-i5-diagnostic-snapshot-4/config/enhanced-4b.yaml --fixtures tests/fixtures/trust_i5_formatter_boundaries.json --work-dir .runtime/qa/production-i5-20261108/formatter-candidate --output .runtime/qa/production-i5-20261108/formatter-candidate.json
.venv/bin/python tools/qualification/verify_formatter_boundaries.py --fixtures tests/fixtures/trust_i5_formatter_boundaries.json --baseline-report .runtime/qa/production-i5-20261108/formatter-baseline.json --baseline-work-dir .runtime/qa/production-i5-20261108/formatter-baseline --baseline-application-root ../agentPDFDoc-i5-baseline --candidate-report .runtime/qa/production-i5-20261108/formatter-candidate.json --candidate-work-dir .runtime/qa/production-i5-20261108/formatter-candidate --candidate-application-root ../agentPDFDoc-i5-diagnostic-snapshot-4 --output .runtime/qa/production-i5-20261108/formatter-boundary-verification.json
```

Le reçu d'orchestration `followup-gates-and-formatter-1.json` conserve arguments absolus, débuts/fins UTC et codes de sortie. Les deux bras se déroulent entre 23:10:31 et 23:10:36 UTC ; le vérificateur termine avec le code 0. Les fichiers bruts restent locaux, sans exposition des journaux privés dans le dépôt.

| Preuve | SHA-256 |
|---|---|
| Rapport référence | `497d5b3820d046a2f93bf38efb7f62431381b760461533ed37bb7a08da10f24f` |
| Rapport candidat | `e2921178caee92387772a9e0fde161759b22d89c4122401aa0775f9762bc3c36` |
| Vérification des six parcours | `e3e059e1000a7ee73799e7277e64aaa3e63e789b4e8f152d15317d6e9ba4e8cd` |
| Revue indépendante des sorties | `ea67406d00154d666791015437a29297f7a55e38ac952d7f7ed1452032945815` |
| Première erreur auxiliaire de lecture | `b3ea3750bac1ee2c5b0033e16b72ceb7bb311f3aece941ee31259a2c919b1d47` |
| Code du vérificateur | `aa4ddf1cf0a5863505f85f85f30a88b7b248908bd879bcc7e3d704d39f3c6e2e` |
| JUnit des quinze contre-tests | `91c04aca9b148c5a124515aa68bec66e3896cbac9e0a0de54c2ef3785fecc33f` |

La frontière contrôlée est démontrée pour ces six cas. La qualification de l'application de confiance reste conditionnée aux autres portes, aux requêtes natives, au transfert réservé et aux limites de déploiement déclarées dans le bilan global.
