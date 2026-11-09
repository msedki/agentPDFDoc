# I5-PJ — fondement scientifique des contrôles de preuve

**Rôle :** justification des hypothèses et des essais de la reprise I5 demandée avec la pièce jointe · **Propriétaire :** qualification documentaire · **Statut :** Vivant, références vérifiées ; essais DEV/FINAL exécutés, critères finaux non satisfaits · **Référence :** `fe4693da07ed9e948f65e4cadb51cd43ec36ebe2`, branche `enhanced_version` · **Mis à jour :** 2026-11-09 (UTC) · **Source de vérité :** ce rapport pour l'analyse bibliographique ; [protocole I5-PJ](trust-i5-pj-protocol-2026-11-09.md) pour les critères ; [résultats locaux](trust-i5-pj-results-2026-11-09.md) et [revue indépendante](trust-i5-pj-review-2026-11-09.md) pour les observations

## Question et périmètre

Deux défauts ont été reproduits lors de la reprise : une relation `< 3.3 V`
traitée comme une égalité, conduisant à une concordance injustifiée ; une clause
`unless TA=25°C` considérée comme un appui pour une réponse à `TA=25°C`, alors
que cette condition est exclue. Le protocole conserve les cas et leur état de
référence. Le présent rapport explique pourquoi la présence du nombre, de
l'unité et d'une citation ne suffit pas à valider ces réponses.

Les publications ci-dessous ont été ouvertes sur les sites des auteurs ou des
organismes de publication le 9 novembre 2026. Les résultats chiffrés sont ceux
des articles. Ils ne mesurent ni agentPDFDoc, ni son Qwen3-4B Q4_K_M, ni le
poste cible. Aucun modèle, poids ou composant supplémentaire n'est adopté par
cette étude. Les règles déterministes proposées sont des choix d'ingénierie
à éprouver ; elles ne sont pas présentées comme des algorithmes validés par ces
articles.

## Publications examinées

### S01 — ALCE, EMNLP 2023, publication évaluée par les pairs

[Gao et al., article et PDF officiels](https://aclanthology.org/2023.emnlp-main.398/),
§2–3 et §5 ; [code des auteurs](https://github.com/princeton-nlp/ALCE).

**Tâche et protocole.** Générer des réponses avec citations sur 1 000 questions
de chacun des jeux ASQA, QAMPARI et ELI5, à partir de Wikipedia ou Sphere.
Comparaisons de modèles OpenAI et de familles LLaMA/Vicuna, avec variations de
récupération et de contexte. **Mesures.** Fluidité, couverture des réponses,
précision et rappel des citations ; le support est estimé par TRUE, un modèle
NLI T5-11B, puis confronté à des jugements humains. **Résultat.** Sur ELI5,
environ la moitié des générations ChatGPT/GPT-4 étudiées ne sont pas entièrement
appuyées par leurs citations. **Limite et transfert.** La qualité d'une citation
diffère de sa présence. Le juge et les corpus ne qualifient pas notre 4B.
L'essai local doit distinguer référence valide, extrait présent, relation
correcte et complétude de la réponse.

### S02 — RAGTruth, ACL 2024, publication évaluée par les pairs

[Niu et al., article et PDF officiels](https://aclanthology.org/2024.acl-long.585/),
§3–5 ; [données des auteurs](https://github.com/ParticleMedia/RAGTruth).

**Tâche et corpus.** Détection d'hallucinations dans 17 790 réponses issues de
2 965 entrées : questions MS MARCO, données structurées vers texte et résumés
d'actualités. Six générateurs : GPT-3.5, GPT-4, Mistral-7B et Llama-2-7B/13B/70B.
**Protocole et mesures.** Deux annotations indépendantes par réponse, arbitrage
si nécessaire ; évaluation aux niveaux réponse et segment, avec précision,
rappel et F1. Quatre catégories séparent contradiction et information ajoutée,
chacune évidente ou subtile. **Résultat.** Un Llama-2-13B ajusté obtient une
détection compétitive avec les approches par prompt GPT-4 étudiées.
**Limite et transfert.** Données et modèles distincts du français technique
local. L'article classe expressément l'interprétation `null` comme `false`
parmi les hallucinations. Il justifie des annotations séparées des relations,
conditions et informations absentes, sans confondre égalité des nombres et
fidélité du sens.

### S03 — Searching for Best Practices in RAG, EMNLP 2024, publication évaluée par les pairs

[Wang et al., article et PDF officiels](https://aclanthology.org/2024.emnlp-main.981/),
§3–5, tableau 1 et annexes A.3/A.7 ;
[code des auteurs](https://github.com/FudanDNN-NLP/RAG).

**Protocole.** Comparaisons successives de composants, puis de quelques
combinaisons, sans recherche exhaustive. Retrieval sur TREC DL 2019/2020 ;
génération sur QA générale, multihop et spécialisée, avec notamment
Llama3-8B-Instruct. **Mesures.** mAP, nDCG, rappel, EM/F1, métriques RAG et
latence. **Résultat.** Dans la configuration du tableau 1, hybride + HyDE
atteint un score RAG de 0,580 à 11,71 s/question ; hybride seul, 0,498 à
1,45 s. L'ordre, le reclassement et la compression ont aussi des effets.
**Limite et transfert.** Les auteurs excluent l'optimalité universelle.
Comparer lexical, dense, hybride et reclassement à corpus constant est
pertinent ; leurs réglages ne sont pas transposés au 4B. Une amélioration du
retrieval ne corrige pas, à elle seule, une mauvaise interprétation d'un
opérateur ou d'une exception. HyDE n'est pas ajouté sans bénéfice local mesuré.

### S04 — Sufficient Context, ICLR 2025, publication évaluée par les pairs

[Fiche officielle Google Research](https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems-2/),
[texte intégral v3, §3–5](https://arxiv.org/html/2411.06037v3).

**Tâche.** Distinguer contexte insuffisant et mauvaise utilisation d'un
contexte suffisant. **Protocole.** Qualification sur 115 exemples annotés ;
étude sur FreshQA, MuSiQue-Ans et HotpotQA, principalement avec 6 000 tokens
de contexte. Modèles propriétaires et familles Llama, Mistral, Gemma ; juges
Gemini 1.5 Pro, FLAMe-24B et TRUE-NLI-11B. **Mesures et résultats.** Le juge
Gemini one-shot atteint 93 % d'exactitude sur les 115 exemples. La génération
sélective améliore de 2–10 % la fraction de réponses correctes parmi les
réponses produites, selon les configurations. **Limite et transfert.** Une
affirmation impliquée n'établit pas la suffisance pour toute la question.
Le protocole local doit mesurer ensemble couverture, complétude et
abstentions. Leurs juges, leur raisonnement et leurs seuils ne sont pas
importés : notre politique interdit de compléter les sources par les
connaissances internes du générateur.

### S05 — GaRAGe, Findings ACL 2025, publication évaluée par les pairs

[Sorodoc et al., article et PDF officiels](https://aclanthology.org/2025.findings-acl.875/),
§2–4 ; [données des auteurs](https://github.com/amazon-science/GaRAGe).

**Corpus et protocole.** 2 366 questions, plus de 35 000 passages annotés ;
pertinence et actualité des preuves, connaissances publiques et collections
représentant des sources privées. 427 questions demandent une déflexion.
Même prompt et décodage glouton pour GPT-4o, Gemini, Claude, Nova,
Mistral/Mixtral et Qwen2.5. **Mesures.** Adéquation de la réponse, factualité
restreinte aux preuves pertinentes, attribution et déflexion ; GPT-4o est
principalement utilisé comme juge. **Résultats.** Maximum annoncé d'environ
60 % de factualité tenant compte de la pertinence, 58,9 % de F1 d'attribution
et 31,1 % des déflexions requises correctement détectées. **Limite et
transfert.** Jugement automatique et corpus distincts du projet. Un passage
proche du sujet, périmé ou excluant la condition demandée doit être distingué
d'un passage qui répond. La seule fidélité à un extrait n'établit pas son
applicabilité à la question.

### S06 — FaithBench, NAACL 2025, publication évaluée par les pairs

[Bao et al., article et PDF officiels](https://aclanthology.org/2025.naacl-short.38/),
§2–3 ; [données des auteurs](https://github.com/vectara/FaithBench).

**Corpus et protocole.** 750 résumés, soit 75 passages et dix modèles de huit
familles ; sélection de cas difficiles sur lesquels les détecteurs divergent,
puis annotations humaines de segments avec explications. **Mesures et
résultats.** Exactitude équilibrée et macro-F1 des détecteurs ; meilleurs
résultats rapportés d'environ 62 % et 57 %, respectivement. **Limite.** Cette
sélection difficile n'est pas représentative de la fréquence des erreurs en
production. **Transfert.** Évaluer le vérificateur sur des annotations
distinctes de celles utilisées pour sa mise au point, avec faux acceptés et
faux rejetés, notamment pour les inversions d'opérateurs et d'exceptions.
La catégorie d'ajouts « bénins » de l'article n'est pas reprise comme
autorisation : dans agentPDFDoc, une information factuelle absente des
documents reste non étayée, même si elle paraît vraie extérieurement.

### S07 — OmniDocBench, CVPR 2025, publication évaluée par les pairs

[Publication officielle CVPR](https://openaccess.thecvf.com/content/CVPR2025/html/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.html),
[texte arXiv v2, §3–5](https://arxiv.org/html/2412.07626v2) ;
[code des auteurs](https://github.com/opendatalab/OmniDocBench).

**Corpus.** La version v2 consultée décrit 981 pages, neuf types documentaires,
19 catégories de mise en page, avec textes, tableaux, formules, boîtes et ordre
de lecture annotés. **Protocole.** Comparaison de pipelines et de modèles
vision-langage sur documents anglais/chinois. **Mesures.** Distances d'édition
pour texte et ordre, TEDS pour tableaux, métriques de formules. **Résultat.**
Les résultats varient selon les types et éléments ; par exemple MinerU obtient
une distance d'édition textuelle de 0,061 en anglais et 0,215 en chinois dans
le tableau 2 de cette version. **Limite et transfert.** Ces résultats ne
qualifient ni notre matériel ni nos PDF. Vérifier séparément signes,
opérateurs, unités et liens cellule-en-tête : une réponse fidèle à une
extraction fautive reste erronée. Ne pas mélanger l'effectif de cette version
du papier avec celui d'une version ultérieure du dépôt.

### S08 — HalluGuard, Findings ACL 2026, publication évaluée par les pairs

[Bergeron et al., article et PDF officiels](https://aclanthology.org/2026.findings-acl.835/),
§4–6 et limites ; [ressources citées dans le PDF](https://hf.co/collections/lrsbrgrn/halluguard).

**Méthode et corpus.** Qwen3-4B spécialisé par ORPO/LoRA, sur 76 708 tuples
synthétiques de préférence dérivés de FineWeb ; classement d'une paire
document–affirmation avec justification. **Évaluation.** Onze ensembles
LLM-AggreFact ; exactitude équilibrée de 84,4 % sur RAGTruth et 77,1 % en
moyenne. **Limites explicites.** Entraînement et évaluation en anglais ;
généralisation linguistique/sectorielle non vérifiée. Vérification multimodale
des tableaux et réduction de la latence restent des perspectives.
**Décision locale.** Retenir la nécessité d'une vérification indépendante,
différer l'intégration du modèle. Ses poids sont spécialisés et distincts du
générateur conservé, même si le backbone s'appelle Qwen3-4B. Le score publié
ne valide ni le modèle quantifié courant, ni son autoévaluation, ni la chaîne
documentaire locale. Aucun second modèle génératif n'est introduit.

## Hypothèses locales et décisions expérimentales

Les liens suivants motivent les expériences ; ils ne valent pas résultat
positif. Les seuils, partitions, commandes et statuts appartiennent au
[protocole](trust-i5-pj-protocol-2026-11-09.md).

| Défaut ou risque local | Méthode proposée et appui | Hypothèse à vérifier et contre-épreuve |
|---|---|---|
| `< 3.3 V` interprété comme égalité ; fausse concordance | Repérer une qualification locale non exacte, conserver le passage et empêcher l'emploi du nombre comme opérande exacte ; S01/S02 motivent le contrôle du support sémantique | Réduire les faux accords en préservant les valeurs exactes témoins. Variantes ASCII/Unicode, strict/inclusif, signes, unités et cas non pris en charge. La comparaison algébrique de bornes, y compris deux inégalités concordantes, reste différée ; cette garde ne l'implémente pas. |
| `unless TA=25°C` utilisé comme preuve à `TA=25°C` | Porter l'exclusion et la portée de la condition jusqu'au contrôle ; S02/S04/S05 | Rejeter l'applicabilité erronée, préserver les conditions positives et les exceptions réellement applicables. Évaluer aussi les exceptions non analysables : une absence de prise en charge ne prouve pas l'absence documentaire. |
| Vérificateur trop permissif ou refusant tout | Jeu annoté séparé, faux acceptés/faux rejetés et couverture ; S06/S08 | Comparer référence et candidat à dénominateurs constants ; l'absence d'erreur obtenue par refus général ne satisfait pas l'utilité. |
| Erreur provenant du document extrait | Contrôle séparé du texte et de la relation extraite ; S07 | Distinguer fidélité au passage extrait et fidélité au document original. Une garde de relation ne répare pas un signe perdu par OCR. |
| Effet du correctif confondu avec celui de la recherche | Même corpus, version et passages pour l'essai isolé, puis chaîne réelle ; S03 | Ablater opérateurs et exclusions séparément ; comparer aussi au rendu extractif. Ne pas attribuer un gain de retrieval au contrôle de relation. |

Le maintien de Qwen3-4B, des contraintes de ressources et des sources immuables
est un invariant. Une correction des deux défauts peut être admise sur preuve
locale sans clore les limites précédentes d'OCR, de complétude ou de recette
des plateformes. La relecture des sources est effectuée ; la qualification
de production ne résulte pas de cette revue bibliographique.
