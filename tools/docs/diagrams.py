"""Schémas SVG de la documentation stabilisée, générés sans réseau ni dépendance externe.

Depuis la racine du dépôt :

    .venv\\Scripts\\python.exe tools/docs/diagrams.py          écrit docs/assets/diagrams/*.svg
    .venv\\Scripts\\python.exe tools/docs/diagrams.py --check  compare sans écrire (code 1 si écart)
    .venv/bin/python tools/docs/diagrams.py                  écrit docs/assets/diagrams/*.svg
    .venv/bin/python tools/docs/diagrams.py --check          compare sans écrire (code 1 si écart)

Chaque valeur affichée provient du code ou de la configuration cités dans docs/ ; modifier
ce script puis régénérer, jamais les SVG à la main. La sortie est déterministe (LF, sans date).
Le fond est explicite pour rester lisible dans les thèmes clair et sombre ; les polices sont
locales au poste. Un texte dont la largeur estimée dépasse son cadre lève ValueError.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "assets" / "diagrams"

WIDTH = 880
MIN_FONT = 12
SANS = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
MONO = "Consolas, 'Cascadia Mono', 'DejaVu Sans Mono', monospace"
# Largeur moyenne d'un caractère rapportée à la taille de police : estimation prudente.
CHAR_RATIO = {"sans": 0.57, "mono": 0.61}

INK = "#172B33"
MUTED = "#4A5961"
PAPER = "#F6F4EE"
FRAME = "#D9D9D1"
LIFELINE = "#8E989D"
# (remplissage, contour) : le texte reste à l'encre sur tous les remplissages.
TONES = {
    "client": ("#FFFEFA", "#172B33"),
    "process": ("#E4F0EA", "#2D6950"),
    "service": ("#E3EEF6", "#1F5F8B"),
    "storage": ("#EFEDE6", "#6B6456"),
    "model": ("#ECE8F5", "#5B4B8A"),
    "refusal": ("#F8E9DF", "#A94324"),
    "note": ("#FFF6D9", "#8A6D1F"),
    "group": ("#FBFAF6", "#2D6950"),
}
NETWORK = "#1F5F8B"
PROCESS = "#2D6950"
FILES = "#6B6456"
FLOW = "#172B33"
REFUSAL = "#A94324"
DASHES = {"solid": None, "dashed": "7 5", "dotted": "2 4"}


def text_width(value: str, size: float, family: str = "sans") -> float:
    return len(value) * size * CHAR_RATIO[family]


class Diagram:
    def __init__(self, name: str, height: int, title: str, desc: str):
        self.name, self.height, self.title, self.desc = name, height, title, desc
        self.body: list[str] = []
        self.colors: set[str] = set()
        self.lowest = 0.0

    # -- primitives -------------------------------------------------------------------------
    def fit(self, value: str, size: float, family: str, width: float) -> None:
        if text_width(value, size, family) > width:
            raise ValueError(f"{self.name} : texte trop long pour {width:.0f} px : {value!r}")

    def text(self, x: float, y: float, value: str, *, size: int = 13, weight: str = "normal",
             family: str = "sans", anchor: str = "start", fill: str = INK,
             max_width: float | None = None) -> None:
        if size < MIN_FONT:
            raise ValueError(f"{self.name} : police {size} px inférieure au minimum {MIN_FONT} px")
        if any(ord(char) < 32 for char in value):
            # Garde contre un antislash non doublé (« \r », « \t ») dans un chemin Windows du script.
            raise ValueError(f"{self.name} : caractère de contrôle dans le texte : {value!r}")
        if max_width is not None:
            self.fit(value, size, family, max_width)
        if not 16 <= x <= WIDTH - 16:
            raise ValueError(f"{self.name} : texte hors cadre : {value!r}")
        self.lowest = max(self.lowest, y)
        attributes = [f'x="{x:g}"', f'y="{y:g}"', f'font-size="{size}"', f'fill="{fill}"']
        if weight != "normal":
            attributes.append(f'font-weight="{weight}"')
        if family == "mono":
            attributes.append(f'font-family="{MONO}"')
        if anchor != "start":
            attributes.append(f'text-anchor="{anchor}"')
        self.body.append(f"<text {' '.join(attributes)}>{escape(value)}</text>")

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: str, *,
             rx: float = 6, dash: str | None = None, width: float = 1.4) -> None:
        dashed = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" '
                         f'fill="{fill}" stroke="{stroke}" stroke-width="{width:g}"{dashed}/>')

    def line(self, points: list[tuple[float, float]], color: str, style: str = "solid", *,
             arrow: bool = True, width: float = 1.6) -> None:
        dash = DASHES[style]
        path = " ".join(f"{x:g},{y:g}" for x, y in points)
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        if style == "dotted":
            extra += ' stroke-linecap="round"'
        if arrow:
            self.colors.add(color)
            extra += f' marker-end="url(#{self.marker(color)})"'
        self.body.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="{width:g}"{extra}/>')

    def marker(self, color: str) -> str:
        return f"{self.name}-head-{color.lstrip('#').lower()}"

    def label(self, x: float, y: float, value: str, *, size: int = 12, anchor: str = "start",
              fill: str = INK, family: str = "sans", limit: float = WIDTH - 16) -> float:
        """Texte sur fond papier (lisible au-dessus des lignes de vie) ; renvoie son bord droit."""
        width = text_width(value, size, family)
        left = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
        if left < 16 or left + width > limit:
            raise ValueError(f"{self.name} : étiquette hors cadre : {value!r}")
        self.rect(left - 3, y - size, width + 6, size + 5, PAPER, PAPER, rx=2, width=0)
        self.text(x, y, value, size=size, anchor=anchor, fill=fill, family=family)
        return left + width

    # -- composants -------------------------------------------------------------------------
    def box(self, x: float, y: float, w: float, h: float, tone: str, title: str | None,
            lines: list[str] | tuple[str, ...] = (), *, mono: tuple[int, ...] = (), size: int = 13,
            title_size: int = 14, dash: str | None = None) -> None:
        fill, stroke = TONES[tone]
        self.rect(x, y, w, h, fill, stroke, dash=dash)
        inner = w - 20
        baseline = y + 21
        if title:
            self.text(x + 10, baseline, title, size=title_size, weight="600", max_width=inner)
            baseline += 19
        for index, value in enumerate(lines):
            family = "mono" if index in mono else "sans"
            self.text(x + 10, baseline, value, size=size, family=family, max_width=inner)
            baseline += size + 5
        if baseline - size - 5 + 10 > y + h:
            raise ValueError(f"{self.name} : contenu plus haut que le cadre « {title} »")

    def heading(self, subtitle: str) -> None:
        self.text(24, 34, self.title, size=18, weight="600", max_width=WIDTH - 48)
        self.text(24, 54, subtitle, size=12, fill=MUTED, max_width=WIDTH - 48)

    def legend(self, y: float, lines: list[str]) -> None:
        for index, value in enumerate(lines):
            self.text(24, y + index * 18, value, size=12, fill=MUTED, max_width=WIDTH - 48)

    def render(self) -> str:
        if self.lowest > self.height - 10:
            raise ValueError(f"{self.name} : texte sous le bas du cadre ({self.lowest:g} > {self.height - 10})")
        markers = "".join(
            f'<marker id="{self.marker(color)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="10" '
            f'markerHeight="10" markerUnits="userSpaceOnUse" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>' for color in sorted(self.colors))
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<!-- Généré par tools/docs/diagrams.py : modifier le script puis régénérer. -->",
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{self.height}" '
            f'viewBox="0 0 {WIDTH} {self.height}" role="img" aria-labelledby="{self.name}-title {self.name}-desc" '
            f'font-family="{SANS}">',
            f'<title id="{self.name}-title">{escape(self.title)}</title>',
            f'<desc id="{self.name}-desc">{escape(self.desc)}</desc>',
            f"<defs>{markers}</defs>",
            f'<rect x="0" y="0" width="{WIDTH}" height="{self.height}" rx="10" fill="{PAPER}" stroke="{FRAME}"/>',
            *self.body,
            "</svg>",
        ]
        return "\n".join(lines) + "\n"


class Sequence(Diagram):
    """Diagramme de séquence : participants en tête, étapes empilées avec hauteur variable."""

    def __init__(self, *args, top: int = 70, **kwargs):
        super().__init__(*args, **kwargs)
        self.top = top
        self.centers: dict[str, float] = {}

    def participants(self, items: list[tuple[str, str, str, float, float]]) -> None:
        for key, title, subtitle, center, width in items:
            self.centers[key] = center
            self.box(center - width / 2, self.top, width, 46, "client" if key == "user" else "service", None)
            self.text(center, self.top + 19, title, size=13, weight="600", anchor="middle", max_width=width - 12)
            self.text(center, self.top + 37, subtitle, size=12, anchor="middle", fill=MUTED, max_width=width - 12)

    def lifelines(self, bottom: float) -> None:
        for center in self.centers.values():
            self.body.insert(0, f'<line x1="{center:g}" y1="{self.top + 46}" x2="{center:g}" y2="{bottom:g}" '
                                f'stroke="{LIFELINE}" stroke-width="1" stroke-dasharray="4 4"/>')

    def message(self, y: float, source: str, target: str, value: str, *, style: str = "solid",
                color: str = FLOW, limit: float = WIDTH - 16) -> float:
        x1, x2 = self.centers[source], self.centers[target]
        step = 6 if x2 > x1 else -6
        self.line([(x1 + step, y), (x2 - step, y)], color, style)
        return self.label(min(x1, x2) + 10, y - 6, value, limit=limit)

    def self_step(self, y: float, owner: str, value: str, *, side: str = "right",
                  limit: float = WIDTH - 16) -> float:
        center = self.centers[owner]
        self.rect(center - 5, y - 11, 10, 16, "#FFFEFA", FLOW, rx=2, width=1.2)
        if side == "right":
            return self.label(center + 12, y + 1, value, limit=limit)
        self.label(center - 12, y + 1, value, anchor="end", limit=limit)
        return center


# -- (a) processus et ports ------------------------------------------------------------------

def processes() -> Diagram:
    d = Diagram("processus-ports", 800, "Processus, ports et stockage du poste",
                "Navigateur, superviseur, API FastAPI, Qdrant, Ollama, worker PDF et dossier .runtime ; "
                "tous les services écoutent sur 127.0.0.1.")
    d.heading("Profil config/local16.yaml ; lancement par services/runtime/supervisor.py, "
              "API par services/runtime/api_entry.py.")
    d.box(24, 72, 400, 90, "client", "Navigateur du poste",
          ["http://127.0.0.1:8785/workspace/", "Interface statique Next.js + PDF.js,",
           "servie par l'API (aucun serveur Next.js)"], mono=(0,))
    d.box(456, 72, 400, 90, "client", "Opérateur : PowerShell 5.1",
          [".\\rag.ps1 up | open | status | logs | down", "provision · doctor · backup · verify · restore",
           "entrée : services.runtime.cli"], mono=(0,))
    d.box(456, 184, 400, 60, "process", "Superviseur (cli _serve)",
          ["Job Object Windows, verrou control/runtime.lock"])
    d.line([(656, 162), (656, 182)], PROCESS, "dashed")
    d.rect(24, 270, 832, 324, TONES["group"][0], TONES["group"][1], dash="7 5")
    d.text(40, 292, "Processus possédés par le superviseur : lancés sans fenêtre, arrêtés de façon ciblée",
           size=13, weight="600", fill=PROCESS, max_width=800)
    d.line([(656, 244), (656, 268)], PROCESS, "dashed")
    d.label(664, 262, "lance, surveille, arrête")
    d.box(48, 304, 380, 112, "service", "API FastAPI + interface statique",
          ["uvicorn, 1 worker · 127.0.0.1:8785", "REST /api/v1 et SSE des questions",
           "Host/Origin loopback, session ou jeton exigés", "SQLite : .runtime/data/app.sqlite3"])
    d.line([(224, 162), (224, 302)], NETWORK)
    d.label(232, 212, "HTTP 8785, même origine", limit=440)
    d.box(48, 462, 240, 112, "service", "Qdrant 1.19.1",
          ["127.0.0.1:6333 (HTTP)", "gRPC et télémétrie coupés", "clé d'API par démarrage",
           "pdf_chunks_e5small_v1"], mono=(3,))
    d.box(312, 462, 250, 112, "model", "Ollama 0.35.0",
          ["127.0.0.1:11434", "llama-server : port loopback", "attribué par Ollama",
           "Modèle du profil, CPU ou GPU"], mono=(3,))
    d.box(586, 462, 246, 112, "process", "Worker Docling/Tesseract",
          ["processus Python à la demande", "aucun port réseau", "échanges par fichiers JSON",
           "(requête, résultat, fenêtres)"])
    d.line([(168, 416), (168, 460)], NETWORK)
    d.label(176, 443, "HTTP REST")
    d.line([(380, 416), (380, 460)], NETWORK)
    d.label(388, 443, "HTTP /api/chat")
    d.line([(428, 360), (709, 360), (709, 460)], PROCESS, "dashed")
    d.label(478, 354, "sous-processus")
    d.box(24, 626, 832, 92, "storage", ".runtime/ (non versionné)",
          ["data/ : app.sqlite3, originals/, extractions/, control/, logs/<instance>/, qdrant/",
           "models/ : ollama, e5-small-int8, tokenizer Qwen choisi, docling, tessdata",
           "bin/ : qdrant-1.19.1, ollama-0.35.0, tesseract-5.4.0 · manifests/ : empreintes"])
    d.line([(168, 574), (168, 624)], FILES, "dotted")
    d.line([(437, 574), (437, 624)], FILES, "dotted")
    d.line([(709, 574), (709, 624)], FILES, "dotted")
    d.legend(742, ["Trait plein : requête HTTP sur 127.0.0.1 · tirets : lancement et propriété de processus "
                   "· pointillés : fichiers.",
                   "Aucun service n'écoute hors loopback ; le navigateur ne joint ni Qdrant ni Ollama.",
                   "Hors santé et disponibilité, /api/v1 exige la session ouverte par rag.ps1 open ou le jeton "
                   "de contrôle (W011)."])
    return d


# -- (b) séquence rag.ps1 up -----------------------------------------------------------------

def startup() -> Diagram:
    d = Sequence("sequence-up", 860, "rag.ps1 up puis open : démarrage, ouverture de l'atelier et refus",
                 "Contrôles exécutés par rag.ps1 up dans l'ordre du code, lancement de Qdrant et d'Ollama, décision du "
                 "mode de génération (GPU ou CPU), lancement de l'API, puis demande du lien d'ouverture par rag.ps1 "
                 "open, et message renvoyé par chaque refus.")
    d.heading("Sources : rag.ps1, services/runtime/cli.py (open_workspace), "
              "services/runtime/supervisor.py (start, supervise).")
    right = 524
    d.participants([("user", "rag.ps1 · CLI", "start · open", 80, 112),
                    ("sup", "Superviseur", "cli _serve", 196, 100),
                    ("qdrant", "Qdrant", "6333", 296, 76),
                    ("ollama", "Ollama", "11434", 384, 76),
                    ("api", "API", "8785", 470, 70)])
    d.text(right, 88, "Refus bloquant (message du code)", size=13, weight="600", fill=REFUSAL)
    d.text(right, 106, "aucun processus étranger n'est arrêté", size=12, fill=MUTED)
    steps = [
        ("self", "user", "Environnement .venv du projet présent",
         ["Environnement isolé absent. Exécuter", "bootstrap.ps1 (…), puis rag.ps1 provision."]),
        ("self", "user", "Profil v2 : app.host 127.0.0.1",
         ["Profil version2 requis", "Le runtime exige loopback"]),
        ("self", "user", "llm.accelerator auto, cpu ou gpu ; ancien num_gpu 0",
         ["llm.accelerator accepte auto (…), cpu (…) ou…", "llm.num_gpu est remplacé par llm.accelerator…",
          "llm.num_gpu n'accepte que 0 (…) ; …"]),
        ("self", "user", "URL de Qdrant et d'Ollama : 127.0.0.1, port explicite",
         ["Les services natifs exigent une URL HTTP", "loopback avec port explicite"]),
        ("self", "user", "Chemin …\\qdrant\\storage de 57 caractères au plus",
         ["Chemin Qdrant trop long pour le binaire", "Windows verrouillé : définir",
          "qdrant.storage_dir vers un dossier court…"]),
        ("self", "user", "Superviseur vivant : même profil, état renvoyé tel quel",
         ["Instance existante avec profil différent :", "down puis up pour appliquer la configuration"]),
        ("msg", ("user", "sup"), "lance cli _serve sans fenêtre, attend running (150 s)",
         ["Superviseur terminé (code) avant", "disponibilité ; log",
          "control\\supervisor-start.log"]),
        ("self", "sup", "Verrou control\\runtime.lock de la racine",
         ["Une instance possède déjà cette racine de", "données"]),
        ("self", "sup", "Ports app, Qdrant, Ollama libres (127.0.0.1)",
         ["Port 8785 occupé ; aucun service existant", "ne sera arrêté."]),
        ("self", "sup", "Verrou du stockage Qdrant",
         ["Une instance possède déjà ce stockage Qdrant"]),
        ("self", "sup", "Binaires conformes au manifeste local",
         ["Artefacts non provisionnés ; exécuter", "rag.ps1 provision · Empreinte du binaire …",
          "non conforme au manifeste local"]),
        ("msg", ("sup", "qdrant"), "lance Qdrant avec sa clé, attend /healthz",
         ["Disponibilité non atteinte : …/healthz", "Enfant terminé (…) avant disponibilité"]),
        ("msg", ("sup", "ollama"), "lance Ollama, attend /api/version 0.35.0",
         ["Version du service différente de l'artefact", "verrouillé"]),
        ("self", "sup", "Mode GPU ou CPU décidé d'après ollama.log", None),
        ("msg", ("sup", "api"), "lance l'API, attend /api/v1/health (120 s)", "note"),
        ("back", ("sup", "user"), "runtime.json : running ; la CLI imprime l'état JSON", None),
        ("self", "user", "open : instance running, jeton de contrôle lu",
         ["Instance non démarrée : lancer d'abord", ".\\rag.ps1 up", "Jeton de contrôle de l'instance absent :",
          "redémarrer avec .\\rag.ps1 down puis up"]),
        ("msg", ("user", "api"), "POST /api/v1/admin/session-links (X-RAG-Control-Token)", None),
        ("back", ("api", "user"), "lien /api/v1/session/open?link=… (5 min, usage unique)", None),
        ("self", "user", "lien ouvert dans le navigateur par défaut, non affiché", None),
    ]
    y = 150
    column = WIDTH - 24 - right
    for kind, owner, value, refusal in steps:
        if kind == "self":
            assert isinstance(owner, str)
            end = d.self_step(y, owner, value, limit=right - 10)
        else:
            source, target = owner
            end = d.message(y, source, target, value, style="dashed" if kind == "back" else "solid",
                            limit=right - 10)
        height = 0
        if refusal == "note":
            height = 68
            d.box(right, y - 16, column, height, "note", None,
                  ["Échec d'une phase : enfants de la tentative", "arrêtés par le Job Object, état failed,",
                   "journaux conservés."], size=12)
        elif refusal:
            height = 10 + 16 * len(refusal)
            if end + 8 < right - 4:
                d.line([(end + 6, y - 4), (right - 2, y - 4)], REFUSAL, "dotted", arrow=False, width=1.2)
            d.rect(right, y - 16, column, height, *TONES["refusal"])
            for index, value_line in enumerate(refusal):
                d.text(right + 10, y - 2 + index * 16, value_line, size=12, max_width=column - 20)
        y += max(40, height + 10)
    d.lifelines(y - 20)
    d.legend(y + 8, ["Trait plein : lancement ou requête · tirets : réponse. Un second up (même racine, "
                     "même profil) renvoie l'instance.",
                     "Mode de génération : découverte des GPU journalisée par Ollama, mode écrit dans runtime.json "
                     "et transmis à l'API.",
                     "open est une commande distincte, lancée après up ; le navigateur échange le lien contre "
                     "les cookies de session.",
                     "Les messages tronqués (…) sont complets dans docs/exploitation/DEPANNAGE.md."])
    d.height = int(y + 80)
    return d


# -- (c) chaîne d'ingestion ------------------------------------------------------------------

def ingestion() -> Diagram:
    d = Diagram("ingestion", 850, "Chaîne d'ingestion : import, routage, révisions et publication",
                "Parcours d'un PDF depuis l'import HTTP jusqu'à la publication d'une génération d'index, "
                "avec le routage par page et les points de reprise.")
    d.heading("Sources : services/api/main.py, services/api/jobs.py, services/ingestion/pipeline.py, "
              "services/api/indexing.py.")
    xs = (24, 312, 600)
    w, h = 256, 100
    centers = [x + w / 2 for x in xs]

    def row(y: float, boxes: list[tuple[str, list[str], str]]) -> None:
        for x, (title, lines, tone) in zip(xs, boxes, strict=True):
            d.box(x, y, w, h, tone, title, lines, size=12)
        for left, right_x in zip(xs, xs[1:], strict=False):
            d.line([(left + w + 1, y + h / 2), (right_x - 2, y + h / 2)], FLOW)

    row(72, [("1 · Import HTTP", ["signature %PDF-, 200 Mio au plus", "SHA-256 → originals\\<sha>.pdf",
                                  "version et travail en file (202)"], "service"),
             ("2 · File de travaux", ["un travail d'ingestion à la fois", "attend si une question est active",
                                      "ou si le verrou lourd est tenu"], "process"),
             ("3 · Admission mémoire", ["verrou lourd du poste", "pic 2304 + réserve 1536 Mio",
                                        "sinon travail en pause"], "process")])
    d.line([(centers[2], 172), (centers[2], 188), (centers[0], 188), (centers[0], 206)], FLOW)
    row(208, [("4 · Worker isolé", ["sous-processus Python sans fenêtre", "préflight : pages, chiffrement,",
                                    "classement natif, scan ou blanc"], "process"),
              ("5 · Fenêtres de 4 pages", ["window-*.json écrit par fenêtre", "reprise sans refaire les fenêtres",
                                           "pause coopérative au checkpoint"], "storage"),
              ("6 · Routage par page", ["blanc, natif, structuré ou OCR", "régional ; natif insuffisant",
                                        "→ reconverti en structuré"], "process")])
    route_centers = [24 + index * 208 + 98 for index in range(4)]
    d.line([(centers[2], 308), (centers[2], 350)], FLOW, arrow=False)
    d.line([(route_centers[0], 350), (route_centers[-1], 350)], FLOW, arrow=False)
    for center in route_centers:
        d.line([(center, 350), (center, 374)], FLOW)
    d.text(24, 340, "Voies de routage par page (page_route, routing_reason)", size=13, weight="600",
           max_width=560)
    routes = [("blank", ["aucun contenu visible", "page comptée, sans bloc"]),
              ("native", ["couche texte simple ;", "95 % des caractères,", "ordre vertical conservé"]),
              ("structured", ["tableaux, colonnes,", "typographie variée ;", "Heron et TableFormer"]),
              ("regional_ocr", ["image non couverte ou", "couche texte dégradée ;", "Tesseract fra + eng"])]
    for index, (name, lines) in enumerate(routes):
        d.box(24 + index * 208, 376, 196, 96, "model", None, [], size=12)
        d.text(34 + index * 208, 397, name, size=13, weight="600", family="mono", max_width=176)
        for line_index, value in enumerate(lines):
            d.text(34 + index * 208, 416 + line_index * 17, value, size=12, max_width=176)
    for center in route_centers:
        d.line([(center, 472), (center, 490)], FLOW, arrow=False)
    d.line([(route_centers[0], 490), (route_centers[-1], 490)], FLOW, arrow=False)
    d.line([(centers[0], 490), (centers[0], 506)], FLOW)
    row(508, [("7 · Assemblage", ["sections et tableaux raccordés", "entre fenêtres ; extraction.json",
                                  "ready, ready_partial, interrupted"], "storage"),
              ("8 · Indexation", ["fragments d'environ 320 jetons E5", "embeddings mis en cache par hash",
                                  "Qdrant upsert vérifié, FTS5"], "service"),
              ("9 · Publication", ["d'office si aucun texte ne manque", "(figures seules tolérées, W012) ;",
                                   "sinon publish-partial explicite"], "service")])
    d.box(24, 636, 832, 110, "note", "Révisions et reprise",
          ["Révision d'extraction = uuid5(version, SHA-256 du PDF, empreinte du pipeline) ; "
           "une citation garde sa révision.",
           "Nouvelle génération invisible jusqu'à sa publication ; la précédente passe en nettoyage "
           "vectoriel (vector_cleanup).",
           "Mot OCR sous 0,8 : région non résolue ; texte manquant : ready_partial, publication explicite (W012).",
           "Backend PDF : pdf.pdf_backend (pypdfium2 dans le profil, W009 ; docling_parse sélectionnable)."], size=12)
    d.legend(770, ["Ce schéma montre l'ordre des étapes d'un travail d'ingestion ; les cadres violets "
                   "sont les voies de routage d'une page.",
                   "Une question interactive demande une pause au prochain checkpoint ; "
                   "la reprise d'un travail en pause est manuelle."])
    d.height = 810
    return d


# -- (d) séquence d'une question -------------------------------------------------------------

def question() -> Diagram:
    d = Sequence("sequence-question", 790, "Question : recherche hybride, sélection, admission, génération, citation",
                 "Échanges entre le navigateur, l'API, la recherche, le constructeur de contexte, le gouverneur "
                 "de ressources et Ollama pour une question, jusqu'à l'ouverture d'une citation.")
    d.heading("Sources : services/api/query.py, retrieval.py, context.py, services/runtime/resources.py, "
              "profil local16.")
    d.participants([("user", "Navigateur", "/workspace/", 76, 104),
                    ("api", "API", "QueryService", 198, 110),
                    ("search", "Recherche", "FTS5 · E5 · Qdrant", 338, 136),
                    ("context", "Contexte", "ContextBuilder", 480, 118),
                    ("gov", "Gouverneur", "ResourceGovernor", 624, 128),
                    ("llm", "Ollama", "modèle du profil", 774, 124)])
    steps = [
        ("msg", "user", "api", "POST /api/v1/queries + X-CSRF-Token : question, périmètre, mode", "solid"),
        ("msg", "api", "user", "202 : query_id, events_url", "dashed"),
        ("msg", "user", "api", "GET …/events (SSE ; reprise par Last-Event-ID)", "solid"),
        ("msg", "api", "user", "status queued puis searching", "dashed"),
        ("msg", "api", "search", "BM25 FTS5 (identifiants exacts d'abord) et E5 → Qdrant, filtrés par périmètre",
         "solid"),
        ("self", "search", None, "RRF k = 60, identifiants réservés, dédoublonnage, 6 fragments au plus", "right"),
        ("msg", "api", "context", "expansion parent (900 jetons), budget par mode 1536 / 2560 / 5120", "solid"),
        ("msg", "api", "user", "sources S001…, warnings ; sans source : insuffisance, modèle non appelé",
         "dashed"),
        ("msg", "api", "gov", "admission : verrou lourd, pic froid du profil + réserve hôte", "solid"),
        ("msg", "api", "user", "status waiting_for_resources : remesure toutes les 2 s, 120 s au plus", "dashed"),
        ("msg", "api", "llm", "POST /api/chat en flux ; status generating", "solid"),
        ("self", "gov", None, "réserve 1536 Mio surveillée toutes les 0,5 s ; annulation si menacée", "left"),
        ("msg", "llm", "api", "fragments de texte", "dashed"),
        ("msg", "api", "user", "delta… puis done : IDs inconnus retirés, citations enregistrées", "dashed"),
        ("msg", "user", "api", "GET /api/v1/citations/{query_id}/{source_id}", "solid"),
        ("msg", "api", "user", "version, page, blocs et révision : le lecteur ouvre et surligne", "dashed"),
    ]
    y = 146
    for kind, owner, target, value, style in steps:
        if kind == "self":
            d.self_step(y, owner, value, side=style)
        else:
            assert target is not None
            d.message(y, owner, target, value, style=style, color=NETWORK if style == "solid" else FLOW)
        y += 36
    d.lifelines(y - 14)
    d.legend(y + 16, ["Trait plein : requête · tirets : réponse ou événement SSE.",
                      "Chaque requête du navigateur porte le cookie de session (W011) ; sans session valide, "
                      "401 avant toute recherche.",
                      "Refus d'admission à l'échéance : événement error resource_admission_denied, "
                      "modèle non appelé.",
                      "Une réponse ne cite que des IDs du registre de la question ; le clic relit le registre "
                      "avant d'ouvrir le document."])
    d.height = int(y + 96)
    return d


# -- (e) sauvegarde et restauration ----------------------------------------------------------

def backup() -> Diagram:
    d = Diagram("sauvegarde-restauration", 860, "Sauvegarde et restauration dans une racine neuve",
                "Étapes de rag.ps1 backup et rag.ps1 restore, contenu du snapshot et démarrage du profil restauré.")
    d.heading("Sources : services/runtime/backup.py (create_backup, verify_backup, restore_backup), "
              "services/api/main.py (admin).")
    left, middle, right = 24, 314, 592
    left_width, middle_width, column = 260, 240, 264
    d.text(left, 90, "rag.ps1 backup -Path <neuf>", size=13, weight="600", family="mono",
           max_width=left_width)
    d.text(right, 90, "rag.ps1 restore -Path -Target", size=13, weight="600", family="mono",
           max_width=column)
    saves = [("Instance running", ["identités du superviseur et des", "services revalidées"]),
             ("Destination neuve", ["hors données actives ; 2 Gio", "libres exigés"]),
             ("POST /admin/quiesce", ["jeton et clé Qdrant lus ; mutations", "503, checkpoint, WAL reporté"]),
             ("SQLite : API backup", ["integrity_check, foreign_key_check", "et comptes de 11 tables"]),
             ("Copie des fichiers", ["originals, extractions, manifestes,", "profil, verrous, contrats"]),
             ("Snapshots Qdrant", ["par collection : création,", "téléchargement, checksum"]),
             ("manifest.json complete", ["SHA-256 et taille par fichier,", "puis verify_backup"]),
             ("POST /admin/resume", ["toujours envoyé, même en échec", "(bloc finally)"])]
    restores = [("verify_backup", ["hashes, fichiers en trop refusés,", "comptes SQLite du manifeste"]),
                ("Cible neuve", ["distincte du snapshot ; port 6343", "libre ; snapshot Qdrant 1.19.1"]),
                ("Copie de data/", ["hash de chaque copie vérifié", "avant réécriture des chemins"]),
                ("Chemins SQLite", ["réécrits vers la cible ;", "intégrité et comptes identiques"]),
                ("Stockage Qdrant court", ["si …\\qdrant\\storage > 57 car. :", ".runtime\\q\\<id8>, neuf"]),
                ("Qdrant temporaire 6343", ["clé propre ; envoi des snapshots", "(2 reprises E/S), comptes, arrêt"]),
                ("restored-profile.yaml", ["API 8795, Qdrant 6343,", "Ollama 11445"]),
                ("restore-report.json", ["restored_storage_verified ;", "question et citation : NOT_RUN"])]
    top, height, gap = 104, 68, 10
    for index, (title, lines) in enumerate(saves):
        y = top + index * (height + gap)
        d.box(left, y, left_width, height, "process", title, lines, size=12, title_size=13)
        if index:
            d.line([(left + 130, y - gap), (left + 130, y - 1)], FLOW)
    for index, (title, lines) in enumerate(restores):
        y = top + index * (height + gap)
        d.box(right, y, column, height, "service", title, lines, size=12, title_size=13)
        if index:
            d.line([(right + 132, y - gap), (right + 132, y - 1)], FLOW)
    d.box(middle, top, middle_width, 348, "storage", "Snapshot sauvegardé",
          ["format rag-native-backup-v1", "manifest.json : état et", "SHA-256 de chaque fichier",
           "data/app.sqlite3", "data/originals/", "data/extractions/", "qdrant/<uuid>.snapshot",
           "runtime-manifests/", "config/ : profil, verrous,", "contrats, manifeste des sources"],
          mono=(3, 4, 5, 6, 7), size=12, title_size=13)
    y_manifest = top + 6 * (height + gap) + height / 2
    d.line([(left + left_width + 1, y_manifest), (middle + 30, y_manifest), (middle + 30, top + 350)], FLOW)
    d.line([(middle + middle_width + 1, top + height / 2), (right - 2, top + height / 2)], FLOW)
    bottom = top + 8 * (height + gap) + 8
    d.line([(right + 132, bottom - gap - 8), (right + 132, bottom + 6)], FLOW)
    d.box(24, bottom + 8, 832, 84, "note", "Ensuite, sur le profil restauré",
          ["rag.ps1 up -Profile <cible>\\restored-profile.yaml, puis vérifier une recherche et une ancienne citation.",
           "Ne jamais déplacer ni purger seul le stockage Qdrant court : relocaliser par backup puis restore."],
          size=12)
    d.legend(bottom + 118, ["Ce schéma montre l'ordre des contrôles de la sauvegarde (vert) et de la restauration "
                            "(bleu) et le contenu du snapshot.",
                            "Tout échec laisse un manifeste ou un rapport à l'état failed ; aucune restauration "
                            "n'écrit dans une racine existante."])
    d.height = int(bottom + 158)
    return d


BUILDERS = {"processus-ports": processes, "sequence-up": startup, "ingestion": ingestion,
            "sequence-question": question, "sauvegarde-restauration": backup}


def render_all() -> dict[str, str]:
    return {f"{name}.svg": builder().render() for name, builder in BUILDERS.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="comparer sans écrire")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    rendered = render_all()
    differences = []
    for name, content in rendered.items():
        path = args.output / name
        data = content.encode("utf-8")
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                differences.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
    if differences:
        print("Schémas à régénérer : " + ", ".join(differences))
        return 1
    print(("Schémas conformes : " if args.check else "Schémas écrits : ") + ", ".join(rendered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
