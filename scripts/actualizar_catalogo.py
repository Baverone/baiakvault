"""Recopia o catalogo do jogo do ai-pc para `data/catalogo/` e valida-o.

A extraccao do bundle do jogo NAO se faz aqui: faz-se no ai-pc, com os scripts
de `knowledge\\baiakidle\\` (ver `Desktop\\BaiakIdle\\docs\\dados.md`):

    py knowledge\\baiakidle\\_fetch.py -q https://baiakidle.com/jogar/
    (ler o <script src> novo e trocar BUNDLE_URL/BUNDLE no _extrair_catalogos.py)
    py knowledge\\baiakidle\\_fetch.py -q <o bundle novo>
    py knowledge\\baiakidle\\_extrair_catalogos.py
    py knowledge\\baiakidle\\dados\\construir.py
    py knowledge\\baiakidle\\dados\\validar.py

Depois disso, este script traz os JSON para dentro do repo — o site gera-se so
a partir de `data/catalogo/`, para o repo ser auto-contido e o build nao
depender de outra pasta do PC. Falha alto se um ficheiro faltar ou se as
contagens nao baterem com o que `catalog.validate` espera.

    py scripts\\actualizar_catalogo.py            # copia + valida
    py scripts\\actualizar_catalogo.py --origem X  # outra pasta de origem
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from baiakvault import catalog  # noqa: E402

ORIGEM_POR_OMISSAO = Path(os.environ.get(
    "BAIAKVAULT_AIPC_DADOS",
    r"C:\Users\Catarina\Desktop\ai-pc\knowledge\baiakidle\dados"))


def copiar(origem, destino):
    origem, destino = Path(origem), Path(destino)
    if not origem.is_dir():
        raise SystemExit("origem nao existe: %s" % origem)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "bruto").mkdir(exist_ok=True)
    copiados = []
    for nome in catalog.FILES:
        src = origem / (nome + ".json")
        if not src.is_file():
            raise SystemExit("falta na origem: %s" % src)
        shutil.copyfile(src, destino / (nome + ".json"))
        copiados.append(nome + ".json")
    for nome in catalog.RAW_FILES:
        src = origem / "bruto" / (nome + ".json")
        if not src.is_file():
            raise SystemExit("falta na origem: %s" % src)
        shutil.copyfile(src, destino / "bruto" / (nome + ".json"))
        copiados.append("bruto/" + nome + ".json")
    return copiados


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--origem", default=str(ORIGEM_POR_OMISSAO))
    ap.add_argument("--destino", default=str(catalog.DEFAULT_DIR))
    args = ap.parse_args(argv)

    copiados = copiar(args.origem, args.destino)
    for c in copiados:
        print("copiado", c)
    cat = catalog.load(args.destino)
    problemas = catalog.validate(cat)
    if problemas:
        for p in problemas:
            print("ERRO", p)
        return 1
    print("catalogo valido:", ", ".join("%s=%d" % kv for kv in sorted(cat.counts().items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
