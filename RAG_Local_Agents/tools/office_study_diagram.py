"""Diagramme de proposition documentaire R28, aucune implémentation Office."""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / 'reports/office-architecture-proposee.svg'
parts = ['''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 675" font-size="16" role="img" aria-labelledby="title desc">
<title id="title">Extension Office proposée, pipeline PDF préservé</title>
<desc id="desc">Originaux immuables, trois adaptateurs distincts, révisions structurées, indexation et RAG communs, lecteurs par format. Les voies DOCX et XLSX ne sont pas encore implémentées.</desc>
<rect width="1100" height="675" fill="#f8fafc" class="background"/>
<style>
svg{background:#f8fafc;color:#172e45}text{font-family:system-ui,sans-serif;fill:currentColor}
.heading{font-weight:700}.box{fill:#fff;stroke:#294766;stroke-width:1.5}
.pdf{fill:#e7f0fb;stroke:#1e5fa7}.office{fill:#e4f5f0;stroke:#146854}.shared{fill:#f0eafd;stroke:#61479a}
.line{fill:none;stroke:#465c76;stroke-width:2;marker-end:url(#arrow)}
@media(prefers-color-scheme:dark){svg{background:#121e2e;color:#edf3fa}.background{fill:#121e2e}.box{fill:#202f43;stroke:#adbed5}.pdf{fill:#163452;stroke:#7ebafa}.office{fill:#183e37;stroke:#83d9be}.shared{fill:#33274d;stroke:#c0a1fa}.line{stroke:#adbed5}}
</style>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>
<text class="heading" font-size="24" x="30" y="40">Extension DOCX/XLSX — architecture proposée</text>
<text font-size="15" x="30" y="65">Étude du 9 octobre 2026 · Office non implémenté · CPU local / Windows et GNU/Linux</text>
''']

def box(x, y, w, h, lines, kind='box'):
    parts.append(f'<rect class="box {kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="9"/>')
    for i, line in enumerate(lines):
        parts.append(f'<text x="{x+16}" y="{y+28+i*23}">{escape(line)}</text>')

def arrow(x1, y1, x2, y2):
    parts.append(f'<path class="line" d="M{x1},{y1} L{x2},{y2}"/>')

box(30, 92, 1040, 76, ['Originaux immuables : SHA-256 · document / version · format validé',
                        'PDF : contrôle existant     |     DOCX / XLSX : préflight ZIP/OPC + quotas + XML sans DTD/réseau'])
for x, kind, lines in [
    (30, 'pdf', ['PDF actuel préservé', 'Docling / PDFium / OCR', 'Page + bbox + texte exact']),
    (390, 'office', ['DOCX proposé', 'python-docx + OOXML borné', 'Partie + élément + offsets']),
    (750, 'office', ['XLSX proposé', 'openpyxl + OOXML streaming', 'Feuille + cellules / plages'])
]:
    arrow(x+160, 168, x+160, 205)
    box(x, 207, 320, 102, lines, kind)
    arrow(x+160, 309, x+160, 350)
box(30, 352, 1040, 81, ['Révisions structurées : blocs / tableaux / cellules typées · localisateurs par format',
                        'Texte d’indexation dérivé + bindings sources · couverture / avertissements · checkpoints'], 'shared')
arrow(550, 433, 550, 457)
box(30, 459, 1040, 81, ['Socle commun : SQLite + FTS5 / E5 CPU / Qdrant · publication atomique',
                        'Scopes avant top-k et contexte · Ollama local · citations immuables version / révision'], 'shared')
arrow(550, 540, 550, 564)
box(30, 566, 1040, 76, ['Même poste documentaire : import / bibliothèque / recherche / questions / comparaison',
                        'Lecteur PDF.js actuel     |     DOCX structuré React     |     XLSX par fenêtres bornées'])
parts.append('</svg>\n')
OUT.write_text('\n'.join(parts), encoding='utf-8')
print(OUT)
