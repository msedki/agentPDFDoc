# I5 — fiabilité des preuves et générateur 4B unique

**Statut : sources I5 publiées et vérifiées ; qualification de production non acquise.**
Le suivi des actions reste dans [PLAN.md](../PLAN.md). Ce bilan distingue les
changements implémentés, les observations exécutées et les critères qui restent
à démontrer. I5 désigne la reprise du 8 novembre 2026 dans l'historique du dépôt ;
elle répond à la troisième itération demandée dans la conversation.

## 1. Périmètre et critères préalables

La référence est `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, conservée dans un
worktree isolé. La branche de livraison est `enhanced_version`. Le
[protocole](trust-4b-protocol-2026-11-08.md) a été gelé avant les modifications
produit, avec ses neuf critères de réception. Les
[points d'entrée](trust-4b-entrypoints-addendum-2026-11-08.md) et les
[ressources](trust-4b-resource-addendum-2026-11-08.md) ont leurs addenda préalables.
Aucun critère n'est abaissé à la lecture d'un résultat.

Les deux bras utilisent Qwen3 **4.0B Q4_K_M**, tag
`qwen3-4b-enhanced:q4km`, sans autre générateur. Le GGUF, le tokenizer, les
paramètres d'inférence, E5-small INT8, Qdrant, Docling et le Tesseract corrigé
sont identifiés dans le protocole. Les plafonds de contexte, de fragments,
de sortie et la réserve de mémoire restent constants. Les nouvelles lectures
OCR partagent les budgets d'appels et de pixels existants.

Le corpus I4 déjà consulté sert exclusivement au développement : deux PDF TI,
huit questions de transfert, deux scans et huit questions Office, soit vingt
questions par bras. Un autre ensemble, préparé indépendamment avant le code,
est réservé à la réception finale : dix questions et deux dérivés positifs par
bras. Une erreur, un délai dépassé ou une abstention sur une question positive
reste au dénominateur.

## 2. Changements et conséquences

### Extraction et géométrie des sources

La couverture des objets vectoriels détecte un corps visible absent de la
couche texte, y compris lorsqu'un pied de page natif faisait auparavant classer
la page comme exploitable. La reprise OCR est régionale et bornée ; les zones
non résolues restent signalées.

Les relations de tableau sont reconstruites depuis les positions et les
caractères réellement observés. Une cellule vide ne décale plus les rôles
Min/Typ/Max ; les sous-lignes et conditions restent distinctes. La grammaire
libellé/valeur/unité établit une quantité sans inventer un rôle statistique.
Un tableau tourné utilise un repère de lecture local attesté, puis revient
aux coordonnées physiques du PDF pour ses références.

Les conditions générales d'un tableau sont liées par des indices explicites,
des positions et des fragments exacts. La proximité seule ne justifie pas
l'association. Le catalogue revalide la révision, le texte, le cadre de page
et la boîte du bloc depuis SQLite, sans prendre le résultat de recherche pour
autorité. Voir le [rapport d'ingestion](trust-4b-ingestion-2026-11-08.md).

### Accord OCR et conservation de l'incertitude

Une confiance élevée n'est plus suffisante. Les observations conservent leurs
rasters, paramètres, positions et lectures littérales ; leur accord doit être
bijectif. Une négation supplémentaire, une unité différente, un signe ambigu
ou un conflit entre régions interdit la preuve concernée. Le contrôle des
signes positifs a été corrigé après un contre-exemple réel « ± » lu « + ».

Une seule relecture sans agrandissement peut rattraper un score trop faible
si le premier accord littéral et géométrique est déjà complet. Elle conserve
la lecture agrandie et ne peut rattraper un désaccord de texte. Le texte brut
n'est jamais remplacé par la valeur attendue d'un test. Ces contrôles améliorent
l'examen de la lecture ; ils ne certifient pas tous les glyphes de tout document.

### Preuves admises et réponse finale

Les besoins explicites de la question sont conservés avant la génération.
Le 4B reçoit une vue limitée aux preuves admissibles et produit un plan par
identifiants ; il ne fournit pas de prose libre à publier. Les faits retenus
gardent leurs passages, conditions, réserves, documents, pages et révisions.
Le contrôleur complète les preuves demandées omises du plan, exclut les ajouts
hors besoin et vérifie de nouveau tous les segments avant le premier delta
public. Une limite ne peut être transformée en conclusion par le modèle.

Les calculs restent déterministes, avec entrées, unités, méthode et références
rejouables. Les conflits et les lacunes sont conservés. Un besoin général que
la grammaire ne sait pas vérifier reçoit une limite explicite ; cette route
doit être mesurée comme telle, sans lui attribuer un gain de complétude.
Voir le [rapport des contrats](trust-4b-evidence-2026-11-08.md).

### Exploitation et distribution

Le profil renforcé devient le défaut de l'API et des lanceurs. Les entrées de
génération refusent un autre modèle ou la désactivation des contrôles requis.
Le catalogue et le filtre de distribution retiennent uniquement ce générateur,
avec les composants non génératifs nécessaires. Le provisionnement importe
le GGUF verrouillé, vérifie le stockage natif après l'arrêt du service possédé
et conserve les bornes de ressources.

Une migration explicite reprend les contrôles du profil renforcé en conservant
les chemins et ports utilisateur dont l'origine est connue. Les anciens profils
restent accessibles aux opérations de maintenance. Les preuves géométriques
absentes des anciennes extractions demandent une ré-ingestion ; leur absence
n'est pas remplacée par une attestation automatique. Les procédures figurent
dans l'[exploitation](../../docs/exploitation/EXPLOITATION.md) et le
[déploiement](../../docs/deploiement/DEPLOIEMENT.md).

## 3. Résultats contrôlés déjà exécutés

La matrice primaire conserve les mêmes trente cas, leurs sources et leurs
attendus. L'extraction Office, SQLite, FTS et QueryService sont réels ; E5,
le transport vectoriel, le tokenizer et le plan génératif y sont des doubles
nommés. Ce résultat n'est donc pas une mesure du modèle 4B réel.

| Mesure primaire | Référence | Candidat |
|---|---:|---:|
| Questions positives complètes et fidèles | 12/12 | 12/12 |
| Contrôles limites selon le critère gelé | 18/18 | 16/18 |
| Faits littéraux retrouvés, proxy R@10 | 15/15 | 15/15 |
| Proxy de présence dans le contexte | 14/15 | 14/15 |
| Citations à intégrité littérale vérifiée | 31/31 | 27/27 |
| Marqueurs de faits inventés publiés | 0 | 0 |
| Latence médiane de cette campagne | 131,065 ms | 134,72 ms |
| Latence maximale de cette campagne | 328,28 ms | 398,31 ms |

Les douze réponses positives sont déterministes dans les deux bras. La revue
indépendante confirme onze réponses identiques et une permutation d'ordre des
documents/citations. Les 33 instances de documents sont identiques. Le proxy
14/15 conserve l'échec de sa regex sur une tabulation échappée : l'unité est
présente une fois décodée, mais le compteur brut n'est pas réécrit.

Les cas L11/L12 ne traversent plus le sélecteur sur la nouvelle route générale
sans preuve admissible. Leur résultat ne démontre donc pas le rejet des plans
adverses attendu par le critère gelé : les deux échecs restent comptés. Un
complément distinct sur une route ayant un catalogue non vide vérifie cette
frontière sans remplacer les trente primaires. Voir la
[revue indépendante](trust-4b-controlled-review-2026-11-08.md).

### Suivi final sur la source 8

Le même ensemble contrôlé de trente positions est exécuté une nouvelle fois
après le suivi natif 8, sans changer ses 33 originaux, ses questions, son
harnais ni ses critères. Ce suivi distinct confirme **12/12 positifs et
16/18 limites**. L11/L12 restent en échec, sans appel au double de sélection ;
la route générale ne met pas à l’épreuve les plans adverses de ces deux cas.
Les six appels de sélection de la campagne sont des doubles déclarés, aucun
ne prouve une inférence réelle 4B. L10 provoque bien l’erreur applicative de
localisateur attendue, sans texte public : son contrôle réussit, et aucune
erreur du harnais n’est observée.

Le reçu d’exécution porte
`b98ba82cca716fe445fa54866f8fac8f212463595a0b2c26e0b1a864635c1d49` ;
la revue contre les originaux, les traces et les citations porte
`89ebc4e7e40d89f404cbd568a85b2dbd52289bc3a6571a3be9652c2751dbb332`.
Les primaires et le supplément de frontière restent conservés séparément.

## 4. Campagnes natives et régressions

### Observations de développement conservées

La phase 4 comprend cinq refus d'admission mémoire et trois réponses
déterministes. Elle est conservée dans la [revue de ressources](trust-4b-resource-observations-2026-11-08.md).
La mémoire occupée par les preuves de tests sur tmpfs a été libérée après leur
conservation vérifiée sur disque. La phase 5 est une reprise distincte, avec
6 656 Mio disponibles exigés avant chaque bloc ; la réserve produit de
1 536 Mio et le seuil froid de 5 888 Mio ne changent pas.

La référence de phase 5 termine ses vingt questions le 9 novembre à 00:41:23
UTC. Les cinq groupes de services sont arrêtés et réapés, les vingt cas ont un
résultat terminal et les cinq contrôles de stabilité ne signalent aucun fichier
modifié. Les verdicts viennent de la [revue des PDF et scans](trust-4b-development-review-2026-11-09.md)
et de la [revue Office](trust-4b-api-office-review-2026-11-09.md).

| Ensemble de référence phase 5 | Positifs stricts | Limites strictes | Erreurs techniques |
|---|---:|---:|---:|
| Transfert I4 devenu développement | 0/6 | 1/2 | 1/8 |
| Deux scans de développement | 0/2 | Sans cas limite | 0/2 |
| Deux PDF TI | 1/2 | Sans cas limite | 0/2 |
| Huit cas Office | 4/4 | 4/4 | 0/8 |

La référence conserve la fausse association Min/Typ de H03 et deux réponses
de scans contenant des unités ou variables OCR corrompues. Les deux plages
d'INA226 sont présentes mais accompagnées d'une réserve injustifiée. H06
termine en `ollama_timeout` : une requête au modèle a bien été envoyée, sans
réponse réussie ; le champ final `model_called=false` ne signifie pas absence
de tentative. Les quatre positifs Office et TMP117 suivent des routes
déterministes, distinctes des réponses obtenues avec le modèle.

### Candidat de phase 5 : quatre réponses, puis interruption du pilote

L'instantané de développement 5 porte le reçu
`bddd2d348b07d154e94ed652155152bb9bbede8f9bd6e2e04715902a3f14f478`.
Après extraction complète des trois premiers PDF, H01/H02/H04 sont complets
et fidèles, sans réserve globale injustifiée : **3/3 positifs relus réussis**.
H03 évite la fausse colonne et l'extrapolation, mais omet la plage garantie
justifiant la limite : **0/1 cas limite réussi**. Les quatre réponses sont
déterministes ; leurs latences ne mesurent pas la vitesse du 4B.

Le lancement du bloc B est refusé par la sonde de port avant création du
dossier, démarrage de service ou mesure de question. Les quatre réponses A
restent les seules réponses candidates de phase 5 ; les seize autres questions
prévues ne sont pas créditées. La cause historique exacte de l'occupation du
port est inconnue. Un contre-exemple de socket distinct prouve toutefois une
lacune du harnais sur les ports en `TIME_WAIT` ; le pilote est raccordé au
helper POSIX existant du runtime, qui continue de refuser les écouteurs actifs.
Les limites du modèle et du bloc ne sont pas modifiées.

Le défaut de justification H03 et l'incident de lancement sont conservés.
Une reprise sur un nouvel instantané de développement est préparée après leur
correction. Les extractions restantes sont réalisées avec l'ingestion inchangée
de l'instantané 5 ; leur réutilisation exigera une comparaison des sources et
des empreintes. Aucun corpus réservé I5 n'est ouvert à ce stade.

### Candidat de phase 6 : vingt résultats terminaux, trois erreurs

Le candidat de phase 6 termine le 9 novembre à 01:53:49 UTC. Son reçu source
`f6c39760709a5bdb1cd454f9a99ba850d472583e6000f396e7c9b9ee8b293690`
couvre 169 fichiers. Les trois groupes d'extraction et les cinq blocs de
questions sont fermés, avec arrêt des services vérifié et sources inchangées.
Les sept PDF/scans ont été réextraits : 125 pages et 6 066 blocs. Les résultats
ne sont pas fusionnés avec les quatre réponses candidates de phase 5.

| Ensemble candidat phase 6 | Positifs stricts | Limites strictes | Erreurs techniques |
|---|---:|---:|---:|
| Transfert I4 devenu développement | 4/6 | 1/2 | 2/8 |
| Deux scans de développement | 1/2 | Sans cas limite | 0/2 |
| Deux PDF TI | 1/2 | Sans cas limite | 1/2 |
| Huit cas Office | 4/4 | 3/4 | 0/8 |
| **Total** | **10/14** | **4/6** | **3/20** |

H03 justifie maintenant correctement la limite par la plage garantie.
SCAN1 restitue les deux plages sans publier l'unité OCR corrompue voisine.
INA226 restitue les plages de bus et d'alimentation sans réserve globale
injustifiée. H07 s'abstient encore, faute de sujet explicitement rattaché aux
lignes pourtant présentes. SCAN2 conserve une abstention sûre sur ses liaisons
OCR ambiguës ; cela reste un échec d'utilité sur un positif récupérable. L13
Office omet la seconde négation de l'original. H06, H08 et TMP117 échouent avec
`trace_write_failed` avant une tentative de génération.

Les cinq requêtes réelles au modèle aboutissent ; douze réponses sont
déterministes. Les trois erreurs ne sont attribuées à aucune de ces deux routes
réussies. La cohérence littérale des citations livrées n'efface ni les omissions
ni les erreurs. Les [coûts et arrêts](trust-4b-development-resource-costs-2026-11-09.md)
sont distincts des verdicts de contenu.

Une phase 7 de développement est préparée après correction des cadres de page,
des réserves rattachées à un sujet répété et de l'autorité du sujet de tableau.
Le [rapport des frontières de source](trust-4b-source-boundaries-2026-11-09.md)
conserve les contre-exemples avant correction. Le corpus réservé I5 reste fermé.

### Candidat de phase 7 : erreurs de trace corrigées, trois besoins incomplets

La phase 7 utilise l'instantané de 172 fichiers, reçu
`d496b48fc8b4119b9ff7cdd6b1e4960d84dd6b7bf3ffdfa1c16bf1e89a6539df`.
Elle se déroule de 02:19:34 à 02:27:38 UTC le 9 novembre et termine ses
vingt cas avec cinq arrêts vérifiés, sans dérive des sources. Les extractions
complètes de phase 6 sont réemployées après contrôle des octets et dépendances ;
aucun nouveau worker PDF n'est attribué à cette phase. Le réemploi ne reconstitue
pas un gel binaire exhaustif qui n'avait pas été enregistré avant la phase 6.

| Ensemble candidat phase 7 | Positifs stricts | Limites strictes | Erreurs techniques |
|---|---:|---:|---:|
| Transfert I4 devenu développement | 5/6 | 1/2 | 0/8 |
| Deux scans de développement | 1/2 | Sans cas limite | 0/2 |
| Deux PDF TI | 2/2 | Sans cas limite | 0/2 |
| Huit cas Office | 4/4 | 4/4 | 0/8 |
| **Total** | **12/14** | **5/6** | **0/20** |

H07 restitue désormais les deux délais typiques avec leurs overdrives et toutes
les dépendances, y compris le sujet imprimé. TMP117 restitue les deux plages
avec leurs températures. L13 conserve les deux négations ; les huit contrôles
Office de liaisons, révisions et hashes passent avec base inchangée.

Les trois besoins non satisfaits sont **H06**, **H08** et **SCAN2**. H06 refuse
les deux plages pourtant livrées dans le paragraphe natif. H08 refuse sans citer
la condition source de 10 mV ; il ne promet pas de garantie à 1 mV, mais régresse
sur ce critère face à la référence 5. Leur fin technique réussie ne satisfait
pas leur besoin documentaire. Le sujet manque dans leurs relations de prose ;
l'autorité d'en-tête ajoutée en phase 7 s'applique alors seulement aux tableaux.
SCAN2 conserve les mêmes lectures OCR ambiguës et une abstention sûre, toujours
comptée comme échec positif.

La revue PDF/scans porte le reçu
`f7c335d692308899b320770d222fcfc09f0a8ed10c5ba0d36a181de9763ea3cd` ;
la revue Office avec raccord de provenance porte
`db88485b03ef32638e49dcd8aec92daa2de6623661858f7f582089c29b613fa8`.
Les cinq tentatives réelles de génération aboutissent ; les quinze autres
réponses sont déterministes. Un suivi 8 motivé par H06/H08 est préparé avant
les portes finales et avant l'ouverture du réservé, avec les mêmes vingt cas
et des sorties neuves. Les résultats 5/6/7 et leurs échecs restent conservés.

### Source 8 : sujet de prose vérifié et régression TMP117 conservée

L'autorité d'un en-tête imprimé est étendue aux blocs de prose PDF complets et
revalidés. Un titre déjà retenu, commençant par un identifiant explicite unique,
peut aussi fournir son segment d'identité sous les mêmes gardes de périmètre,
qualité, révision, géométrie et absence de concurrent. Une relation qui emprunte
ce sujet doit en conserver la citation ; passage et dépendance forment une
unité de restitution sous budget. Le nom du fichier ne fournit plus le sujet
de cette prose PDF.

Les contrôles hors moteur reconstruisent le catalogue depuis les mêmes bases
et les mêmes fragments retenus en phase 7. H06, H08 et INA226 sont rétablis dans
ces contrôles ; H08 utilise explicitement un double de sélection et conserve
sa voie modèle réelle à éprouver. TMP117 régresse : les deux plages sont citées,
mais leur sujet ne peut être établi et la réserve initiale rend la réponse
incomplète au sens du critère. L'extraction mêle navigation, pictogrammes et
ligne de révision au corps supérieur. La relation nécessaire manque ; aucun
motif lexical propre à cette fiche n'est ajouté pour contourner le refus.

La revue indépendante se clôt donc **avec une non-régression TI en échec**,
reçu `7810a8695aa1634ccb49fef5243003d4df7346b6eac7176c19400c5a4d23eb47`.
Le reçu API `94b8fa47a6b0cb0b45fd6c9e04f7c40fd8d93739cc68ca7df97ebaa357215042`
conserve les 364 tests ciblés réussis, Ruff/Mypy, les premiers contre-exemples
rouges et les trois seules sources produit modifiées depuis 7. La grammaire
des valeurs, conditions et garanties reste identique.

L'instantané 8 porte le reçu
`1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b`.
Le suivi natif de vingt questions se déroule le 9 novembre de 03:08:51 à
03:23:52 UTC sous le plan
`0ed26792f303db5785cba66871688528ec7a1e53a5b4eeb975435889929e85bb`.
Les vingt états sont terminaux, sans erreur technique. Les cinq groupes de
services sont arrêtés et réapés ; les inventaires complets de ROOT et de
l'instantané concordent avec les 172 fichiers gelés. Le reçu de clôture porte
`226ac1d46120e32a0a0cc628392c689447f3d866090b8ba7bf4c2d0634dc6fe9`.

| Ensemble candidat phase 8 | Positifs stricts | Limites strictes | Erreurs techniques |
|---|---:|---:|---:|
| Transfert I4 devenu développement | 6/6 | 2/2 | 0/8 |
| Deux scans de développement | 1/2 | Sans cas limite | 0/2 |
| Deux PDF TI | 1/2 | Sans cas limite | 0/2 |
| Huit cas Office | 4/4 | 4/4 | 0/8 |
| **Total** | **12/14** | **6/6** | **0/20** |

H06 restitue maintenant les deux plages avec l'identité imprimée citée, par
la voie déterministe (15,292 s observées). H08 appelle réellement le 4B et
refuse le maximum demandé tout en citant les 60 µs à 10 mV et leur sujet
(117,959 s). Ces observations natives sont distinctes des contrôles simulés.

TMP117 confirme la régression sur la voie modèle réelle (78,212 s) : les deux
plages et températures sont exactes, mais la réserve globale est injustifiée
et l'intitulé source « Supply range » requis est omis. Aucun nombre faux n'est
imputé à ce cas ; la complétude et le contexte demandé échouent. SCAN2 conserve
son abstention totale sur les lectures ambiguës et reste un échec positif.
INA226 passe avec ses deux plages. Office conserve les quatre positifs et
quatre limites, dont les deux négations de L13 et la note complète de L16.

La revue indépendante PDF/scans/TI porte le reçu
`f1e404e764d6cb3211d60bd0819c2b79e019f3ab21749ac4bf99e2728c86cc34`.
La revue Office finale, contre les neuf originaux XML et avec l'audit de
liaisons DB rattaché, porte
`fbb2c31152e106481c01f21c565f07813eb0fd8542969c5e1ec9b4568a872a9e` ;
elle conserve sa première relecture et le reçu API
`7836fc7c0d963e0ad350437b95091749d44e8ce71f6a9349289281b37fd0d65c`.
Sept appels réels au modèle et treize réponses déterministes sont distingués.
Les mêmes limites de
contexte, mémoire et délais sont conservées. La variation des temps entre
phases ne démontre pas une accélération du modèle : les routes diffèrent et
chaque cas n'a qu'une observation par phase.

### Portes logicielles et périmètre temporel

La suite portable déjà exécutée compte 4 704 PASS /25 SKIP, les intégrations
hors tests longs 27 PASS /3 SKIP, l'OCR réel 8 PASS et le frontend 487 PASS.
Ces résultats précèdent les derniers correctifs et ne qualifient pas leurs
octets. Les premiers essais rouges restent conservés, notamment 5 FAIL /3 PASS
pour l'OCR et la première suite portable en échec. Les portes finales ont porté
sur les sources stabilisées ; leurs résultats sont maintenant clos, selon l'[ordonnancement préalable](trust-4b-final-blocks-addendum-2026-11-09.md).

Le premier passage portable final sur la source 8 se termine à 03:36:45 UTC :
**5 078 PASS, 2 FAIL, 25 SKIP et 48 désélectionnés**, en 549,35 s. Le reçu porte
`4adf0393805b53069a3171c30e16c3c13ac02e9b2d2b2f18f8aa99d335018e83`.
Les 549 fichiers gelés restent inchangés pendant ce passage. Les deux attentes
en échec attribuent DEV123 à une liste dont ni l'en-tête ni les items ne portent
cet identifiant ; seules la question et le nom `DEV123.pdf` le fournissent.
Le nouveau contrat retourne correctement `partial` au lieu de cette liaison
non prouvée. Les variantes ayant un identifiant imprimé ne sont pas en échec.

La disposition conserve ces deux cas comme contrôles négatifs et maintient les
vrais positifs avec leurs assertions de conditions et citations. Elle ne change
aucun produit ni aucun cas ou critère documentaire natif/contrôlé. Le passage
rouge reste intact. Après contre-revue, cette seule adaptation de test change
le gel logiciel v2 en v3 : huit variantes positives avec sujet imprimé et les
anciens corps de fonctions restent inchangés, les deux variantes sans sujet
sont des négatifs explicites. Aucun fichier produit ne change. Les 25 skips ne sont pas crédités : 22 portent
sur Windows/PowerShell/Win32 ; les trois autres concernent un ancien extrait
absent, un emplacement de stockage Ollama non provisionné pour ce contrôle et
un build CMake/compilateur indisponible.

### Résultats des portes finales

| Porte finale | Résultat | Périmètre et limite |
|---|---:|---|
| Portable Python | 5 080 PASS, 25 SKIP, 48 désélectionnés | Gel logiciel v3, 577,44 s ; le rouge précédent n’est pas remplacé |
| Intégration hors tests longs | 30 PASS, 3 SKIP, 101 désélectionnés | 20,06 s ; les trois skips nécessitent Windows/Win32 |
| OCR réel | 8 PASS, aucun SKIP | 208,99 s, mêmes moteurs et sources gelées |
| Ruff | PASS | Services, tests et outils |
| Mypy | PASS | 148 fichiers sources |
| Frontend Node | 487 PASS | Ensemble distinct, jamais additionné aux groupes Python |
| TypeScript, ESLint, export frontend | PASS | Aucun essai navigateur ni qualification de kit neuf déduit |

Le reçu de clôture des cinq portes code porte
`a7ad9e999456423da069346880c4925c6afa9e678ec0b08e59d17de66b57f51d` ;
la contre-revue indépendante porte
`a282f6d0aeee4084aff14b8d1b115271bdd5e92e456062c940505371f2fb014e`.
Les 549 fichiers du gel logiciel et les 172 fichiers produit du snapshot 8
restent identiques. Le frontend conserve ses 176 entrées vérifiées avant et
après les quatre portes ; cinq configurations complémentaires sont attestées
seulement après le build, identiques à la référence Git. L’export précède le
commit de livraison : il ne constitue pas un paquet distribuable lié à ce
futur commit. Skips et désélections ne sont jamais crédités comme réussites.

Ces essais se chevauchent parfois dans leur sélection et ne forment pas un
dénominateur global additionnable. Le passage natif 8 et le suivi contrôlé ne
sont pas répétés après la correction du test : leurs octets produit et leurs
entrées restent identiques, ce que vérifient les deux gels.

## 5. Transfert réservé : interruption et absence de verdict

Le gel final est enregistré le 9 novembre à **04:05:09 UTC**, avant la première
lecture du contenu réservé par les auteurs produit. Il lie les 172 fichiers
produit, la référence isolée, 65 fichiers runtime, les versions de bibliothèques
et les empreintes des modèles. Son reçu porte
`3835b9ea656e92c7cf80de04267d1b8632f346de4c6f152f1da35f8a0c091472` ;
le plan lié porte
`e689708ccbc5ced018ca9c6bd438b0328b3d4c92825251ddf63d8ac143975492`.
Les trois manifestes réservés sont ensuite copiés octet pour octet dans
[trust-i5-corpus](trust-i5-corpus/). La matérialisation réelle recopie trois
originaux et recrée deux paires PDF/image identiques aux empreintes gelées :
reçu `ab31f41def13f9e6553c3548469ebce0a065ffcdc21a53668b316b54d210c67e`,
vérification `72881ad5c49ad30bddca8fe94e6c4cee4aae55b302eb34bad8b80665c143e5eb`.
Les deux pré-revues indépendantes des sources et oracles ne relèvent pas de
désaccord ; elles ne sont pas des essais de réponse de l’application.

Le premier lot candidat démarre à 04:13:46 UTC. D01 et D02 traitent leurs
22 et 26 pages et disposent de reçus de workers fermés, respectivement en
262,53 s et 236,21 s, contre 108,60 s et 119,60 s pour les extractions de
référence conservées. Les deux sorties restent `ready_partial` ; ce statut
n’interdit pas une réponse correctement étayée et ne garantit pas son utilité.
Ces durées uniques ne démontrent pas un effet causal ni une capacité cible.

La continuité du canal d’exécution est ensuite perdue : la session de
l’ordonnanceur n’est plus accessible. D03 conserve trois fenêtres couvrant
les indices 0–11 ; sa dernière écriture de cycle de vie date de
**04:26:26 UTC**, sur l’événement `page_range=[13,13]`. Aucun reçu terminal D03,
d’action d’extraction ou de dispatcher n’est disponible. La cause demeure
**inconnue** : ni délai dépassé, ni épuisement mémoire, ni défaut produit ne
sont attribués sans preuve. La disponibilité d’un verrou et de ports dans un
nouveau contexte ne prouve pas l’arrêt de l’ancien groupe de processus.
Une sonde Python de trois secondes confirme seulement qu’une nouvelle
exécution courte est suivable ; elle ne rétablit pas l’ancien handle.

Le protocole exige un arrêt vérifié avant toute nouvelle charge native.
La disposition root stoppe donc la poursuite, sans relance, suppression de
sortie, déverrouillage ou modification du produit. Reçu de décision :
`7af3f487d920f9861965fd3542a0c786d10476af051725018c2df9ce5abad07c`.
La contre-revue de l’incident et de toutes les identités porte
`b81c89c926e3037e7c13ac83c56e31f2eff32228919391df1a5708543eaa134f`.
Les 172 fichiers produit et les 549 fichiers du gel logiciel sont inchangés.

| Ensemble réservé | Référence | Candidat | Verdict documentaire |
|---|---|---|---|
| 8 positifs originaux | 8 NOT_RUN | 8 BLOCKED | Non évalué |
| 2 limites originales | 2 NOT_RUN | 2 BLOCKED | Non évalué |
| 2 positifs dérivés | 2 NOT_RUN | 2 BLOCKED | Non évalué |
| Total des positions prévues | 12 conservées | 12 conservées | Aucun score, aucune réponse observée |

Les entrées de référence existent ; aucun lancement de ses questions n’est observé. Le
candidat n’a pas de manifeste final de requêtes après ce lot interrompu et
aucun démarrage du lot dérivé n’est observé. Le blocage pour arrêt non prouvé s’applique aux
deux bras. Ces classements sont une disposition de qualification datée,
jamais des reçus fictifs du dispatcher. **Aucun résultat « 0/24 » n’est calculé.**
La [revue réservée](trust-4b-reserved-review-2026-11-09.md) conserve la matrice,
les sources, les contrôles de méthode et l’incident.

Le parcours HTTP/SSE v4 demeure **NOT_RUN**, bloqué par la même précondition.
Il n’existe aucune preuve I5 de ses imports, de sa génération, de la publication
publique ou de la conservation des anciennes citations après remplacement.
Les essais HTTP antérieurs restent historiques, sans attribution à la source 8.
Aucun navigateur ni kit neuf n’est qualifié par les tests de cette itération.

## 6. Matrice de réception I5

Les statuts ci-dessous appliquent les critères gelés ; `PARTIAL` ne vaut pas
`PASS`. Chaque preuve porte sur son code, son corpus et son environnement.

| Critère | Statut | Conclusion fondée sur les observations |
|---|---|---|
| I5-D01 — fidélité de tous les segments | **FAIL** | TMP117 contient une réserve globale injustifiée. Des chiffres et citations exacts ne suffisent pas : le critère comprend explicitement les réserves. Aucun succès réservé ou HTTP n’est ajouté. |
| I5-D02 — ingestion et géométrie | **PASS, périmètre prévu** | H01/H03/H07 correctement liés et corps utile H02 récupéré ; contrôles géométriques/couverture et provenance vérifiés. Ce statut ne qualifie pas tous les documents ni le transfert. |
| I5-D03 — complétude | **FAIL** | Développement final 12/14 positifs : SCAN2 et TMP117 échouent. Les 6/6 limites constituent un dénominateur distinct. |
| I5-D04 — OCR utile | **FAIL** | Intégrations OCR réelles 8/8, mais ancien SCAN2 incomplet ; les deux dérivés réservés ne sont pas évalués. |
| I5-D05 — non-régression | **FAIL** | Contrôlé 12/12 positifs et 16/18 limites : L11/L12 ne traversent pas le sélecteur adversarial. Office 8/8 et portes logicielles réussies ne remplacent pas ces deux critères. |
| I5-D06 — nouveau transfert | **BLOCKED** | 24 positions conservées, aucune requête observée, pas de score. Le lot d’extraction candidat est interrompu. |
| I5-D07 — exploitation et coûts | **BLOCKED** | Caps, identité 4B, ressources et arrêts du développement sont documentés. HTTP/SSE v4 est NOT_RUN et l’arrêt du dernier lot réservé n’est pas prouvé. |
| I5-D08 — reproductibilité | **PARTIAL** | Séparation, gels, ablations, matérialisation et absence d’ajustement après ouverture établis ; toutes les tentatives et positions prévues conservées. Les mesures réservées et la clôture du dernier lot manquent. |
| I5-D09 — livraison | **PASS — sources avec réserves** | Six portes documentaires réussies ; commit technique [7cd39839](https://github.com/msedki/agentPDFDoc/commit/7cd398399c98701309ace0498be3f149ae4e276d), parent/arbre/SHA distants vérifiés, publication sans force. [Reçu](trust-4b-publication-2026-11-09.json). La qualification de production reste non acquise. |

La qualification de diffusion est **non acquise**. L’installation neuve
Windows, Linux aarch64 et le poste physique CPU/16 Go restent NOT_RUN pour I5.
Les anciennes recettes, le build frontend et un catalogue conforme ne
qualifient pas ces cibles par héritage.

## 7. Priorités restant à satisfaire

1. Rétablir une autorité de sujet et de contexte structurellement prouvée pour
   les listes de prose telles que TMP117, puis obtenir une réponse complète
   sans réserve d’absence injustifiée. Ni nom de fichier ni exception dédiée
   à une fiche ne doit remplacer cette preuve.
2. Résoudre la lecture utile du scan encore ambigu, en conservant signes,
   unités, rôles et conditions, dans les mêmes bornes de ressources. Une
   abstention sûre demeure un échec positif.
3. Recevoir les frontières adversariales sur les routes réellement traversées,
   en conservant les primaires L11/L12 échoués et leur supplément distinct.
   Le critère original n’est pas réécrit après son observation.
4. Disposer d’une continuité d’exécution et d’arrêts vérifiables avant une
   nouvelle campagne native et le parcours HTTP/SSE. Toute reprise doit avoir
   des sorties neuves, conserver l’incident et ses positions primaires, et
   annoncer explicitement son statut de suivi. Aucun ajustement produit n’a
   été effectué sur les oracles désormais ouverts.
5. Recetter un paquet lié au commit livré, son installation/migration et les
   cibles natives de diffusion. Les preuves du poste de développement restent
   limitées à ce poste.

## 8. Commandes et publication

Les commandes publiques et les différences avec les pilotes privés de la
session figurent dans le [guide de reproduction](trust-4b-reproduce-2026-11-08.md).
Le commit technique [7cd39839](https://github.com/msedki/agentPDFDoc/commit/7cd398399c98701309ace0498be3f149ae4e276d) est publié sur `enhanced_version` avec pour
parent `41857e17a438fe43123e4ef8274d9d2d446bfbc2` et pour arbre
`b1fef837513eaedab1a56ffffdbef8f505a6c4a0`. Les 166 fichiers transférés ont des
empreintes Git identiques à leurs objets stagés. La lecture distante du
9 novembre 2026 à 05:07:28 UTC vérifie la branche, le parent et l’arbre ; la
mise à jour est faite sans force, avec contrôle du parent attendu. Le commit
canonique local retrouve exactement le SHA distant et le checkout est propre
après import. Le [reçu de publication](trust-4b-publication-2026-11-09.json) conserve ces identités,
les contrôles des gels et les six portes documentaires déjà réussies.

La présente clôture documentaire référence ce commit technique ; elle ne
modifie ni produit, ni tests, ni critères, ni résultats. La publication du code
reste distincte d’une release qualifiée pour la production.
