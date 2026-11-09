# I5 — revue des deux passages de la suite portable

**Statut :** résultats exécutés, relus le 8 novembre 2026. **Périmètre :** JUnit, journaux, inventaire des cas et changements des tests ; aucune nouvelle exécution dans cette revue. **Responsabilité :** rôle validation distinct du rôle ayant exécuté les commandes, mais coauteur de certaines fixtures ; cette revue n'est donc pas un audit aveugle. Révision Git de départ : `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, modifications I5 non encore commitées lors des essais.

## Résultat constaté

Le second portable passe intégralement dans le périmètre sélectionné : **4 704 PASS, 25 SKIP, 45 désélectionnés**, aucun échec ni erreur de préparation. Il conserve les mêmes 25 entrées ignorées et leurs mêmes motifs que le premier passage. Aucun cas précédemment réussi n'est devenu ignoré.

| Mesure | Premier portable candidat | Second portable candidat |
|---|---:|---:|
| Réussites | 4 006 | 4 704 |
| Cas FAILED (assertion ou exception) | 190 | 0 |
| Erreurs de préparation/exécution | 298 | 0 |
| Entrées ignorées dans JUnit | 25 | 25 |
| Cas désélectionnés par marqueurs | 45 | 45 |
| Avertissements | 1 | 1 |
| Durée affichée par pytest | 339,39 s | 416,45 s |

Ces deux passages sont deux états du **candidat I5**, pas une comparaison expérimentale entre la pipeline I4 et I5. Le second contient 210 entrées JUnit de plus : 223 nouveaux identifiants et 13 identifiants remplacés ou reparamétrés. Leurs durées et le nombre de tests réussis ne mesurent ni la qualité RAG, ni la fidélité des réponses, ni la latence du modèle.

La sélection reste `not acceptance and not slow and not integration`, avec des répertoires temporaires distincts hors dépôt. Les commandes exactes figurent dans le [guide de reproduction](trust-4b-reproduce-2026-11-08.md). Certains tests API placés dans `tests/integration` sans marqueur `integration` appartiennent ainsi au portable ; le nom du dossier ne suffit pas à qualifier un test de natif.

## Résolution du premier passage rouge

Les JUnit partagent 4 506 identifiants. **475 des 488 entrées initialement FAIL/ERROR passent sous exactement le même identifiant.** Les 13 restantes sont toutes reliées ci-dessous à des remplacements présents et réussis dans le second JUnit. Aucun premier échec n'a été supprimé des journaux.

Abréviations des fichiers : **LI** = `tests/unit/test_dist_linux_install.py`, **LK** = `tests/unit/test_dist_linux_kit.py`, **PS** = `tests/unit/test_runtime_launcher_ps1.py`. Les paramètres omis du nom de fonction dans une cellule sont indiqués explicitement dans la même cellule.

| Nº | Ancien cas | Remplacement exécuté | Garantie conservée ou nouveau contrat explicite |
|---:|---|---|---|
| 1 | LI `test_each_kit_file_is_read_once_during_install` | `test_payload_files_are_read_once_and_selection_metadata_reads_are_bounded` | Charge utile toujours lue une seule fois ; jusqu'à trois lectures des trois fichiers de sélection vérifiés, chacune bornée. |
| 2 | LI `test_new_install_preserves_same_selection_in_profile_report_and_pointer`, RAM 16 Gio, choix automatique 2B | `test_historical_archive_reader_preserves_selection_in_profile_report_and_pointer`, mêmes paramètres | Maintenance d'une archive synthétique explicite ; vrais lecteur, sélecteur et écrivain de profil hors ligne. |
| 3 | Même fonction LI, RAM 16 Gio, choix manuel ancien 4B | Même fonction de lecture d'archive, mêmes paramètres | Conservation du choix manuel, du profil, du rapport et du pointeur. |
| 4 | Même fonction LI, RAM inconnue, repli ancien 4B | Même fonction de lecture d'archive, mêmes paramètres | Conservation du repli historique dans le lecteur d'archives. |
| 5 | LI `test_state_is_translated`, état running et identité `qwen3.5:4b` | Même fonction, identité `qwen3-4b-enhanced:q4km` | Traduction de l'état avec l'identité réellement livrée. |
| 6 | LI `test_uninstall_stops_this_version_removes_it_without_following_links_and_keeps_the_data` | Même fonction, variantes `enhanced` et `historical-archive` | Un seul arrêt de l'instance possédée ; liens non suivis, fichiers extérieurs et données conservés ; un ou deux profils selon l'archive. |
| 7 | LK `test_absolute_outgoing_or_dangling_links_stop_the_build`, lien sortant sous `.runtime/models/e5/model.onnx` | Même fonction, lien sortant sous `.runtime/models/e5-small-int8/linked.onnx` | Le lien est placé dans l'arbre E5 effectivement sélectionné, pour exercer le refus du constructeur. |
| 8 | LK `test_build_kit_models_option_defaults_to_both_and_refuses_the_2b_alone` | `test_build_kit_models_option_defaults_to_enhanced_and_refuses_2b` | Le défaut de construction et l'option explicite respectent le générateur renforcé unique. |
| 9 | LK `test_catalogue_can_add_delivered_manual_model_set_without_qualifying_it` | `test_current_builder_refuses_a_second_declared_generator_even_if_not_selected`, deux variantes | Un second générateur déclaré est refusé, sélectionné ou non, avant création du kit. |
| 10 | LK `test_models_4b_alone_drops_the_2b_blobs_manifest_and_tokenizer` | `test_nominal_and_explicit_4b_drop_all_historical_generator_weights_and_tokenizers` | Construction nominale et 4B explicite excluent les poids et tokenizers des anciens générateurs. |
| 11 | LK `test_the_default_kit_ships_both_models_and_requires_the_4b` | `test_the_default_kit_ships_only_the_enhanced_4b_and_refuses_2b` | Kit renforcé unique et refus explicite du 2B. |
| 12 | PS `test_rag_ps1_model_omits_the_default_profile_and_reaches_the_cli`, modèle 2B | Cas nominal renforcé de la même fonction, plus `test_rag_ps1_transmits_but_cli_refuses_a_legacy_model_before_start[qwen3.5:2b]` | L'argument atteint la CLI ; l'ancien modèle est refusé avant le démarrage. |
| 13 | Même fonction PS, ancien modèle 4B | Cas nominal renforcé, plus `test_rag_ps1_transmits_but_cli_refuses_a_legacy_model_before_start[qwen3.5:4b]` | Le modèle renforcé est admis ; l'ancien profil sans contrôles renforcés est refusé. |

Le changement de contrat des lignes 8 à 13 est fixé dans l'[addendum des points d'entrée](trust-4b-entrypoints-addendum-2026-11-08.md), avant ces essais. Les tests PS interprètent les arguments du script et appellent la vraie CLI avec un démarrage doublé ; ils ne constituent pas une exécution de PowerShell.

## Revue des assertions et des fixtures

Les assertions ne sont **pas toutes identiques** à la révision de départ. Les changements intentionnels suivants ont été examinés :

- Les fabriques nominales utilisent un profil enhanced valide, un catalogue unique et de petits blobs dont les empreintes correspondent aux octets. Les gardes du constructeur ne sont pas neutralisées. Les archives historiques sont reconstruites explicitement pour les seuls scénarios de maintenance et relues par le vrai `verify_kit`.
- Les contrôles d'intégrité, de refus avant écriture, de ports, de sauvegarde, de liens, d'arrêt et de données conservées restent actifs. Les scénarios à deux profils historiques restent distincts des nouveaux kits à un seul profil.
- Le contrôle des lectures autorise désormais jusqu'à trois accès pour `model_profiles.py`, `model_profiles.json` et `models.lock.json`, en raison de leur vérification avant copie. Les autres plafonds antérieurs restent bornés et toute charge utile doit encore être lue au moins une fois. Ce changement est déclaré, sans le présenter comme une égalité des assertions antérieures.
- Les tests de budgets continuent à lire les profils historiques hors ligne ; le profil actif enhanced passe par la garde réelle. Les assertions de réserve, de plafond et de statut incomplet restent en place.
- Les positifs de tableaux ont reçu une géométrie synthétique explicite, requise par la revalidation des liaisons. Les injections de coordonnées ou rôles erronés restent négatives. Ces témoins ne prétendent pas provenir d'une extraction native.
- Les tests de frontière du générateur qui seraient désormais court-circuités par une réponse déterministe forcent explicitement la route du sélecteur par un double nommé. Ils vérifient d'abord que le catalogue est étayé et non vide, puis conservent les contrôles de publication, d'admission, d'arrêt et de libération. Leur portée est celle d'une frontière contrôlée.
- Les anciens doubles OCR fournissent les deux lectures de vérification supplémentaires, déclarées sans corroboration. Les assertions d'incertitude, de limites d'appels et de pixels, de provenance et d'absence de fuite sont conservées ou renforcées.

Une inspection des ajouts du diff des tests suivis par Git n'a trouvé ni nouveau `skip`/`xfail`, ni assertion triviale `assert True`/`assert 1`. L'inventaire AST des assertions a été conservé à titre de contrôle de cohérence ; un nombre d'assertions ne prouve pas leur force. La revue s'appuie également sur les scénarios, leurs résultats et les remplacements explicités ci-dessus.

Cette inspection compare les sources courantes à Git HEAD, et les résultats des deux passages entre eux. Elle ne certifie pas l'identité octet par octet de l'ensemble des sources de tests au début des deux exécutions : aucun instantané complet de ces sources n'a été récupéré pour cette revue. Elle ne transforme donc pas les adaptations décrites en « assertions inchangées ».

## Les 25 entrées ignorées

Les identifiants, messages et détails JUnit sont identiques entre les deux passages.

| Motif | Entrées | Portée non démontrée |
|---|---:|---|
| Windows, jonctions, Job Object, installateur/raccourcis/désinstallation PowerShell 5.1, lecture Win32 | 12 | Comportements réels propres à Windows ; comprend une entrée de module ignoré à la collecte. |
| Exécutable PowerShell absent | 10 | Analyse syntaxique réelle des scripts et certains rendus de diagnostic PowerShell. |
| Ancienne extraction de référence P02 absente | 1 | Ce témoin historique précis de propagation de provenance OCR jusqu'aux citations API. |
| Ancien magasin Qwen3.5-4B dérivé absent | 1 | Conformité de ce magasin historique au verrou ; ce motif ne décrit pas le modèle natif Qwen3-4B renforcé provisionné. |
| Chaîne de compilation C native incomplète | 1 | Reconstruction réelle CMake/make et élimination des chemins absolus de fabrication. |

Les 45 désélections conservent les marqueurs exclus. Elles ne sont ni des réussites ni des régressions nouvellement masquées. Les huit essais OCR natifs, les intégrations séparées, le complément de six parcours formatter et les quinze contre-tests de son lecteur ont leurs propres reçus ; leurs nombres ne sont pas additionnés ici pour gonfler le portable.

L'avertissement présent dans les deux journaux vient de `fastapi.testclient` : Starlette annonce la dépréciation de son utilisation d'`httpx`. Aucun changement de dépendance n'est déduit de ce seul avertissement.

## Preuves et limites de la conclusion

Les journaux et JUnit sont conservés localement sous `.runtime/qa/production-i5-20261108/`. Le reçu détaillé `portable-independent-review-receipt.json` contient l'inventaire, les 13 correspondances vérifiées et les motifs d'exclusion ; SHA-256 `fbe3c1f72b748bff13fb08f874b0e28895db574f6c6c9bf2cae4e6069c52f951`.

| Preuve | SHA-256 |
|---|---|
| `portable-candidate-1.xml` | `ceb255c89232c33e54d246b90e048bb79f0f5fef48311c0e521f07472ca5d5dd` |
| `portable-candidate-1.log` | `fb57cfe342f89a08ee494b25519e68deebe31e408da4b450a639204342f93ce7` |
| `portable-candidate-2.xml` | `f27dd88ba619e61e43fe4f1691920695590a5c07a93c878bbbe16928d1e5ead9` |
| `portable-candidate-2.log` | `4bbf9d487007e029655c910ec59ba23b2fa3c64a4905cd85ded4831fdd6c334d` |

La porte portable sélectionnée est verte. Elle ne démontre pas à elle seule une installation native neuve, les plateformes ignorées, l'inférence réelle 4B, la fidélité à des PDF originaux ou la généralisation au corpus réservé. Les critères de réception restent ceux du [protocole I5](trust-4b-protocol-2026-11-08.md) et des essais distincts effectivement exécutés.
