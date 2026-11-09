# I5 — Observations de ressources et de réponses, phase 4A

**Ces huit observations ne qualifient pas la génération 4B ni une diffusion en production.** Elles comprennent cinq erreurs d’admission mémoire avant tout appel au modèle. Dans le bras candidat, une autre question répondable reçoit une abstention évitable ; le cas limite n’extrapole pas, mais sa justification demeure incomplète. Seul H04 satisfait les besoins documentaires demandés dans ce sous-ensemble, avec un défaut typographique de l’extraction conservé ci-dessous.

Relecture achevée le `2026-11-08T23:50:24.012011+00:00`. Elle porte sur les résultats primaires de H01–H04, déjà publics et consommés en I4. Le corpus réservé I5 reste fermé. Le relecteur est distinct de l’exécuteur de ces essais et auteur de harnais et de tests du dépôt ; cette revue n’est ni aveugle ni un audit externe.

## 1. Périmètre et identités

Le protocole de la phase 4 prévoit20 questions par bras. Ce reçu couvre seulement les quatre premières, soit trois positifs et un cas limite par bras. Il ne crédite aucun résultat aux16 autres questions de chaque bras. Les erreurs et abstentions restent dans leur dénominateur initial. Les critères sont ceux de [l’oracle public I4](production-i4-corpus/questions-oracles.json) et du plan de revue gelé avant lecture des sorties ; aucune réponse, extraction, règle d’acceptation ou donnée attendue n’a été modifiée ici.

| Élément | Référence |
| --- | --- |
| Référence produit | Commit `41857e17a438fe43123e4ef8274d9d2d446bfbc2` |
| Candidat | Instantané de diagnostic 4, distinct d’un gel final de livraison |
| Reçu de l’instantané | SHA256 `c393b906bf5bed33afb7be9ba9337c6b002928910930f99202f653275d0f4822` |
| Plan natif de phase 4 | SHA256 `f1bbaaf19e1c614228c12e7b15cb20a2a79b7dd7e1286b8293cae0fc9037ad15` |
| Générateur configuré dans les deux bras | `qwen3-4b-enhanced:q4km`, Qwen3–4B, Q4_K_M, CPU, `think=false` |
| Inférence déclarée | Contexte 8192, sortie 1536, température 0,2, top-p 0,9, seed 0 ; **aucun appel effectif** |
| Période candidat | `2026-11-08T23:20:55.872635+00:00` à `2026-11-08T23:23:51.290839+00:00` |
| Période référence | `2026-11-08T23:23:51.296369+00:00` à `2026-11-08T23:32:41.730587+00:00` |

Les manifestes portent les mêmes SHA256 des trois PDF originaux, les mêmes questions et les mêmes périmètres. Les extractions diffèrent, comme prévu : la référence réutilise les extractions I4 du produit correspondant, avec Tesseract corrigé ; le candidat utilise les extractions fraîches de l’instantané4. Les mesures historiques d’extraction ne sont donc pas présentées comme une nouvelle mesure de latence de la référence. Les deux manifestes de code diffèrent et leurs reçus de stabilité indiquent chacun une liste vide de fichiers modifiés pendant le bloc.

Ollama, Qdrant, le tokenizer, E5 et le stockage de cette campagne sont réels. Le transport est l’appel direct du service applicatif, sans nouveau test HTTP ni navigateur. `model_called=false` dans les huit mesures et les deux journaux Ollama ne contiennent aucune requête `/api/chat` ou `/api/generate`. Démarrer les services et indexer des documents ne constitue pas une génération 4B. Les deux reçus d’arrêt confirment que leurs groupes possédés sont vides et leurs processus réapés ; le code retour 0 du harnais indique une campagne terminée, pas huit réponses réussies.

## 2. Les huit observations conservées

La colonne de mémoire reproduit la valeur arrondie au point de décision d’admission. Le seuil est **5888 Mio**, composé d’un pic froid prévu de 4352 Mio et d’une réserve de 1536 Mio. Le minimum du moniteur mémoire est une autre observation, à un autre instant ; les deux valeurs ne sont pas interchangeables.

| Bras | Cas | Besoin | Latence observée, s | Mémoire disponible à l’admission, Mio | Résultat observé | Succès strict |
| --- | --- | --- | ---: | ---: | --- | --- |
| baseline | H01 | Positif, spécifications et conditions | 122.31 | 3566 | Erreur mémoire avant génération | FAIL |
| baseline | H02 | Positif, circuits devenus inutiles | 127.47 | 3451 | Erreur mémoire avant génération | FAIL |
| baseline | H03 | Limite, sortie à 150 °C | 125.22 | 3077 | Erreur mémoire avant génération | FAIL |
| baseline | H04 | Positif, plages de fonctionnement | 126.52 | 3068 | Erreur mémoire avant génération | FAIL |
| candidate | H01 | Positif, spécifications et conditions | 126.04 | 3552 | Erreur mémoire avant génération | FAIL |
| candidate | H02 | Positif, circuits devenus inutiles | 6.04 | Sans admission générateur | Abstention évitable sur un positif | FAIL |
| candidate | H03 | Limite, sortie à 150 °C | 1.75 | Sans admission générateur | Non-extrapolation pertinente ; justification incomplète | FAIL |
| candidate | H04 | Positif, plages de fonctionnement | 2.76 | Sans admission générateur | Deux plages étayées ; défaut typographique signalé | PASS |

Les quatre erreurs de la référence et H01 candidat retournent `resource_admission_denied`. Il ne s’agit ni d’une réponse documentaire prudente, ni d’une panne du fournisseur, ni d’un dépassement de la limite du harnais. Aucune réponse finale, aucun message assistant et aucune citation de réponse finale ne sont enregistrés pour ces cinq cas. Ils échouent à la validation fonctionnelle, y compris H03 de la référence, qui était un cas limite.

Ces refus ont pris environ 122 à 127 secondes. Cette durée décrit le parcours d’attente et d’admission observé ; elle ne mesure pas une génération 4B. Les minima de mémoire disponible échantillonnés vont d’environ2826 à 3310 Mio et les pics RSS agrégés d’environ870 à 1255 Mio. Ils couvrent les processus suivis du parcours sans inférence, pas la consommation mémoire d’un 4B chargé.

## 3. Utilité, limites et preuves effectivement publiées

### H02 candidat : abstention évitable

La réponse expose une limite de l’analyse littérale, sans prétendre que l’information manque dans le document. Ce choix de formulation évite une fausse conclusion sur la source. Il ne satisfait toutefois pas la question : le passage complet qui énumère les trois circuits devenus inutiles était disponible. La fiche de revue H02 relie l’échec au filtre littéral du qualificatif «externe», qui refuse la clause source malgré sa quantification explicite.

Ce cas demeure un échec sur un positif répondable, avec abstention totale. Il ne publie aucun fait documentaire ni aucune citation finale : les métriques de fidélité des faits et de précision des citations y sont **non applicables**, jamais 100 %. La présence de six sources récupérées et conservées pour l’audit ne remplace pas une réponse.

### H03 candidat : non-extrapolation correcte, justification incomplète

La réponse indique que la valeur n’est pas établie dans les conditions demandées et refuse de transposer une valeur issue d’autres conditions. Elle n’invente aucun résultat à 150 °C et n’étend aucune garantie : le contrôle de non-extrapolation est satisfait et l’abstention est pertinente.

Le critère gelé exige aussi de conserver les limites de la plage. L’original publié s’arrête à 100 °C ; la réponse ne rappelle pas cette borne et ne fournit pas le passage justificatif. **Le succès strict reste donc faux**, contrairement au seul contrôle de non-extrapolation. La distinction a été recoupée avec le relecteur du contrat de preuve en utilisant le même oracle public, sans changement de seuil. La précision de citations est non applicable, car il n’y a aucun marqueur ni citation finale.

### H04 candidat : réponse documentée, avec une imperfection de transcription

Les deux besoins sont couverts sur la première page d’AD22105 : alimentation simple de 2,7 à 7,0 V et température de fonctionnement de −40 à +150 °C. Le signe négatif et le mode d’alimentation sont conservés. Les informations supplémentaires incluses dans les trois extraits — caractéristiques de précision, hystérésis, dissipation et résistance de programmation — apparaissent aussi sur la page ; elles n’ont pas été assimilées aux plages demandées.

La revue a recoupé les trois occurrences de citation avec leurs **deux sources distinctes**. Pour chaque extrait, document, version, génération, révision d’extraction, page, identifiant de bloc, hash du texte et offsets correspondent aux enregistrements SQLite. Les trois sous-chaînes sont exactes par rapport au texte extrait. Le SHA du PDF original, le SHA du contenu canonique de l’extraction et les trois hashes de blocs ont été vérifiés séparément. Les deux bases SQLite ont conservé le même SHA256 avant et après la relecture.

La première citation finit cependant par `7.0 V, V`, tandis que la page originale ne porte qu’un seul `V`. Ce doublon vient du texte natif extrait et est reproduit par la reconstruction déterministe. Il ne change pas la valeur ni la condition, mais empêche de revendiquer une transcription littérale parfaite de l’original. Les plages et les autres informations des extraits ont été contrôlées sur l’image historique de la page, sans nouveau rendu. Le tableau suivant distingue ces propriétés.

| Propriété H04 | Observation |
| --- | --- |
| Besoins demandés complets | 2 groupes sur 2 |
| Passages documentaires publiés | 3, tous soutenus quant au sens et aux conditions |
| Occurrences de marqueurs | 3 sur 3 rattachées aux sous-chaînes annoncées |
| Sources finales distinctes | 2 sur 2 de la page et de la version attendues |
| Transcription typographique parfaite de l’original | Non : duplication d’une unité dans le premier extrait |
| Calcul ou extrapolation ajouté | Aucun |
| Appel au générateur | Aucun, route `deterministic_evidence_contract` |

Le warning d’extraction partielle est conservé comme signal d’exploitation. Il n’est pas présenté comme une preuve que les deux plages citées manquent ou sont incertaines : leur support a été vérifié séparément sur la page originale.

## 4. Dénominateurs et absence de conclusion causale

| Mesure sur ce sous-ensemble | Référence | Candidat |
| --- | ---: | ---: |
| Positifs complets | 0/3 | 1/3 |
| Cas limites strictement complets | 0/1 | 0/1 |
| Erreurs techniques | 4/4 | 1/4 |
| Abstentions totales évitables sur positifs | 0/3 — les trois sont en erreur technique | 1/3 |
| Contrôle de non-extrapolation effectivement publié sur le cas limite | Non exécuté jusqu’à une réponse | Satisfait, justification incomplète |
| Appels 4B | 0 | 0 |
| Citations finales uniques / occurrences | 0/0, précision N/A | 2 sources / 3 occurrences, toutes contrôlées sur H04 |

La baisse apparente des erreurs dans le bras candidat s’accompagne de routes déterministes, d’une abstention excessive et d’une limitation incomplète. Elle ne prouve ni un gain général de qualité, ni une meilleure performance du 4B. Une moyenne de latence sur ces routes différentes serait trompeuse. Les températures, quantification et autres paramètres du générateur n’ont pas été évalués expérimentalement par ces huit observations puisqu’aucune génération n’a démarré.

## 5. Préservation des preuves et reprise distincte

Le diagnostic d’environnement a identifié des résultats de tests et des archives de dépendances conservés sur un montage tmpfs. Leur préservation puis leur déplacement vers du disque a été décidée pour rétablir les conditions d’admission. Le script autorisé est figé au SHA256 `f473de4069ab25ae87c908ca83eac018267f638b93e7ed5241dc6b27a30c03f9`.

Cette opération conserve les fichiers originaux jusqu’à la comparaison des inventaires de contenu et de métadonnées, préserve les liens symboliques et les groupes de liens physiques internes, puis conserve les anciens chemins sous forme de liens. Son résultat doit être établi par un **reçu opératoire séparé**. La présente revue ne lit pas l’opération en cours et ne revendique donc ni migration terminée, ni quantité de mémoire récupérée.

La reprise prévue est une phase 5 explicitement distincte, avec les mêmes données et limites, un contrôle préalable de mémoire disponible d’au moins 6,5 Gio et le seuil produit de5888 Mio conservé. Une admission rendue possible après déplacement des fichiers sera un changement d’environnement, pas une amélioration de consommation mémoire attribuable au code. Les erreurs de phase 4 demeurent dans l’historique ; la reprise ne les remplace pas.

## 6. Reproduction de la relecture et limites

Le reçu détaillé `development-phase4-review.json`, conservé avec les preuves QA, contient les huit mesures, leur SHA, les états et textes terminaux, les dénominateurs, la chaîne de provenance H04 et les hashes des bases avant/après. Son SHA256 est `a277e91ab154caac4bcbf2613b89782545f7f95f805a00152bd3a92128478476`. Les fichiers de mesure sont conservés dans leurs dossiers de campagne respectifs ; ils ne sont pas exposés comme des journaux publics contenant les originaux ou les chemins de l’environnement.

La relecture est reproductible sans moteur : comparer les états, questions et réponses de `query_runs` en SQLite `mode=ro` avec les mesures ; reconstituer les deltas publics ; distinguer les sources enregistrées de `done.citations` ; vérifier les sous-chaînes et hashes des blocs puis les liens document/version/révision/génération. Les images déjà conservées ont les SHA256 `0a9034dc2f8fb8a73def553d3ee663edf1d55fdc7f4dcbe97efebff30d7c44e9` pour AD22103 p2 et `2c83457fe1df455fef4d7eab1e89fdb334e1db2c59570d53d516494ee80aabe5` pour AD22105 p1.

Une assertion auxiliaire de cette relecture comparait initialement, à tort, le hash du contenu canonique de l’extraction au SHA des octets PDF. Elle a été corrigée après lecture du contrat existant : `extraction_revisions.source_hash` porte sur pages/sections/tableaux, tandis que `document_versions.sha256` porte sur le fichier original. Les deux vérifications distinctes concordent. De même, l’empreinte canonique de la table des identités de code est recalculée séparément du SHA des octets du fichier manifeste ; les deux archives de code correspondent à leurs reçus. Cette erreur du relecteur n’a modifié aucun résultat de campagne, oracle, produit ou harnais et n’a entraîné aucune nouvelle requête.

| Mesure primaire conservée | SHA256 |
| --- | --- |
| `H01-baseline-0.json` | `763bc240c0f5fcd10341749c2b197e576589c783399bf10db817d9f8d83d9cf7` |
| `H02-baseline-0.json` | `6ec520ed88ca7219524b89bce5822808f21c0ba631ca6ab1a23689fe3fd8a090` |
| `H03-baseline-0.json` | `19be5faf3272359d6c0aff9437638dfaf53a2721630abc4fb21e7d6bf161b3a3` |
| `H04-baseline-0.json` | `32c92aa92a19e3526d4393d1ba286e5356e1c362dd5d0d8f340e89cd5d87e323` |
| `H01-candidate-0.json` | `66ed58b0cef1a5144fe82b0186683bfbeae710a5473c62b3cf8feceef083344f` |
| `H02-candidate-0.json` | `6909ba2aa065acd3d539ee075f522bf348ca78adf82ecfef3b7547abc8a46abb` |
| `H03-candidate-0.json` | `0788f13238cd7bd8acfc384ad6ec8475416dbc10c5817a4e0fb3413bd681b294` |
| `H04-candidate-0.json` | `08a3241f06c14da06bcd004740d67affd196177748825602d8b2c883c11cb585` |

**Restent à démontrer :** le comportement 4B après admission sur des conditions explicites, la résolution des besoins manquants H01/H02 et de la justification H03, le reste des20 questions de développement, puis la qualification réservée selon son gel propre. Les tests portables, les compléments contrôlés et les vérifications frontend sont décrits séparément dans [la revue des tests](trust-4b-test-review-2026-11-08.md), [le complément de frontière du formateur](trust-4b-formatter-boundaries-2026-11-08.md) et [la synthèse JSON](trust-4b-validation-2026-11-08.json) ; ils ne sont pas additionnés aux huit observations de ce reçu.
