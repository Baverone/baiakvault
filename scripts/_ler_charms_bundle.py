r"""Leitura local do bundle do cliente a procura das regras dos charms.

Ficheiro estatico ja descarregado no ai-pc (sem sessao, sem rede). Imprime os
trechos a volta de cada aglomerado de «charm» para leitura humana. Foi com isto
que se escreveu `docs/charms.md` (ordem 3, 16/09/2026); nao faz parte do build.

Uso: py scripts\_ler_charms_bundle.py [lista | <indice do aglomerado> [margem] | grep <regex> [margem]]
"""
import re
import sys

BUNDLE = (r"C:\Users\Catarina\Desktop\ai-pc\knowledge\baiakidle\_raw"
          r"\baiakidle-com-jogar-assets-index-DnzxFejS-js.html")


def load():
    return open(BUNDLE, encoding="utf-8", errors="replace").read()


def clusters(text, pattern=r"(?i)charm", gap=400):
    out = []
    for m in re.finditer(pattern, text):
        i = m.start()
        if out and i - out[-1][1] < gap:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def main(argv):
    text = load()
    if argv and argv[0] == "grep":
        for m in re.finditer(argv[1], text):
            a = max(0, m.start() - int(argv[2]) if len(argv) > 2 else m.start() - 300)
            b = min(len(text), m.end() + (int(argv[2]) if len(argv) > 2 else 300))
            print("=== %d" % m.start())
            print(text[a:b])
        return
    cl = clusters(text)
    if not argv or argv[0] == "lista":
        print("%d chars, %d aglomerados" % (len(text), len(cl)))
        for n, (a, b) in enumerate(cl):
            print("%3d  %8d..%8d  (%d)  %s" % (n, a, b, b - a, text[a - 60:a + 80].replace("\n", " ")))
        return
    n = int(argv[0])
    a, b = cl[n]
    pad = int(argv[1]) if len(argv) > 1 else 600
    print(text[max(0, a - pad):min(len(text), b + pad)])


if __name__ == "__main__":
    main(sys.argv[1:])
