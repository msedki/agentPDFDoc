# Qualification synthétique — préparation et contrôles locaux

État au 30/09/2026 01:23 UTC : **32 PDF générés, 200 questions annotées en templates ;
aucun résultat OCR, retrieval, LLM ou E2E déduit de ces contrôles**.

Les PDF représentent 1 698 273 octets et 52 pages lisibles en comptant le PDF
chiffré avec son mot de passe public de fixture. Le fichier corrompu est le 32e
fichier et n'a aucune page lisible. Trois PDF hostiles sont séparés.
L'inventaire exact, les SHA-256 et les inspections natives sont dans
[manifest.json](manifest.json). Le contenu et les questions sont synthétiques ;
ils ne démontrent pas la qualité documentaire sur les livrets métier.

| Catégorie | Développement | Final |
|---|---:|---:|
| Factuel FR/EN | 35 | 35 |
| Identifiants techniques | 15 | 15 |
| Tableaux/unités | 12 | 12 |
| Comparaisons | 10 | 10 |
| Suivis conversationnels répondables | 8 | 8 |
| Sans réponse dans le scope | 20 | 20 |
| Total | 100 | 100 |

Familles disjointes : ateliers pneumatiques pour développement, stations
thermiques Boréal pour final. Le final comporte 80 questions répondables et
20 absences documentaires ; ses questions/valeurs ne doivent pas servir au tuning.
Les IDs de version, révision, génération et blocs restent `null` jusqu'à lecture
des artefacts d'extraction réels. Les SHA des fichiers générés sont, eux, réels.

[final.freeze.json](final.freeze.json) identifie le final par SHA-256 du JSON
canonique : `673e437138ae66a4baee730d3181012c6bf66e1d96e91c4af7a08e2a8ee546d4`.
Ce gel a été établi après ajout des empreintes de scopes, pendant préparation,
avant tout import ou tuning. La résolution future doit conserver les templates
gelés et écrire un artefact séparé.

Contrôles exécutés :

- Génération ReportLab 5.0.1 / Python 3.12, inspection structure/texte PDFium :
  [sortie génération](reports/generate-2026-09-30-rerun.log), exit 0.
- 15 tests structure/quotas/empreintes/refus et sécurité du resolver :
  [reprise corrigée](reports/unit-2026-09-30-corrected.log), exit 0, 0,284 s
  mesurées par le runner. Il s'agit de tests locaux, pas d'une latence applicative.
- Régénération séquentielle : [preuve d'octets](reports/reproducibility-2026-09-30.json),
  32 SHA comparés identiques et `final.json` identique octet pour octet.
- [Planche visuelle](reports/previews/contact-sheet.png) lue dans le client :
  table scannée de la page mixte lisible sous le paragraphe natif, deux colonnes
  distinctes, ancre visible malgré rotation/CropBox, glyphes Unicode visibles,
  scan FR/EN lisible et continuation du tableau à la page 5.
- [Préflight natif des annotations](reports/native-annotations-2026-09-30.json) :
  180 unités de preuve inspectées, 150 présentes dans le texte natif, 26 sur scans
  et 4 sur tables scannées nécessitant OCR. Aucune unité native attendue absente.
  Les offsets/SHA mesurés sont ceux du préflight PDFium, avec IDs runtime nuls ;
  ce résultat ne compte comme aucune couverture retrieval ou de contexte final.

Échecs/reprises conservés : le premier appel ReportLab avec le raccourci de style
romain `r` échouait sur `getattr('R')`; les noms documentés `ROMAN_LOWER`/`ARABIC`
fonctionnent. L'attribut `pypdfium2.V_PYPDFIUM2` absent a été remplacé par la version
du paquet via `importlib.metadata`. Le [premier test](reports/unit-2026-09-30.log)
attendait une césure extraite inchangée et a échoué : cet écart réel est décrit
ci-dessous, puis le test a été corrigé pour vérifier les octets source et signaler
la transformation. Une tentative de runner Python inline a aussi échoué à cause
du passage des guillemets par PowerShell ; le runner de fichier a été exécuté.

Limites observées et restant à qualifier :

- PDFium développe le ToUnicode U+FB01 en `fi`. La césure visible `con-` / `trole`
  devient `con` + U+0002 + `trole` dans `get_text_bounded`, et U+FFFE dans
  `get_text_range`. Le manifeste enregistre ces transformations. Un hash fidèle
  au texte du parseur ne prouve pas la conservation de tous les glyphes PDF.
- Les scans ont zéro caractère natif. Les pages mixtes gardent leur paragraphe
  natif, sans texte natif de table. Cela prouve leur composition, pas l'OCR réussi.
- Le cas taille dépasse 64 Kio : son refus exige une configuration **isolée** de
  test à 65 536 octets. Il ne valide pas la limite de production de 200 Mio et ne
  nécessite aucun changement de la configuration livrée.
- Le PDF chiffré est inspecté avec le mot de passe public `qualification-only` ;
  son ouverture sans mot de passe est refusée. L'import doit être essayé sans
  fournir ce mot de passe. Blank/corrupt/size n'ont pas été importés dans l'API.
- Les annotations d'absence proviennent du contenu source contrôlé ; une absence
  de résultat retrieval ne remplacera pas cette annotation.
- Aucun seuil D02/D04/D05/D06/D07 n'est coché par ce livrable préparatoire.

Méthode et commandes : [tools/qualification/README.md](../../tools/qualification/README.md).

Un premier import DEV natif est réellement publié dans l'API isolée : DA-P01,
2 pages / 11 blocs, couverture 2/2 et OCR 0. Le collecteur GET conserve
[les réponses exactes et leur identité](runtime/2026-09-30-DA-P01-published.json),
avec vérification du SHA original et des hashes UTF-8 du `raw_text`.
[La résolution séparée du développement](runtime/2026-09-30-development-partial.json)
compte 15 questions résolues et 85 non résolues. Ces dernières gardent leurs
sources absentes ; le dataset original et le gel final sont inchangés. Cette
preuve ne fournit aucun Recall, EvidenceCoverage ou score de génération et ne
qualifie pas le développement de 100 questions.
