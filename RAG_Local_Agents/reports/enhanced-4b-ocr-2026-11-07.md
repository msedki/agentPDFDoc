# EV4B — reprise OCR des champs numériques : résultat négatif et contrôles acquis

**Rôle :** compte rendu des essais OCR de composant · **Propriétaire :** ingestion et qualification EV4B · **Statut :** tests de politique acquis ; récupération native du zéro non acquise · **Date :** 2026-11-07 (UTC) · **Référence :** base `59d47e98` et modifications locales `enhanced_version` · **Source de vérité :** [mesures et empreintes](enhanced-4b-ocr-results-2026-11-07.json), sorties brutes identifiées par leurs SHA-256 et [pilote reproductible](../../tools/qualification/enhanced_ocr_smoke.py).

## Résultat

**Tesseract lit encore « OV » sur l'image synthétique portant « 0 V ».** La
reprise de rangée à densité native puis l'unique variante ×2 n'ont pas récupéré
le zéro. La version implémentée conserve cette ambiguïté, son image et ses deux
lectures ; elle n'invente pas une valeur corrigée. Le dérivé ×2 reste une option
du pilote d'essai ; la reprise nominale conserve la densité native.

| Cas | Nature de la baseline | Densité native | Variante ×2 | Révision finale, densité native |
|---|---|---|---|---|
| Tableau synthétique « Min / Max ; 0 V / 36 V » | Quatre lectures Tesseract réellement exécutées | FAIL : OV conservé | FAIL : OV conservé | FAIL : OV conservé |
| Reprise du champ minimum avec baseline OV | Ambiguïté injectée, candidat produit par Tesseract réel | FAIL : récupération non acquise | FAIL : récupération non acquise | FAIL : récupération non acquise |
| Conflit entre baseline OV et image portant 0 A | Baseline injectée, candidat produit par Tesseract réel | PASS : rejet, ambiguïté conservée | PASS : rejet, ambiguïté conservée | PASS : rejet, ambiguïté conservée |

Chaque campagne comprend **3 contrôles, dont 1 réussi et 2 échoués**, et 7 appels
natifs Tesseract : 4 lectures de cellules, puis une reprise de rangée par cas.
Les deux critères de récupération ne sont pas deux documents indépendants.
Les campagnes successives ne sont pas additionnées pour annoncer une nouvelle
taille de corpus.

Les temps cumulés des seuls sous-processus OCR sont respectivement **0,706 s**,
**0,608 s** et **0,591 s**. Ces valeurs décrivent les exécutions observées ; trois
petits essais ne démontrent pas un gain de latence. Elles n'incluent ni Docling,
ni recherche, ni modèle 4B, ni consommation mémoire de l'application complète.

## Mécanisme implémenté

Les colonnes numériques sont établies par des entêtes littéraux `min`, `max`,
`typ` et leurs variantes explicites, reconnus dans la même grille et alignés
géométriquement. Un champ de code ou un texte libre contenant O ne suffit pas à
déclencher une reprise. Le mécanisme traite une ambiguïté O/0 dans un littéral
numérique, ou un tiret long placé devant le nombre ; il ne peut pas détecter
toute erreur OCR ni un signe déjà disparu sans indice.

La reprise réutilise Tesseract, la langue, PSM 6 et le seuil 0,8. Elle respecte
les limites existantes de rangée : 2048×128 pixels, encre ≤48 pixels, budget de
pixels cumulé et au plus 32 appels supplémentaires par région. Une cellule
déjà reprise par la politique mono-glyphe empêche le cumul d'une seconde
tentative sur sa rangée. Le candidat doit avoir des confiances et boîtes
recevables, rester dans les cellules et confirmer les voisines déjà admissibles.
Ses unités, signes et chiffres non ambigus doivent rester cohérents avec la
lecture initiale. Aucune sortie n'est fabriquée par remplacement lexical.

La variante expérimentale ×2 ne concerne que les lignes numériques ambiguës
d'encre ≤24 pixels. Elle contrôle les dimensions finales et les allocations
avant resize, conserve l'inverse des coordonnées et ne crée pas un deuxième
appel. Son absence de gain sur cet essai justifie sa non-promotion.

Le texte brut, les tokens candidats, les cadres, les paramètres, la décision
et le crop PNG réellement fourni au moteur sont conservés dans
`ocr_numeric_readings`, séparément des traces opérationnelles dépourvues de texte.
La capture d'image est plafonnée à 256 Kio par rangée et 2 Mio par région ;
un dépassement est signalé `snapshot_byte_limit`. Une ambiguïté persistante est
publiée comme région `OCR_NUMERIC_AMBIGUITY`. L'identité d'extraction change grâce
aux hashes des sources d'ingestion ; une ancienne extraction n'est pas présentée
comme résultat de la nouvelle politique.

Ce déclenchement intervient pendant l'ingestion des grilles. **La reprise OCR
à la demande d'une question n'est pas intégrée dans ce lot.** Les données
historiques employées par une autre expérience doivent donc rester explicitement
identifiées comme extraction figée.

## Vérifications et conditions

- Suite ciblée finale : **201 PASS** = 170 tests OCR/provenance et 31 tests de
  l'évaluateur ; une dépréciation pandas préexistante sur une concaténation vide.
  Preuve : `.runtime/qa/ev4b-ocr-eval-unit-03.xml`. Les tests OCR de cette suite
  utilisent des doubles nommés ; ils ne sont pas des scores de reconnaissance.
- Un passage intermédiaire a produit 200 PASS et un échec d'attente du motif de
  refus : le budget choisi atteignait le plafond d'un crop avant le plafond
  cumulé. Le test a été ajusté pour exercer réellement ce second plafond, sans
  changer les gardes du produit. Le XML du passage reste conservé.
- Ruff passe sur les modules et nouveaux tests modifiés. Mypy passe sur les
  trois nouveaux modules avec dépendances non suivies. Le typage transversal de
  l'ancien adaptateur n'est pas déclaré acquis : Docling est absent et l'inférence
  du type `table_model` reste indéterminée dans cet environnement.
- Moteur réel : **Tesseract 5.5.0**, langue `eng`, exécuté sur Linux ; le projet
  possède également un verrou Tesseract 5.4.0, non assimilé à cet essai. Police
  locale OpenSans-Regular, 30 pixels. Les hashes moteur/police et des résultats
  sont dans le JSON lié en tête.

Commandes du dernier contrôle :

```bash
python -m pytest tests/unit/test_ingestion_numeric_evidence.py \
  tests/unit/test_ingestion_ocr_row_context.py \
  tests/unit/test_ingestion_regional_grid.py \
  tests/unit/test_ingestion_provenance.py \
  tests/unit/test_qualification_enhanced_eval.py -q
python tools/qualification/enhanced_ocr_smoke.py \
  --font /usr/share/fonts/truetype/open-sans/OpenSans-Regular.ttf \
  --numeric-density-factor 1 \
  --output .runtime/qa/ev4b-ocr-native-03-final-default
```

Un nouveau rejeu doit employer un nouveau dossier de sortie. L'option
`--numeric-density-factor 2` expose la seule variante testée. Le pilote rend un
code non nul lorsque ses critères de récupération échouent ; le refus correct
d'une ambiguïté ne masque pas cet échec.

## Portée de la réception

Acquis : politique bornée, conservation des lectures et régions, garde des codes
et unités, géométrie inverse, refus traçable et reproduction d'une limite native.
Non acquis : récupération de « 0 V » dans cet exemple, gain d'exactitude OCR,
extraction PDF complète avec Docling, déclenchement OCR lié à une question,
qualification Windows et généralisation à d'autres documents ou polices.
