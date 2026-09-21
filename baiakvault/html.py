"""Fragmentos de HTML: a moldura da pagina, o menu, tabelas e formatacao.

Sem framework, sem CDN, sem JavaScript por omissao. Mobile-first: le-se a
390 px e cresce ate 900 px. O CSS e um so ficheiro partilhado (`estilo.css`),
escrito pelo gerador ao lado das paginas.

A regra de ouro esta em `fmt`: um valor `None` sai sempre «?», nunca «None».
O teste `test_build` varre as paginas a procura de None/nan/undefined.
"""

UNKNOWN = "?"

CSS = """\
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#14161a;color:#e6e6e6;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:12px 12px 64px}
h1{font-size:20px;margin:6px 0 4px}
h2{font-size:16px;margin:22px 0 8px;color:#9fd0ff}
h3{font-size:14px;margin:14px 0 6px;color:#c9c9c9}
a{color:#9fd0ff}
nav.menu{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 14px}
nav.menu a{padding:5px 10px;border-radius:8px;background:#1d2128;color:#cfd6de;text-decoration:none;font-size:13px;border:1px solid #2a2f38}
nav.menu a.aqui{background:#243044;color:#fff}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:5px 6px;border-bottom:1px solid #2a2f38;text-align:left;vertical-align:top}
th{color:#9aa0a8;font-weight:600}
td.n,th.n{text-align:right;white-space:nowrap}
.tabela{overflow-x:auto}
.cartao{background:#1d2128;border:1px solid #2a2f38;border-radius:10px;padding:10px 12px;margin:10px 0}
.mudo{color:#9aa0a8}
.aviso{color:#e0a052;font-size:13px}
.marca{display:inline-block;padding:1px 6px;border-radius:6px;font-size:11px;background:#2a2f38;color:#cfd6de;margin-left:4px}
.marca.major{background:#3b2f14;color:#f0c46a}
.marca.minor{background:#1f2f3b;color:#9fd0ff}
.grelha{display:grid;grid-template-columns:1fr;gap:10px}
@media(min-width:640px){.grelha{grid-template-columns:1fr 1fr}}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;font-size:14px}
.kv dt{color:#9aa0a8}
.kv dd{margin:0}
footer{margin-top:32px;color:#6f7680;font-size:12px;border-top:1px solid #2a2f38;padding-top:10px}
code{background:#11141a;padding:1px 4px;border-radius:4px;font-size:12px}
small{font-size:12px}
section.nivel{border-top:2px solid #2a2f38;margin-top:18px;padding-top:6px}
h4{font-size:14px;margin:6px 0 4px;color:#c9c9c9}
details summary{cursor:pointer;color:#9fd0ff}
.kv table{font-size:12px}
ol.passos{padding-left:22px}ol.passos li{margin:6px 0}ol.passos li.mudo b{font-weight:normal}
"""


def esc(value):
    """Escapa para HTML. `None` sai «?» — e a regra, nao um acidente."""
    if value is None:
        return UNKNOWN
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def fmt(value, decimals=0, suffix=""):
    """Numero com separador de milhares a portuguesa (1.234.567). `None` -> «?»."""
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, float) and value != value:  # NaN
        return UNKNOWN
    try:
        if decimals:
            text = ("{:,.%df}" % decimals).format(float(value))
        else:
            text = "{:,}".format(int(round(float(value))))
    except (TypeError, ValueError):
        return esc(value)
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text + suffix


def kk(value):
    """1.234.567 -> «1,23 kk», como o jogo e o canal falam. `None` -> «?»."""
    if value is None:
        return UNKNOWN
    try:
        v = float(value)
    except (TypeError, ValueError):
        return esc(value)
    if abs(v) >= 1_000_000:
        return fmt(v / 1_000_000, 2, " kk")
    if abs(v) >= 1_000:
        return fmt(v / 1_000, 1, " k")
    return fmt(v)


def yes_no(value):
    if value is None:
        return UNKNOWN
    return "sim" if value else "nao"


def pct_of_100k(chance):
    """As chances do cliente vem por 100 000. `None` -> «?»."""
    if chance is None:
        return UNKNOWN
    return fmt(chance / 1000.0, 2, "%")


def nav(root, here=""):
    links = (("index.html", "Inicio", "inicio"),
             ("builds/index.html", "Builds", "builds"),
             ("hunts/index.html", "Hunts", "hunts"),
             ("charms/index.html", "Charms", "charms"),
             ("codex/index.html", "Codex", "codex"))
    parts = []
    for href, label, key in links:
        cls = ' class="aqui"' if key == here else ""
        parts.append('<a href="%s%s"%s>%s</a>' % (root, href, cls, label))
    return '<nav class="menu">%s</nav>' % "".join(parts)


def page(title, body, root="", here="", generated_at=None, extra_head=""):
    """A moldura inteira. `root` e o prefixo ate a raiz do site ("" ou "../")."""
    footer = ("<footer>BaiakVault v0.1 &middot; gerado a %s &middot; nada aqui toca no jogo "
              "nem na conta: le catalogos publicos e o que o Andre da.</footer>"
              % esc(generated_at))
    return ("<!doctype html><html lang=\"pt\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s</title><link rel=\"stylesheet\" href=\"%sestilo.css\">%s</head>"
            "<body><div class=\"wrap\">%s%s%s</div></body></html>"
            % (esc(title), root, extra_head, nav(root, here), body, footer))


def table(headers, rows, numeric=()):
    """`headers` e lista de texto; `rows` lista de listas ja formatadas (texto
    HTML pronto). `numeric` sao os indices de coluna alinhados a direita."""
    head = "".join('<th%s>%s</th>' % (' class="n"' if i in numeric else "", esc(h))
                   for i, h in enumerate(headers))
    body = []
    for row in rows:
        cells = "".join('<td%s>%s</td>' % (' class="n"' if i in numeric else "", c)
                        for i, c in enumerate(row))
        body.append("<tr>%s</tr>" % cells)
    return '<div class="tabela"><table><tr>%s</tr>%s</table></div>' % (head, "".join(body))


def kv(pairs):
    """Lista de definicoes chave -> valor (valores ja em HTML)."""
    return '<dl class="kv">%s</dl>' % "".join(
        "<dt>%s</dt><dd>%s</dd>" % (esc(k), v) for k, v in pairs)


def source_line(source, seen_at=None):
    text = "fonte: %s" % esc(source)
    if seen_at:
        text += " (visto a %s)" % esc(seen_at)
    return '<p class="mudo"><small>%s</small></p>' % text
