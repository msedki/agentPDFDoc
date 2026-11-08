# EV4B — KV, résidence, rejeu exact et import natif du 4B

**Rôle :** compte rendu de qualification du composant de génération · **Propriétaire :** runtime et qualification EV4B · **Statut :** essais natifs terminés, portée limitée, D07 non acquis · **Date :** 2026-11-07 UTC · **Référence :** base `59d47e98`, travail `enhanced_version` · **Source de vérité :** [mesures individuelles et manifeste des preuves](enhanced-4b-runtime-results-2026-11-07.json).

## Résultat et périmètre

**Les six combinaisons KV/contexte ont exécuté leurs deux requêtes, les quatre
transitions de résidence sont vérifiées, et le rejeu séparé reproduit la sortie
brute capturée.** L'import dans un store vide reproduit aussi le digest du modèle
antérieur. Les preuves portent sur le runtime : **aucun score de justesse
documentaire, gain de qualité ni validation D07 n'en est déduit**.

Le modèle reste **Qwen3-4B, poids Q4_K_M**, alias verrouillé
`qwen3-4b-enhanced:q4km`, sous Ollama **0.35.0**, CPU explicite, quatre threads
demandés. Les modes f16/q8_0/q4_0 du tableau désignent uniquement le cache KV.
Le digest natif est vérifié via `/api/tags` et les types K/V, tailles et contextes
sont confirmés par les logs d'allocation, indépendamment des variables demandées.

La matrice s'est déroulée du **23:44:41 au 23:49:54 UTC**. Elle comprend **un seul
contexte capturé**, six conditions et deux appels successifs par condition :
**12 générations**, puis **4 générations de résidence**. Le rejeu séparé ajoute
une génération. Ce ne sont pas 17 questions indépendantes.

Les messages, le schéma de réponse et la graine 0 restent identiques. Paramètres
fixes : température 0,2, top-p 0,9, plafond de sortie 768, `think=false`,
`keep_alive=10m`. Le prompt compte **1 091 tokens natifs**, confirmés dans chaque
cellule. Le contrôle préalable réserve **1 091 + 768 + 256 = 2 115 tokens** ;
les deux contextes admissibles sont employés sans tronquer le prompt.

- À **8 192**, le corps HTTP est celui de la capture, octet pour octet :
  `fixed_context_replay`. Le KV du serveur reste la variable expérimentale.
- À **4 096**, seul `options.num_ctx` change : `fixed_context_ablation`.
  Cette variante n'est pas un rejeu exact de la requête initiale.
- Un seul serveur de la matrice fonctionne à la fois ; parallélisme, nombre
  de modèles chargés et file sont fixés à 1. Flash Attention est demandé,
  `LLAMA_ARG_CACHE_RAM=256` et `LLAMA_ARG_CTX_CHECKPOINTS=2` sont explicitement
  définis. Les environnements, versions et empreintes sont dans le manifeste.

## Allocation, mémoire et latences observées

La mémoire ci-dessous concerne **la famille de processus Ollama : serveur et
descendants observés**. Elle exclut l'API, la recherche, Qdrant, le navigateur et
le client de mesure. Le pic présenté est le maximum des deux phases de requête
de la cellule ; leurs valeurs séparées figurent dans le JSON.

| KV | Contexte | Allocation KV vérifiée, MiB | Pic RSS / PSS de la famille, MiB | Premier contenu, appel 1 / 2, s | Fin de génération, appel 1 / 2, s |
|---|---:|---:|---:|---:|---:|
| f16 | 4 096 | 576 | 3 169,0 / 3 166,7 | 22,326 / 0,102 | 26,772 / 3,754 |
| f16 | 8 192 | 1 152 | 3 825,2 / 3 822,9 | 22,382 / 0,092 | 26,289 / 3,483 |
| q8_0 | 4 096 | 306 | 2 899,2 / 2 896,9 | 30,813 / 0,126 | 36,169 / 6,042 |
| q8_0 | 8 192 | 612 | 3 293,9 / 3 291,5 | 31,512 / 0,130 | 36,686 / 5,431 |
| q4_0 | 4 096 | 162 | 2 751,8 / 2 749,5 | 32,870 / 0,112 | 37,592 / 4,881 |
| q4_0 | 8 192 | 324 | 3 007,5 / 3 005,2 | 31,315 / 0,117 | 36,252 / 4,953 |

Source : sections `cells` et `evidence_manifest` du
[JSON de résultats](enhanced-4b-runtime-results-2026-11-07.json).
Dans chaque allocation, K et V occupent chacun la moitié du total indiqué.

Le premier appel utilise un nouveau serveur et annonce **0 token de prompt en
cache** ; le second conserve le modèle résident et annonce **1 090/1 091 tokens
en cache**. Un nouveau serveur ne prouve pas un cache de fichiers système froid.
Le temps jusqu'au premier contenu mesure le premier fragment non vide du modèle,
pas la première réponse documentaire validée et affichée. La fin de génération
mesure la fin du flux HTTP ; elle n'inclut pas la recherche ni le rendu.

L'allocation KV et les pics de mémoire sont plus faibles dans les cellules
quantifiées observées. Le premier contenu y arrive ici plus tard que dans les
cellules f16. L'ordre des conditions est fixe, les états de cache diffèrent entre
les deux appels et un seul contexte est utilisé : **aucun percentile de service,
intervalle de confiance ni classement général de vitesse n'est établi**.
Le prompt de 1 091 tokens ne teste pas la saturation des fenêtres 4 096/8 192.

Les **1 175 échantillons** de la matrice et de la résidence, à intervalle demandé
de 250 ms, comportent tous une famille et un PSS lisibles. Le RSS additionne les
pages partagées de plusieurs processus ; le PSS est relevé par lectures
successives, non atomiques. Ces pics échantillonnés ne sont pas des maxima absolus.
Les sept familles créées par la matrice sont arrêtées, sans PID survivant recensé.

### Identité des sorties et différence structurelle

Les 12 sorties forment **deux groupes d'empreintes brutes : A = 10, B = 2**.
Les deux sorties B sont les seconds appels f16, à 4 096 et 8 192. Elles comportent
50 tokens de sortie, contre 57 pour les sorties A.

Toutes passent un parsing JSON strict sans clé dupliquée ni constante non finie.
Après tri des clés et suppression des blancs de présentation, **deux empreintes
subsistent** : la différence n'est donc pas seulement typographique. Le seul
changement est la liste `$.references`, qui contient deux références dans A et
une seule dans B ; la seconde référence racine est absente de B. La sous-structure
`comparisons`, dont la comparaison conserve ses deux références, est identique.

Il s'agit d'une variation réelle du plan structuré observé. **Le parsing JSON et
l'identité d'une sortie ne prouvent ni la conformité au schéma ni la justesse de ses
références.** La matrice ne juge pas ces réponses contre les documents. Elle ne
démontre pas non plus un déterminisme général de la graine ou du runtime.

## Résidence : vérification par `/api/ps`

Une séquence séparée utilise q8_0/8 192 et le même corps de génération à chaque
étape, via `OllamaGateway`. Les appels de contrôle de déchargement sont distincts
de ce corps. Les quatre sorties appartiennent au groupe A.

| Politique / étape | Résident avant → après | Premier contenu, s | Génération, s | Décision observée |
|---|---|---:|---:|---|
| `keep` | non → oui | 30,934 | 36,351 | conservé |
| `unload` | oui → non | 0,121 | 5,559 | déchargement vérifié ; contrôle 79,12 ms |
| `adaptive_normal` | non → oui | 30,417 | 35,970 | conservé ; disponible 3 970,54 MiB > seuil 2 560 |
| `configured_threshold_probe` | oui → non | 0,144 | 5,453 | déchargement vérifié ; contrôle 81,45 ms |

Source : section `residence` du
[JSON de résultats](enhanced-4b-runtime-results-2026-11-07.json), avec états
`/api/ps` avant/après et compteurs natifs.

Le probe configure volontairement un seuil de **9 969 MiB**, supérieur aux
9 967,26 MiB de mémoire visible, avec estimation d'embedding et marge de
déchargement nulles ; la disponibilité relevée est 3 920,21 MiB. Il vérifie la
branche de décision et le déchargement avec un **seuil artificiel configuré**.
Il ne démontre pas un manque de RAM naturel. L'étape adaptative normale conserve
le modèle : le déchargement adaptatif sous pression naturelle n'est pas testé
dans cette matrice. Les observations de la campagne applicative sont rapportées
séparément dans le [bilan EV4B](enhanced-4b-results-2026-11-07.md).

Les latences ne comparent pas causalement les politiques : `keep` et l'étape
adaptative normale commencent sans modèle chargé ; les deux déchargements
suivent une génération profitant du préfixe en cache. Les quatre pics RSS sont
compris entre 3 296,0 et 3 296,6 MiB. L'absence du modèle dans `/api/ps` est
vérifiée ; la quantité exacte de RAM rendue à l'OS n'est pas isolée par ces pics.

## Rejeu séparé, import neuf et coût de sérialisation

### Rejeu exact de la requête capturée

Un nouveau serveur q8_0/8 192 reproduit les **octets HTTP et le digest du modèle**,
puis une sortie brute identique à la capture, groupe A : premier contenu à
**30,323 s**, génération terminée en **35,764 s**, 1 091 tokens de prompt sans
préfixe en cache et 57 tokens de sortie. Le KV effectif de **612 MiB** est vérifié
dans les logs du nouveau serveur. Le pic échantillonné de cette famille est
**3 296,0 MiB RSS / 3 293,7 MiB PSS**, sur sa vie observée ; la phase du sampler
reste nommée `startup` pendant cet essai séparé.

L'outil de rejeu ne vérifie pas lui-même les options du serveur et conserve
`server_options_verified=false` ; le fichier serveur séparé apporte la preuve
effective de ce nouveau KV. L'environnement initial n'est pas intégralement reproduit : le réglage
de checkpoints v1 était inopérant, tandis que ce serveur fixe explicitement
`LLAMA_ARG_CTX_CHECKPOINTS=2`. **Requête exacte ne signifie donc pas environnement
entier identique.** Ni recherche ni rendu de réponse ne sont rejoués.

### Import natif dans un store vide

Le provisionnement retourne **`imported_verified`**, puis **`verified_existing`**
au second appel. Le digest natif du modèle et le SHA-256 du GGUF correspondent
strictement au manifeste antérieur. C'est seulement après ces contrôles que le
manifeste existant reçoit la provenance vérifiée ; son ancienne version est
conservée et le store initial reste inchangé. Les identités du tokenizer, de son
template et des manifestes figurent dans `native_provision` et le manifeste des
preuves. **Aucune inférence n'est exécutée dans le store neuf.** Le rejeu ci-dessus
utilise le store existant. Les serveurs de ces deux essais sont arrêtés.

### Sérialisation des traces, hors inférence

Huit événements réels capturés sont réenregistrés **20 fois par mode**, dans
l'ordre fixe `off`, `hashes`, `full`. Le chronomètre couvre création de la trace,
enregistrement, sérialisation/hachage, résumé et fermeture. Il exclut construction
de la requête, recherche, inférence initiale et relecture de vérification.

| Mode | Médiane, ms | Maximum observé, ms | Octets par requête |
|---|---:|---:|---:|
| `off` | 0,068 | 0,157 | 0 |
| `hashes` | 1,376 | 1,613 | 3 291–3 294 |
| `full` | 2,079 | 2,603 | 55 149–55 152 |

Ces observations décrivent une boucle locale de sérialisation après arrêt des
serveurs natifs. Le surcoût du pipeline complet reste **`NOT_RUN`** ; ces durées
ne sont pas un effet mesuré sur la latence d'inférence. Les 60 observations sont
conservées dans `trace_serialization` du JSON.

## Hôte, essais interrompus et portée de réception

L'hôte est Linux x86_64, avec **9 CPU logiques visibles**, **9 967,26 MiB de RAM
visible** et 6 125,88 MiB disponibles au départ. Il n'expose aucun swap ; aucun
swap utilisé, entrant ou sortant n'est relevé dans les échantillons de la matrice.
Le minimum de mémoire disponible observé y est 2 193,33 MiB. Les limites cgroup
et la description précise du processeur ne sont pas observées ; le support de
stockage n'est pas mesuré et aucun navigateur n'est exercé.

Les essais applicatifs antérieurs sont conservés séparément et ne contribuent
pas aux dénominateurs de la matrice :

- **v2 :** première requête terminée en erreur `resource_admission_denied`, sans
  appel LLM ; le snapshot d'attente capturé indique 5 557,60 MiB disponibles pour
  5 888 requis, puis le message d'erreur terminal indique 5 604 MiB disponibles,
  en affichage entier. La seconde trace s'arrête sur `admission.wait`, également
  sans requête LLM capturée.
- **v3 :** une réponse baseline est terminée. La requête enhanced suivante a
  attendu avec modèle résident, 2 156,36 MiB disponibles pour 2 176 requis, puis
  a atteint `admission.granted` et `llm.request`. **Aucune `llm.response` ni fin de
  requête n'est capturée avant l'interruption.** Ce constat corrige le diagnostic
  provisoire fondé sur la dernière lecture de l'attente ; v3 ne doit pas être
  présentée comme entièrement interrompue avant appel du modèle.
- Le profil pilote de v3 estime la charge froide à 3 840 MiB, sur la base d'une
  observation v1 explicitement distincte de cette matrice. La réserve reste à
  1 536 MiB ; l'estimation du profil de référence reste à 4 352 MiB. Cette
  expérience de diagnostic ne change pas les seuils de production.

Le manifeste versionné identifie les rapports natifs, leurs logs et échantillons,
la capture source, les outils, le binaire, les profils et les manifestes du modèle
par leurs SHA-256. **Le corpus, les messages, les sorties brutes et les chaînes
HTTP ne sont pas recopiés dans cette synthèse versionnée.**

**D07 reste `false`.** Cette série qualifie des mécanismes du runtime sur un
contexte figé. Elle ne constitue pas une réception de l'application et du
navigateur sur la machine cible 16 Go, une activité mixte de 30 minutes, une
comparaison de qualité sur corpus représentatif, ni une preuve du comportement
du correctif d'admission applicative sur une campagne complète. La réception
de ces points repose sur leurs propres essais et preuves.
