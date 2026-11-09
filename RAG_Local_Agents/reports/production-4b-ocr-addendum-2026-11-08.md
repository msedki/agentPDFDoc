# I4 — expérience corrective OCR avant gel final

**Rôle :** décision expérimentale complémentaire, sans modification des critères.
**Propriétaire :** intégration RAG. **Date :** 8 novembre 2026, UTC.
**Statut initial :** fixé avant la compilation du correctif natif et ses essais.
Le [protocole I4](production-4b-protocol-2026-11-08.md) conserve son empreinte
et ses critères D01–D10. Ce document consigne un défaut nouvellement exécuté.

## Observation discriminante

Les poids Docling et tessdata ont été vérifiés contre le verrou. La construction
utilisateur de Tesseract 5.4.0 avec Leptonica 1.87.0 a passé les contrôles de
version, de bibliothèques dynamiques, d'absence de RPATH et de chemins de build.
Le binaire initial a pour SHA-256
`d6433dab06f0c58ff3536560b208e92c156664f7fe48210f00f7a17f75e0c3ac`.

Le vrai module d'intégration OCR du worktree `fa3eabc` termine avec **5 FAIL et
3 PASS** en 150,85 s : sept contrôles OCR et un contrôle de police. Il n'est plus
ignoré faute de modèles. Les cas en échec s'arrêtent à l'orientation non résolue,
avant les reconnaissances de cellules ; le worker conserve `ready_partial`.

Une seule sonde du raster exact du premier cas, reconstruit et contrôlé au SHA-256
`a5b899ec216980cc14d3e074e405524b5bdcdede1540e2012c30fecf24b70f53`,
donne un arrêt **SIGFPE, code −8**, en 0,435 s. Le modèle `osd` est conforme au
verrou. Une seconde sonde isolant le chemin SIMD par l'option amont
`DOTPRODUCT=generic` produit le même signal, en 0,300 s. Aucun seuil de confiance,
angle ou texte attendu n'a été modifié. Les deux reçus restent distincts sous
`.runtime/qa/production-i4-20261108/ocr-osd-diagnostic/`.

## Hypothèse et modification limitée

Le [défaut amont Tesseract #4257](https://github.com/tesseract-ocr/tesseract/issues/4257)
décrit une exception flottante dans la normalisation du classifieur historique
de 5.4.0. Le correctif amont PR4259 traite l'absence de prototypes avant de calculer
leur score. L'attribution de notre arrêt à cette cause reste une hypothèse tant
que l'ablation n'a pas réussi sur le raster conservé.

Appliquer uniquement le correctif amont vérifié, avec commit, fichier, empreintes
avant/après et reçu de compilation. Les archives sources originales restent
inchangées. Le binaire corrigé sera identifié comme **5.4.0 avec correctif amont**,
et son manifeste devra distinguer cet état de 5.4.0 sans correctif. Le contrôle de
réutilisation refusera un ancien manifeste ne portant pas le correctif requis.
Les exceptions flottantes restent activées ; aucune orientation zéro n'est déduite
d'un arrêt ou d'une réponse illisible.

## Essai prévu et acceptation inchangée

1. Conserver le binaire/manifeste initiaux et la totalité des échecs OCR.
2. Recompiler seulement l'objet affecté dans la construction déjà vérifiée pour
   isoler le correctif : mêmes compilateur, options, Leptonica, bibliothèques,
   tessdata, image et commande. La recette de construction neuve appliquera le
   même correctif vérifié avant compilation.
3. Exécuter une sonde sur le raster conservé. Un arrêt normal et un résultat
   d'orientation recevable par les seuils existants sont nécessaires, sans être
   une preuve suffisante de qualité OCR.
4. Rejouer les sept vrais contrôles OCR et le contrôle de police, dans un nouveau
   dossier de preuve. Les nombres, signes, unités, cellules, conditions et boîtes
   doivent satisfaire les assertions originales. Tout échec persistant reste
   un échec de D05 et devra être expliqué, sans correction lexicale par attendu.
5. Exécuter ensuite les deux scans de transfert seulement après le gel final du
   produit. Aucune sortie du transfert ne sera utilisée pour régler ce correctif.

Cette intervention porte sur le moteur OCR, pas sur le générateur : le modèle
Qwen3-4B, sa quantification, les poids d'extraction/embedding et les budgets restent
inchangés. La comparaison OCR isolée et la comparaison applicative seront publiées
séparément ; les sorties initiales ne seront pas remplacées par leur reprise.
