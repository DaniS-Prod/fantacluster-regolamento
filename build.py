#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — genera docs/index.html a partire dal Markdown in src/.

Uso:
    python build.py

Nessun framework, nessun npm. Unica dipendenza: mistune (pip install mistune).
Il file HTML prodotto e' autosufficiente: CSS e JS sono inline, nessuna risorsa
esterna. Funziona sia su GitHub Pages sia aperto in locale (doppio click,
protocollo file://).

Convenzioni del Markdown sorgente (vedi README):
  ---front matter---   opzionale in cima: usato il campo `stagione`.
  #     -> titolo della pagina.
  ##    -> articolo. id esplicito con {#art-N}. Numerato "Art. N".
  ###   -> comma.       id esplicito con {#art-N-M}  (es. {#art-6-4}).
  ####  -> sotto-comma.  id esplicito con {#art-N-M-K} (es. {#art-6-5-1}).
  ## Titolo {#altro}   -> con id che NON inizia per "art-" diventa appendice
                          (sezione non numerata, es. le Sottoscrizioni).
  ---                  -> a livello di documento separa gli articoli dalla
                          chiusura (motto + eventuali appendici).
Gli id sono usati tali e quali come ancore; se un heading non ha id esplicito,
viene numerato automaticamente in base alla posizione.
"""

import html
import pathlib
import re
import subprocess
from datetime import datetime, timezone

import mistune

# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
OUT_DIR = ROOT / "docs"
OUT_FILE = OUT_DIR / "index.html"

# Includere il blocco firme (## Sottoscrizioni, id "firme") nel sito pubblicato?
# Il sorgente Markdown lo contiene per fedelta' all'originale, ma di default NON
# finisce sul sito (contiene nomi reali). Metti True se vuoi pubblicarlo.
INCLUDI_FIRME = False

# URL canonico del sito pubblicato su GitHub Pages, es:
#   "https://tuo-utente.github.io/fantacluster-regolamento/"
# Se valorizzato, il pulsante "copia link" produce SEMPRE un URL che punta al
# sito pubblicato, anche quando la pagina e' aperta in locale (file://): comodo
# per incollare in chat un link al comma durante l'asta.
# Lascialo "" per usare l'indirizzo corrente della pagina.
SITE_URL = ""

MESI_IT = [
    "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

# --------------------------------------------------------------------------
# Lettura sorgenti + front matter + data ultima modifica
# --------------------------------------------------------------------------
def leggi_sorgenti():
    """Concatena tutti i src/*.md in ordine alfabetico di nome file.

    Ignora i file il cui nome inizia con '_' (bozze/note) e i README.
    Ritorna (testo_markdown, elenco_percorsi_usati).
    """
    if not SRC_DIR.is_dir():
        raise SystemExit(
            f"Cartella sorgente mancante: {SRC_DIR}\n"
            "Crea src/ e mettici il regolamento in Markdown (vedi README)."
        )
    files = sorted(
        p for p in SRC_DIR.glob("*.md")
        if not p.name.startswith("_") and p.name.lower() != "readme.md"
    )
    if not files:
        raise SystemExit(f"Nessun file .md trovato in {SRC_DIR}.")
    testo = "\n\n".join(p.read_text(encoding="utf-8") for p in files)
    return testo, files


def separa_frontmatter(text):
    """Estrae il front matter YAML iniziale (se presente).

    Ritorna (dict_campi_semplici, corpo_markdown). Vengono letti solo i campi
    `chiave: valore` di primo livello (le righe indentate sono ignorate).
    """
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---[ \t]*\n?", text, re.S)
    if not m:
        return fm, text
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][\w-]*):[ \t]*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip("\"'")
    return fm, text[m.end():]


def _git(*args):
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(ROOT),
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def data_ultima_modifica(files):
    """Data di ultima modifica del regolamento.

    - Se ci sono modifiche non ancora committate in src/, usa "adesso": la data
      riflette la modifica che stai per pubblicare, senza dover committare prima
      di rigenerare.
    - Altrimenti usa la data dell'ultimo commit che ha toccato src/.
    - Se git non e' disponibile o non ci sono commit, usa l'ora corrente.
    Ritorna (datetime, testo_italiano).
    """
    dt = None
    rel = [str(p.relative_to(ROOT)).replace("\\", "/") for p in files]

    if _git("status", "--porcelain", "--", *rel):
        dt = datetime.now(timezone.utc).astimezone()
    else:
        iso = _git("log", "-1", "--format=%cI", "--", *rel) or _git("log", "-1", "--format=%cI")
        if iso:
            try:
                dt = datetime.fromisoformat(iso)
            except ValueError:
                dt = None
    if dt is None:
        dt = datetime.now(timezone.utc).astimezone()
    return dt, f"{dt.day} {MESI_IT[dt.month]} {dt.year}"


# --------------------------------------------------------------------------
# Rendering AST -> HTML
# --------------------------------------------------------------------------
def testo_nodo(nodo):
    """Testo semplice di un nodo AST (per euristiche / ricerca / data-label)."""
    t = nodo.get("type")
    if t in ("text", "codespan", "inline_html"):
        return nodo.get("raw", "") if t != "inline_html" else ""
    if t in ("softbreak", "linebreak"):
        return " "
    figli = nodo.get("children")
    if figli:
        return "".join(testo_nodo(c) for c in figli)
    return nodo.get("raw", "")


def rendi_inline(nodi):
    out = []
    for n in nodi:
        t = n["type"]
        if t == "text":
            out.append(html.escape(n["raw"], quote=False))
        elif t == "strong":
            out.append("<strong>" + rendi_inline(n["children"]) + "</strong>")
        elif t == "emphasis":
            out.append("<em>" + rendi_inline(n["children"]) + "</em>")
        elif t == "codespan":
            out.append("<code>" + html.escape(n["raw"]) + "</code>")
        elif t == "strikethrough":
            out.append("<del>" + rendi_inline(n["children"]) + "</del>")
        elif t == "link":
            url = n["attrs"]["url"]
            esterno = url.startswith(("http://", "https://"))
            extra = ' target="_blank" rel="noopener noreferrer"' if esterno else ""
            out.append(
                '<a href="' + html.escape(url, quote=True) + '"' + extra + ">"
                + rendi_inline(n["children"]) + "</a>"
            )
        elif t == "inline_html":
            out.append(n["raw"])  # HTML voluto dall'autore (es. <br>)
        elif t == "linebreak":
            out.append("<br>")
        elif t == "softbreak":
            out.append(" ")
        elif "children" in n:
            out.append(rendi_inline(n["children"]))
        elif "raw" in n:
            out.append(html.escape(n["raw"]))
    return "".join(out)


def rendi_tabella(nodo):
    head = next((c for c in nodo["children"] if c["type"] == "table_head"), None)
    body = next((c for c in nodo["children"] if c["type"] == "table_body"), None)
    intestazioni = [rendi_inline(c["children"]) for c in head["children"]] if head else []
    label = [testo_nodo(c).strip() for c in head["children"]] if head else []
    ncol = len(intestazioni)
    ha_intestazioni = any(l for l in label)

    maxlen = 0
    righe = []
    for r in (body["children"] if body else []):
        celle = []
        for i, c in enumerate(r["children"]):
            maxlen = max(maxlen, len(testo_nodo(c).strip()))
            etichetta = label[i] if i < len(label) else ""
            celle.append(
                '<td data-label="' + html.escape(etichetta, quote=True) + '">'
                + rendi_inline(c["children"]) + "</td>"
            )
        righe.append("<tr>" + "".join(celle) + "</tr>")

    # Le tabelle con intestazione, larghe (>=3 colonne) o con celle lunghe si
    # riflettono in card su mobile; le altre restano a scorrimento orizzontale.
    layout = "cards" if (ha_intestazioni and (ncol >= 3 or maxlen > 45)) else "scroll"

    thead = ""
    if ha_intestazioni:
        thead = "<thead><tr>" + "".join(
            f'<th scope="col">{h}</th>' for h in intestazioni
        ) + "</tr></thead>"
    tbody = "<tbody>" + "".join(righe) + "</tbody>"
    return (
        f'<div class="table-wrap"><table class="rulebook-table table-{layout}">'
        + thead + tbody + "</table></div>"
    )


def rendi_lista(nodo):
    tag = "ol" if nodo["attrs"].get("ordered") else "ul"
    items = "".join(
        "<li>" + rendi_blocchi(it["children"]) + "</li>" for it in nodo["children"]
    )
    return f"<{tag}>{items}</{tag}>"


def rendi_blocchi(nodi):
    out = []
    for n in nodi:
        t = n["type"]
        if t == "paragraph":
            out.append("<p>" + rendi_inline(n["children"]) + "</p>")
        elif t == "block_text":
            out.append(rendi_inline(n["children"]))
        elif t == "list":
            out.append(rendi_lista(n))
        elif t == "table":
            out.append(rendi_tabella(n))
        elif t == "thematic_break":
            out.append("<hr>")
        elif t == "block_quote":
            out.append('<blockquote class="nota">' + rendi_blocchi(n["children"]) + "</blockquote>")
        elif t in ("block_code", "code"):
            out.append("<pre><code>" + html.escape(n.get("raw", "")) + "</code></pre>")
        elif t == "block_html":
            out.append(n.get("raw", ""))
        elif t == "heading":
            lvl = min(max(n["attrs"]["level"], 4), 6)
            out.append(f"<h{lvl}>" + rendi_inline(n["children"]) + f"</h{lvl}>")
        elif t == "blank_line":
            pass
        elif "children" in n:
            out.append(rendi_blocchi(n["children"]))
    return "".join(out)


# --------------------------------------------------------------------------
# Parsing heading: id/classi espliciti + titolo formattato ripulito
# --------------------------------------------------------------------------
ATTR_RE = re.compile(r"\s*\{([^}]*)\}\s*$")


def parse_heading(children):
    """Ritorna (id, classi, titolo_html, titolo_testo) di un heading.

    Estrae un eventuale blocco attributi finale `{#id .classe ...}` e lo toglie
    sia dal testo semplice sia dall'HTML (preservando l'eventuale formattazione
    inline del titolo, es. corsivo).
    """
    raw = "".join(testo_nodo(c) for c in children).strip()
    hid, classi = None, []
    m = ATTR_RE.search(raw)
    if m:
        for part in m.group(1).split():
            if part.startswith("#"):
                hid = part[1:]
            elif part.startswith("."):
                classi.append(part[1:])
    inner = ATTR_RE.sub("", rendi_inline(children)).strip()
    testo = ATTR_RE.sub("", raw).strip()
    return hid, classi, inner, testo


def numeri_da_id(hid):
    """['6','5','1'] da 'art-6-5-1'; None se l'id non e' nella forma art-N[-M...]."""
    if hid and re.fullmatch(r"art-\d+(?:-\d+)*", hid):
        return hid[4:].split("-")
    return None


def togli_prefisso(html_str, etichette):
    """Rimuove dal titolo un'eventuale numerazione gia' scritta a mano."""
    for lab in etichette:
        m = re.match(re.escape(lab) + r"\s*[—–\-:.)]*\s*", html_str)
        if m:
            return html_str[m.end():].lstrip()
    return html_str


# --------------------------------------------------------------------------
# Costruzione del modello documento
# --------------------------------------------------------------------------
def costruisci_documento(md_text):
    md = mistune.create_markdown(
        renderer=None, escape=False, plugins=["table", "strikethrough"]
    )
    tokens = md(md_text)

    doc = {
        "titolo_html": "Regolamento",
        "titolo_raw": "Regolamento",
        "preambolo": [],
        "articoli": [],
        "chiusura": [],     # motto e prosa libera di chiusura
        "appendici": [],    # sezioni non numerate (es. Sottoscrizioni)
    }
    titolo_impostato = False
    art = comma = sub = appendice = None
    chiusura = False

    def target():
        if appendice is not None:
            return appendice["corpo"]
        if sub is not None:
            return sub["corpo"]
        if comma is not None:
            return comma["corpo"]
        if art is not None:
            return art["intro"]
        if chiusura:
            return doc["chiusura"]
        return doc["preambolo"]

    for tok in tokens:
        t = tok["type"]

        if t == "blank_line":
            continue

        if t == "thematic_break":
            # Separatore di documento: chiude gli articoli, inizia la chiusura.
            art = comma = sub = appendice = None
            chiusura = True
            continue

        if t == "heading":
            lvl = tok["attrs"]["level"]
            hid, classi, titolo_html, titolo_txt = parse_heading(tok["children"])

            if lvl == 1:
                if not titolo_impostato:
                    doc["titolo_html"] = titolo_html or "Regolamento"
                    doc["titolo_raw"] = titolo_txt or "Regolamento"
                    titolo_impostato = True
                continue

            nums = numeri_da_id(hid)

            if lvl == 2 and hid is not None and nums is None:
                # id che non e' "art-...": appendice (sezione non numerata).
                appendice = {"id": hid, "classi": classi,
                             "titolo_html": titolo_html, "corpo": []}
                doc["appendici"].append(appendice)
                art = comma = sub = None
                continue

            if lvl == 2:
                n = nums[0] if nums else str(len(doc["articoli"]) + 1)
                aid = hid or f"art-{n}"
                titolo_html = togli_prefisso(
                    titolo_html,
                    [f"Art. {n}", f"Articolo {n}", f"Art.{n}", f"{n}."],
                ) or titolo_html
                art = {"id": aid, "num": n, "classi": classi,
                       "titolo_html": titolo_html, "intro": [], "commi": []}
                doc["articoli"].append(art)
                comma = sub = appendice = None
                chiusura = False
                continue

            if lvl == 3:
                if art is None:
                    art = {"id": f"art-{len(doc['articoli']) + 1}",
                           "num": str(len(doc["articoli"]) + 1), "classi": [],
                           "titolo_html": "", "intro": [], "commi": []}
                    doc["articoli"].append(art)
                m_ = nums and ".".join(nums) or f"{art['num']}.{len(art['commi']) + 1}"
                cid = hid or f"art-{art['num']}-{len(art['commi']) + 1}"
                titolo_html = togli_prefisso(titolo_html, [m_, f"{m_}."])
                comma = {"id": cid, "label": m_, "classi": classi,
                         "titolo_html": titolo_html, "corpo": [], "sub": []}
                art["commi"].append(comma)
                sub = None
                continue

            # lvl >= 4: sotto-comma
            if comma is None:
                # Nessun comma aperto: promuovo a comma per non perdere contenuto.
                base = art["num"] if art else str(len(doc["articoli"]))
                comma = {"id": f"art-{base}-x", "label": base, "classi": [],
                         "titolo_html": "", "corpo": [], "sub": []}
                if art:
                    art["commi"].append(comma)
            k = nums and ".".join(nums) or f"{comma['label']}.{len(comma['sub']) + 1}"
            sid = hid or f"{comma['id']}-{len(comma['sub']) + 1}"
            titolo_html = togli_prefisso(titolo_html, [k, f"{k}."])
            sub = {"id": sid, "label": k, "classi": classi,
                   "titolo_html": titolo_html, "corpo": []}
            comma["sub"].append(sub)
            continue

        # blocco generico
        target().append(tok)

    return doc


def stagione_da(fm, titolo_raw):
    if fm.get("stagione"):
        return fm["stagione"]
    m = re.search(r"(20\d{2})\s*[-/–]\s*(20\d{2})", titolo_raw)
    return f"{m.group(1)}-{m.group(2)}" if m else ""


# --------------------------------------------------------------------------
# Assemblaggio HTML
# --------------------------------------------------------------------------
ICON_LINK = (
    '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>'
    '<path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>'
)


def bottone_copia(anchor, label):
    return (
        f'<button class="copy" type="button" data-anchor="{anchor}" '
        f'title="Copia link al comma {label}" '
        f'aria-label="Copia link al comma {label}">{ICON_LINK}</button>'
    )


def html_sub(s):
    sub_t = f'<span class="comma-title">{s["titolo_html"]}</span>' if s["titolo_html"] else ""
    return f"""<section class="subcomma" id="{s['id']}">
  <div class="comma-head">
    <a class="comma-num sub" href="#{s['id']}">{s['label']}</a>
    {bottone_copia(s['id'], s['label'])}{sub_t}
  </div>
  <div class="comma-body">{rendi_blocchi(s['corpo'])}</div>
</section>"""


def html_comma(c):
    sub_t = f'<span class="comma-title">{c["titolo_html"]}</span>' if c["titolo_html"] else ""
    subs = "".join(html_sub(s) for s in c["sub"])
    subs_html = f'<div class="subcommi">{subs}</div>' if subs else ""
    return f"""<section class="comma" id="{c['id']}">
  <div class="comma-head">
    <a class="comma-num" href="#{c['id']}">{c['label']}</a>
    {bottone_copia(c['id'], c['label'])}{sub_t}
  </div>
  <div class="comma-body">{rendi_blocchi(c['corpo'])}</div>
  {subs_html}
</section>"""


def html_articolo(a):
    leaf = len(a["commi"]) == 0
    cls = "article leaf" if leaf else "article"
    intro = rendi_blocchi(a["intro"])
    intro_html = f'<div class="article-intro">{intro}</div>' if intro else ""
    commi = "\n".join(html_comma(c) for c in a["commi"])
    return f"""<section class="{cls}" id="{a['id']}">
  <h2 class="article-head">
    <span class="art-num">Art. {a['num']}</span>
    <span class="art-title">{a['titolo_html']}</span>
  </h2>
  {intro_html}
  {commi}
</section>"""


def html_appendice(a):
    return f"""<section class="appendix leaf-section" id="{a['id']}">
  <h2 class="appendix-head">{a['titolo_html']}</h2>
  <div class="appendix-body">{rendi_blocchi(a['corpo'])}</div>
</section>"""


def html_indice(articoli, appendici):
    voci = [
        f'    <li><a href="#{a["id"]}"><span class="idx-num">{a["num"]}</span>'
        f'<span class="idx-txt">{a["titolo_html"]}</span></a></li>'
        for a in articoli
    ]
    for a in appendici:
        voci.append(
            f'    <li class="idx-appendix"><a href="#{a["id"]}">'
            f'<span class="idx-num">§</span><span class="idx-txt">{a["titolo_html"]}</span></a></li>'
        )
    return '<ol class="index-list">\n' + "\n".join(voci) + "\n  </ol>"


def costruisci_html(doc, stagione, data_dt, data_txt):
    appendici = [a for a in doc["appendici"] if a["id"] != "firme" or INCLUDI_FIRME]

    preambolo_html = rendi_blocchi(doc["preambolo"])
    corpo_articoli = "\n".join(html_articolo(a) for a in doc["articoli"])
    chiusura_html = rendi_blocchi(doc["chiusura"])
    appendici_html = "\n".join(html_appendice(a) for a in appendici)
    indice = html_indice(doc["articoli"], appendici)

    chip_stagione = (
        f'<span class="chip">Stagione {html.escape(stagione)}</span>' if stagione else ""
    )
    preambolo_blocco = (
        f'<div class="preamble filterable">{preambolo_html}</div>' if preambolo_html else ""
    )
    chiusura_blocco = (
        f'<section class="epilogue filterable">{chiusura_html}</section>' if chiusura_html else ""
    )
    site_url_js = html.escape(SITE_URL, quote=True)
    iso = data_dt.date().isoformat()  # solo data: stabile entro la giornata

    return (
        PAGE_HEAD.replace("__TITLE__", doc["titolo_html"])
        + "<style>\n" + CSS + "\n</style>\n</head>\n<body>\n"
        + f"""<a class="skip-link" href="#contenuto">Salta al contenuto</a>

<header class="hero">
  <div class="hero-inner">
    <h1>{doc['titolo_html']}</h1>
    <div class="meta">
      {chip_stagione}
      <span class="updated">Ultima modifica: <time datetime="{iso}">{data_txt}</time></span>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-inner">
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="indice">
      <span class="nav-toggle-icon" aria-hidden="true">☰</span> Indice
    </button>
    <div class="search">
      <input id="q" type="search" inputmode="search" autocomplete="off"
        placeholder="Cerca nei commi…" aria-label="Cerca nei commi">
      <span id="search-count" class="search-count" aria-live="polite"></span>
    </div>
  </div>
</div>

<div class="layout">
  <nav id="indice" class="sidebar" aria-label="Indice degli articoli">
    <p class="sidebar-title">Articoli</p>
    {indice}
  </nav>
  <main id="contenuto" class="content">
    {preambolo_blocco}
    {corpo_articoli}
    {chiusura_blocco}
    {appendici_html}
    <p id="no-results" class="no-results" hidden>Nessun comma corrisponde alla ricerca.</p>
  </main>
</div>

<footer class="site-footer">
  <p>Regolamento generato staticamente — nessun cookie, nessun tracciamento.
  Ultima modifica: {data_txt}.</p>
</footer>

<div id="toast" class="toast" role="status" aria-live="polite"></div>

<script>
const SITE_URL = "{site_url_js}";
</script>
"""
        + "<script>\n" + JS + "\n</script>\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# Template statici (testa / CSS / JS)
# --------------------------------------------------------------------------
PAGE_HEAD = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>__TITLE__</title>
"""

CSS = r"""
:root{
  --bg:#f6f7f5; --surface:#ffffff; --text:#1c1f1a; --muted:#5c6357;
  --border:#e2e5dd; --accent:#2f7d43; --accent-soft:#e4f0e6;
  --accent-ink:#1d5c30; --shadow:0 1px 2px rgba(0,0,0,.05),0 6px 20px rgba(0,0,0,.04);
  --radius:12px; --toolbar-h:56px; --maxw:70ch;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#14170f; --surface:#1c2016; --text:#e9ece3; --muted:#a3ab98;
    --border:#2c3223; --accent:#5fbf76; --accent-soft:#20301f;
    --accent-ink:#8fe0a0; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.3);
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--text);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:17px; line-height:1.6; -webkit-text-size-adjust:100%;
}
a{color:var(--accent-ink)}
.skip-link{position:absolute;left:-999px;top:0;background:var(--accent);color:#fff;
  padding:.6rem 1rem;border-radius:0 0 var(--radius) 0;z-index:100}
.skip-link:focus{left:0}

.hero{background:linear-gradient(180deg,var(--accent-soft),transparent);
  border-bottom:1px solid var(--border)}
.hero-inner{max-width:1180px;margin:0 auto;padding:1.6rem 1.1rem .9rem}
.hero h1{margin:0 0 .5rem;font-size:1.5rem;line-height:1.25;letter-spacing:-.01em}
.meta{display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;
  color:var(--muted);font-size:.9rem}
.chip{display:inline-block;background:var(--accent);color:#fff;font-weight:600;
  padding:.15rem .6rem;border-radius:999px;font-size:.82rem;letter-spacing:.01em}
@media (prefers-color-scheme: dark){.chip{color:#0c130b}}

.toolbar{position:sticky;top:0;z-index:30;
  background:color-mix(in srgb,var(--surface) 92%,transparent);
  -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border)}
.toolbar-inner{max-width:1180px;margin:0 auto;padding:.55rem 1.1rem;
  display:flex;gap:.6rem;align-items:center;min-height:var(--toolbar-h)}
.search{flex:1;position:relative;display:flex;align-items:center;gap:.5rem}
.search input{flex:1;width:100%;padding:.55rem .8rem;font-size:1rem;color:var(--text);
  background:var(--surface);border:1px solid var(--border);border-radius:999px;outline:none}
.search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.search-count{color:var(--muted);font-size:.82rem;white-space:nowrap}
.nav-toggle{display:inline-flex;align-items:center;gap:.4rem;padding:.5rem .8rem;
  font-size:.95rem;font-weight:600;color:var(--text);background:var(--surface);
  border:1px solid var(--border);border-radius:999px;cursor:pointer}
.nav-toggle-icon{font-size:1.05rem;line-height:1}

.layout{max-width:1180px;margin:0 auto;padding:1.2rem 1.1rem 3rem;
  display:grid;grid-template-columns:1fr;gap:1.4rem}

.sidebar{display:none}
.sidebar.open{display:block}
.sidebar-title{margin:.2rem 0 .5rem;font-size:.75rem;text-transform:uppercase;
  letter-spacing:.08em;color:var(--muted);font-weight:700}
.index-list{list-style:none;margin:0;padding:0}
.index-list li{margin:0}
.index-list a{display:flex;gap:.6rem;align-items:baseline;padding:.42rem .55rem;
  border-radius:8px;text-decoration:none;color:var(--text)}
.index-list a:hover{background:var(--accent-soft)}
.idx-num{flex:0 0 auto;min-width:1.4em;text-align:right;color:var(--accent-ink);
  font-weight:700;font-variant-numeric:tabular-nums}
.idx-txt{flex:1}
.idx-appendix{margin-top:.4rem;border-top:1px solid var(--border);padding-top:.4rem}
.idx-appendix .idx-num{color:var(--muted)}

.content{min-width:0}
.preamble{max-width:var(--maxw);color:var(--muted);font-size:1.02rem;
  border-left:3px solid var(--accent);padding:.2rem 0 .2rem 1rem;margin:0 0 1.6rem}
.article{scroll-margin-top:calc(var(--toolbar-h) + 16px);margin:0 0 2.2rem}
.article-head{display:flex;flex-wrap:wrap;gap:.2rem .7rem;align-items:baseline;
  margin:0 0 .8rem;padding-bottom:.5rem;border-bottom:2px solid var(--border);
  font-size:1.28rem;line-height:1.25;letter-spacing:-.01em}
.art-num{color:var(--accent-ink);font-weight:800;white-space:nowrap}
.art-title{font-weight:700}
.article-intro,.appendix-body{max-width:var(--maxw)}
.article.leaf .article-intro{margin-top:.2rem}

.comma{scroll-margin-top:calc(var(--toolbar-h) + 16px);
  padding:.5rem 0;margin:0;position:relative}
.comma + .comma{border-top:1px solid var(--border)}
.comma-head{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.comma-num{font-weight:700;color:var(--accent-ink);text-decoration:none;
  font-variant-numeric:tabular-nums;background:var(--accent-soft);
  padding:.05rem .5rem;border-radius:999px;font-size:.9rem}
.comma-num.sub{font-size:.82rem;opacity:.95}
.comma-num:hover{text-decoration:underline}
.comma-title{font-size:1.02rem;font-weight:700}
.copy{display:inline-flex;align-items:center;justify-content:center;
  width:30px;height:30px;padding:0;color:var(--muted);background:transparent;
  border:1px solid transparent;border-radius:8px;cursor:pointer;opacity:.6}
.copy:hover{color:var(--accent-ink);background:var(--accent-soft);opacity:1}
.copy:focus-visible{outline:2px solid var(--accent);outline-offset:2px;opacity:1}
.comma-body{max-width:var(--maxw)}
.comma-body>*:first-child{margin-top:.35rem}
.comma-body>*:last-child{margin-bottom:0}
.comma-body p{margin:.5rem 0}
.comma-body ul,.comma-body ol{margin:.5rem 0;padding-left:1.4rem}
.comma-body li{margin:.25rem 0}

.subcommi{margin:.4rem 0 0 .2rem;padding-left:.9rem;border-left:2px solid var(--border)}
.subcomma{scroll-margin-top:calc(var(--toolbar-h) + 16px);padding:.35rem 0}
.subcomma .comma-num{background:transparent;padding:.05rem 0}

blockquote.nota{margin:.9rem 0;padding:.6rem .9rem;background:var(--accent-soft);
  border-left:4px solid var(--accent);border-radius:0 8px 8px 0;
  color:var(--text);font-size:.94rem}
blockquote.nota p{margin:.3rem 0}

.comma:target,.subcomma:target{background:var(--accent-soft);border-radius:var(--radius);
  box-shadow:0 0 0 .5rem var(--accent-soft)}

.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:.9rem 0;
  border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);
  box-shadow:var(--shadow)}
.rulebook-table{border-collapse:collapse;width:100%;font-size:.95rem}
.rulebook-table th,.rulebook-table td{padding:.6rem .8rem;text-align:left;
  vertical-align:top;border-bottom:1px solid var(--border)}
.rulebook-table thead th{background:var(--accent-soft);color:var(--accent-ink);
  font-weight:700;position:sticky;top:0}
.rulebook-table tbody tr:last-child td{border-bottom:none}
.rulebook-table td[data-label]{min-width:5rem}

@media (max-width:640px){
  .table-cards{border:0}
  .table-cards thead{position:absolute;width:1px;height:1px;overflow:hidden;
    clip:rect(0 0 0 0);white-space:nowrap}
  .table-cards tbody,.table-cards tr,.table-cards td{display:block;width:100%}
  .table-cards tr{border:1px solid var(--border);border-radius:10px;
    margin:.6rem;padding:.1rem;background:var(--bg)}
  .table-cards td{display:grid;grid-template-columns:minmax(6.5rem,38%) 1fr;
    gap:.4rem .8rem;border-bottom:1px solid var(--border);padding:.5rem .8rem}
  .table-cards tr td:last-child{border-bottom:none}
  .table-cards td::before{content:attr(data-label);font-weight:700;color:var(--muted)}
  .table-cards td:empty{display:none}
}

.is-hidden{display:none !important}
.no-results{color:var(--muted);font-style:italic;padding:1rem 0}

.site-footer{max-width:1180px;margin:0 auto;padding:1.4rem 1.1rem 2rem;
  color:var(--muted);font-size:.85rem;border-top:1px solid var(--border)}

.epilogue{max-width:var(--maxw);margin:2.5rem auto 0;text-align:center;
  color:var(--accent-ink);font-weight:700;letter-spacing:.03em;line-height:2}
.epilogue p{margin:.2rem 0}
.appendix{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--border)}
.appendix-head{font-size:1.2rem;margin:0 0 .6rem}

.toast{position:fixed;left:50%;bottom:1.2rem;transform:translate(-50%,1.5rem);
  background:var(--text);color:var(--bg);padding:.6rem 1rem;border-radius:999px;
  font-size:.9rem;box-shadow:var(--shadow);opacity:0;pointer-events:none;
  transition:opacity .2s ease,transform .2s ease;z-index:60;max-width:90vw}
.toast.show{opacity:1;transform:translate(-50%,0)}

@media (min-width:821px){
  body{font-size:18px}
  .hero h1{font-size:1.9rem}
  .nav-toggle{display:none}
  .layout{grid-template-columns:clamp(220px,26vw,300px) minmax(0,1fr);gap:2rem}
  .sidebar{display:block !important;position:sticky;
    top:calc(var(--toolbar-h) + 16px);align-self:start;
    max-height:calc(100vh - var(--toolbar-h) - 32px);overflow:auto;padding-right:.3rem}
  .article-head{font-size:1.45rem}
}

@media print{
  .toolbar,.sidebar,.nav-toggle,.copy,.skip-link,.toast{display:none !important}
  .is-hidden{display:revert !important}
  body{font-size:12pt}
  .layout{display:block;max-width:none}
  .table-wrap{overflow:visible}
  a[href^="http"]::after{content:" (" attr(href) ")";font-size:.85em;color:#555}
}
"""

JS = r"""
(function(){
  "use strict";

  var input = document.getElementById('q');
  var countEl = document.getElementById('search-count');
  var noResults = document.getElementById('no-results');
  var commi = [].slice.call(document.querySelectorAll('.comma'));
  var containerArticoli = [].slice.call(document.querySelectorAll('.article:not(.leaf)'));
  var foglie = [].slice.call(document.querySelectorAll('.article.leaf, .appendix'));
  var filterable = [].slice.call(document.querySelectorAll('.filterable'));

  function norm(s){
    return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
  }
  commi.forEach(function(c){
    var art = c.closest('.article');
    var t = art ? (art.querySelector('.article-head') || {}).textContent || '' : '';
    c._search = norm(t + ' ' + c.textContent);
  });
  foglie.forEach(function(f){ f._search = norm(f.textContent); });

  function applica(){
    var q = norm(input.value.trim());
    var attivo = q.length > 0;
    var termini = q.split(/\s+/).filter(Boolean);
    function match(el){
      return !attivo || termini.every(function(t){ return el._search.indexOf(t) !== -1; });
    }
    var trovati = 0;

    commi.forEach(function(c){
      var ok = match(c);
      c.classList.toggle('is-hidden', !ok);
      if(ok && attivo) trovati++;
    });
    foglie.forEach(function(f){
      var ok = match(f);
      f.classList.toggle('is-hidden', attivo && !ok);
      if(ok && attivo) trovati++;
    });
    containerArticoli.forEach(function(a){
      var visibili = a.querySelectorAll('.comma:not(.is-hidden)').length;
      a.classList.toggle('is-hidden', attivo && visibili === 0);
    });
    filterable.forEach(function(el){ el.classList.toggle('is-hidden', attivo); });

    if(noResults) noResults.hidden = !(attivo && trovati === 0);
    if(countEl) countEl.textContent = attivo
      ? (trovati + (trovati === 1 ? ' risultato' : ' risultati')) : '';
  }
  if(input){
    input.addEventListener('input', applica);
    var qp = new URLSearchParams(location.search).get('q');
    if(qp){ input.value = qp; applica(); }
  }

  // Menu indice collassabile su mobile
  var toggle = document.querySelector('.nav-toggle');
  var sidebar = document.getElementById('indice');
  if(toggle && sidebar){
    toggle.addEventListener('click', function(){
      var open = sidebar.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    sidebar.addEventListener('click', function(e){
      if(e.target.closest('a') && window.matchMedia('(max-width:820px)').matches){
        sidebar.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // Copia link al comma
  var toast = document.getElementById('toast');
  var toastTimer;
  function mostraToast(msg){
    if(!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ toast.classList.remove('show'); }, 1800);
  }
  function urlComma(anchor){
    if(SITE_URL){ return SITE_URL.replace(/\/+$/,'') + '/#' + anchor; }
    if(location.protocol === 'file:'){ return location.href.replace(/#.*$/,'') + '#' + anchor; }
    return location.origin + location.pathname + '#' + anchor;
  }
  function legacy(text){
    try{
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly','');
      ta.style.position = 'fixed'; ta.style.top = '-1000px'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      var ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    }catch(e){ return false; }
  }
  function copia(text){
    if(navigator.clipboard && window.isSecureContext){
      return navigator.clipboard.writeText(text).then(
        function(){ return true; }, function(){ return legacy(text); });
    }
    return Promise.resolve(legacy(text));
  }
  document.addEventListener('click', function(e){
    var btn = e.target.closest('.copy');
    if(!btn) return;
    var anchor = btn.getAttribute('data-anchor');
    var url = urlComma(anchor);
    if(history.replaceState){ history.replaceState(null, '', '#' + anchor); }
    Promise.resolve(copia(url)).then(function(ok){
      mostraToast(ok ? 'Link copiato negli appunti' : url);
    });
  });
})();
"""


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    md_text, files = leggi_sorgenti()
    fm, corpo = separa_frontmatter(md_text)
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)  # via commenti HTML

    doc = costruisci_documento(corpo)
    stagione = stagione_da(fm, doc["titolo_raw"])
    data_dt, data_txt = data_ultima_modifica(files)

    pagina = costruisci_html(doc, stagione, data_dt, data_txt)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(pagina, encoding="utf-8")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")  # niente Jekyll

    n_commi = sum(len(a["commi"]) for a in doc["articoli"])
    n_sub = sum(len(c["sub"]) for a in doc["articoli"] for c in a["commi"])
    firme = "on" if INCLUDI_FIRME else "off"
    print(
        f"OK  {OUT_FILE.relative_to(ROOT)}  "
        f"({len(doc['articoli'])} articoli, {n_commi} commi, {n_sub} sotto-commi; "
        f"firme {firme}; ultima modifica {data_txt})"
    )


if __name__ == "__main__":
    main()
