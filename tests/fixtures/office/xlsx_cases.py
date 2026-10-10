"""Generated, annotated OOXML packages: no private document or binary fixture.

These are real ZIP/OPC workbooks. Deliberately stale formula cache C4=1
contradicts B2+B3; calcPr requests recalculation but cannot prove freshness.
"""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

TRANSITIONAL = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
STRICT = "http://purl.oclc.org/ooxml/spreadsheetml/main"
TRANSITIONAL_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
STRICT_REL = "http://purl.oclc.org/ooxml/officeDocument/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _relations(namespace, records):
    body = "".join(f'<Relationship Id="{identifier}" Type="{namespace}/{kind}" Target="{target}"'
                   f'{" TargetMode=" + chr(34) + "External" + chr(34) if external else ""}/>'
                   for identifier, kind, target, external in records)
    return f'<Relationships xmlns="{PACKAGE_REL}">{body}</Relationships>'


def workbook_parts(*, strict=False, date1904=False):
    ns = STRICT if strict else TRANSITIONAL
    rel = STRICT_REL if strict else TRANSITIONAL_REL
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/tables/table1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
        '<Override PartName="/xl/comments1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '</Types>',
        "_rels/.rels": _relations(rel, [("rMain", "officeDocument", "xl/workbook.xml", False),
                                        ("rCore", "metadata/core-properties", "docProps/core.xml", False)]),
        "xl/_rels/workbook.xml.rels": _relations(rel, [("r1", "worksheet", "worksheets/sheet1.xml", False),
            ("r2", "worksheet", "worksheets/sheet2.xml", False), ("rStyles", "styles", "styles.xml", False),
            ("rStrings", "sharedStrings", "sharedStrings.xml", False), ("rMetadata", "sheetMetadata", "metadata.xml", False)]),
        "xl/workbook.xml": f'<workbook xmlns="{ns}" xmlns:r="{rel}">'
        f'<workbookPr date1904="{int(date1904)}"/><sheets>'
        '<sheet name="Budget été" sheetId="1" state="visible" r:id="r1"/>'
        '<sheet name="Historique" sheetId="7" state="veryHidden" r:id="r2"/></sheets>'
        '<definedNames><definedName name="BudgetRange" localSheetId="0">\'Budget été\'!$A$1:$C$4</definedName>'
        '<definedName name="ExternalName">\'[other.xlsx]Data\'!$B$2</definedName></definedNames>'
        '<calcPr calcId="42" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>',
        "xl/sharedStrings.xml": f'<sst xmlns="{ns}" count="1" uniqueCount="1"><si>'
        '<r><rPr><b/></rPr><t xml:space="preserve">Projet </t></r><r><t>alpha</t></r>'
        '<rPh sb="0" eb="6"><t>not-visible-phonetics</t></rPh></si></sst>',
        "xl/styles.xml": f'<styleSheet xmlns="{ns}"><numFmts count="1">'
        '<numFmt numFmtId="164" formatCode="[hh]:mm:ss"/></numFmts>'
        '<cellXfs count="3"><xf numFmtId="0"/><xf numFmtId="14"><alignment horizontal="right"/></xf>'
        '<xf numFmtId="164"/></cellXfs></styleSheet>',
        "xl/worksheets/_rels/sheet1.xml.rels": _relations(rel, [("rTable", "table", "../tables/table1.xml", False),
            ("rComment", "comments", "../comments1.xml", False),
            ("rExternal", "hyperlink", "https://example.invalid/private-external", True)]),
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{ns}" xmlns:r="{rel}"><dimension ref="A1"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews><cols><col min="2" max="2" hidden="1" width="12"/></cols>'
        '<sheetData><row r="1">'
        '<c r="A1" t="inlineStr"><is><t>Item</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Amount</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Formula</t></is></c></row>'
        '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="B2"><v>9007199254740993</v></c>'
        '<c r="C2"><f>B2*2</f><v>18014398509481986</v></c></row>'
        '<row r="3" hidden="1"><c r="A3" t="inlineStr"><is><t></t></is></c><c r="B3"><v>0</v></c>'
        '<c r="C3"><f>B3*2</f><v/></c></row>'
        '<row r="4"><c r="A4" t="inlineStr"><is><t>erreur</t></is></c><c r="B4" t="e"><v>#DIV/0!</v></c>'
        '<c r="C4"><f>SUM(B2:B3)</f><v>1</v></c></row>'
        '<row r="5"><c r="A5" t="b"><v>0</v></c><c r="B5" s="1"><v>60</v></c>'
        '<c r="C5" t="d"><v>2026-10-09T12:30:00Z</v></c></row>'
        '<row r="6"><c r="A6"><f t="shared" si="2" ref="A6:A7">B6+$B$2</f><v>5</v></c>'
        '<c r="B6"><f t="array" ref="B6:B7">ROW(B6:B7)</f><v>6</v></c>'
        '<c r="C6" cm="1"><f t="array" ref="C6:C7">_xlfn._xlws.FILTER(B2:B4,B2:B4&gt;0)</f><v>42</v></c></row>'
        '<row r="7"><c r="A7"><f t="shared" si="2"/><v>6</v></c><c r="B7"><v>7</v></c>'
        '<c r="C7"><v>43</v></c></row><row r="8"><c r="B8" s="2"><v>2.5</v></c></row>'
        '<row r="9"><c r="A9" t="str"><v></v></c></row>'
        '<row r="1048576"><c r="XFD1048576" t="inlineStr"><is><t>extrême</t></is></c></row></sheetData>'
        '<mergeCells count="1"><mergeCell ref="A10:C10"/></mergeCells><autoFilter ref="A1:C4"/>'
        '<hyperlinks><hyperlink ref="A2" r:id="rExternal"/><hyperlink ref="A4" location="Historique!A1"/></hyperlinks>'
        '<tableParts count="1"><tablePart r:id="rTable"/></tableParts></worksheet>',
        "xl/worksheets/sheet2.xml": f'<worksheet xmlns="{ns}"><sheetData><row r="1">'
        '<c r="A1" t="inlineStr"><is><t>2025</t></is></c><c r="B1"><f>\'Budget été\'!B2</f><v>12</v></c>'
        '<c r="C1"><f>\'[other.xlsx]Data\'!B2</f><v>19</v></c></row></sheetData></worksheet>',
        "xl/tables/table1.xml": f'<table xmlns="{ns}" id="3" name="BudgetTable" displayName="BudgetTable" ref="A1:C4" headerRowCount="1">'
        '<autoFilter ref="A1:C4"/><tableColumns count="3"><tableColumn id="1" name="Item"/>'
        '<tableColumn id="2" name="Amount"/><tableColumn id="3" name="Formula"><calculatedColumnFormula>B2*2</calculatedColumnFormula>'
        '</tableColumn></tableColumns><tableStyleInfo name="TableStyleMedium2" showRowStripes="1"/></table>',
        "xl/comments1.xml": f'<comments xmlns="{ns}"><authors><author>Fixture author</author></authors><commentList>'
        '<comment ref="B2" authorId="0"><text><r><t>Vérifier le budget.</t></r></text></comment>'
        '<comment ref="D20" authorId="0"><text><t>Commentaire sans cellule source.</t></text></comment>'
        '</commentList></comments>',
        "xl/metadata.xml": f'<metadata xmlns="{ns}" xmlns:da="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">'
        '<metadataTypes count="1"><metadataType name="XLDAPR" minSupportedVersion="120000"/></metadataTypes>'
        '<futureMetadata name="XLDAPR" count="1"><bk><extLst><ext uri="fixture"><da:dynamicArrayProperties fDynamic="1" fCollapsed="0"/>'
        '</ext></extLst></bk></futureMetadata><cellMetadata count="1"><bk><rc t="1" v="0"/></bk></cellMetadata></metadata>',
        "docProps/core.xml": '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Budget fixture</dc:title><dc:creator>Fixture author</dc:creator></cp:coreProperties>',
    }
    return parts


def write_workbook(path: Path, *, parts=None, strict=False, date1904=False):
    parts = workbook_parts(strict=strict, date1904=date1904) if parts is None else parts
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text.encode("utf-8") if isinstance(text, str) else text)
    return path


def sparse_workbook(path: Path, *, present_cells=1000):
    parts = workbook_parts()
    cells = "".join(f'<row r="{index + 1}"><c r="A{index + 1}"><v>{index}</v></c></row>'
                    for index in range(present_cells))
    parts["xl/worksheets/sheet1.xml"] = f'<worksheet xmlns="{TRANSITIONAL}"><dimension ref="A1:XFD1048576"/>'
    parts["xl/worksheets/sheet1.xml"] += f'<sheetData>{cells}</sheetData></worksheet>'
    return write_workbook(path, parts=parts)
