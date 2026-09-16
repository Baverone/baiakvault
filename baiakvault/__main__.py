"""`py -m baiakvault build|serve|check`.

- `build`  gera o site para `docs/` (ou `--out`). Falha alto se o catalogo ou
           a BD estiverem mal — nao se publica meia pagina.
- `check`  valida catalogo + BD e sai != 0 se algo estiver mal. E o que as
           tarefas do runner do ai-pc vao usar.
- `serve`  serve `docs/` em http://127.0.0.1:8774/ para ver no telemovel em
           casa. Na ordem 1 e so leitura; o modo de edicao (a unica porta de
           escrita na vault.db) chega na ordem 2 neste mesmo comando.

Nada disto fala com o baiakidle.com.
"""
import argparse
import http.server
import os
import sys
from pathlib import Path

from . import build as build_module
from . import catalog as catalog_module
from . import db as db_module

PORT = 8774  # 8770 riftvault, 8771 mtgvault, 8773 o Treinador antigo


def cmd_check(args):
    problems = []
    try:
        cat = catalog_module.load(args.catalog)
        problems += ["catalogo: " + p for p in catalog_module.validate(cat)]
    except catalog_module.CatalogError as e:
        print("FALHA catalogo:", e)
        return 2
    db_path = Path(args.db or db_module.DEFAULT_PATH)
    if not db_path.is_file():
        problems.append("BD nao existe: %s (corre `py -m baiakvault build` para a criar)" % db_path)
    else:
        conn = db_module.connect(db_path)
        try:
            problems += ["vault.db: " + p for p in db_module.check(conn, cat)]
            n = conn.execute("SELECT count(*) FROM characters").fetchone()[0]
        finally:
            conn.close()
    if problems:
        for p in problems:
            print("ERRO", p)
        return 1
    print("OK catalogo (%s) e vault.db (%d personagens, esquema v%d)"
          % (", ".join("%s=%d" % kv for kv in sorted(cat.counts().items())),
             n, db_module.SCHEMA_VERSION))
    return 0


def cmd_build(args):
    cat = catalog_module.load(args.catalog)
    problems = catalog_module.validate(cat)
    if problems:
        for p in problems:
            print("ERRO catalogo:", p)
        return 1
    result = build_module.build(args.out, args.db, args.catalog)
    out = result["out"]
    if not (out / "index.html").is_file():
        print("FALHA: index.html nao ficou escrito em", out)
        return 1
    biggest = max(result["files"], key=lambda p: p.stat().st_size)
    print("gerado %d ficheiros em %s (%.2f s; %d personagens, %d hunts; maior: %s, %d KB)"
          % (len(result["files"]), out, result["seconds"], result["characters"],
             result["hunts"], biggest.name, biggest.stat().st_size // 1024))
    return 0


def cmd_serve(args):
    docs = Path(args.out or build_module.DEFAULT_OUT)
    if not (docs / "index.html").is_file():
        print("nao ha site em %s — corre `py -m baiakvault build` primeiro" % docs)
        return 1
    bind = os.environ.get("BAIAKVAULT_BIND", "127.0.0.1")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(docs), **k)
    with http.server.ThreadingHTTPServer((bind, args.port), handler) as srv:
        print("BaiakVault em http://%s:%d/ (so leitura; Ctrl+C para parar)" % (bind, args.port))
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="baiakvault", description=__doc__.splitlines()[0])
    ap.add_argument("--catalog", default=None, help="pasta do catalogo (data/catalogo)")
    ap.add_argument("--db", default=None, help="caminho da vault.db (data/vault.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="gera o site")
    b.add_argument("--out", default=None, help="pasta de saida (docs/)")
    b.set_defaults(fn=cmd_build)
    c = sub.add_parser("check", help="valida catalogo e BD; sai != 0 se algo estiver mal")
    c.set_defaults(fn=cmd_check)
    s = sub.add_parser("serve", help="serve docs/ no porto 8774")
    s.add_argument("--out", default=None)
    s.add_argument("--port", type=int, default=PORT)
    s.set_defaults(fn=cmd_serve)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
