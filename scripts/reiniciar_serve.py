"""Deita abaixo o `baiakvault serve` que esta de pe no 8774, para o vigia
`baiakvault-serve` (runner do ai-pc, 5 min) o relancar com o codigo novo.

O serve fica de pe o dia todo e corre o CODIGO com que arrancou: depois de um
merge, o que esta no porto e a versao antiga. O mtgvault resolve isto com
`taskkill` por porto (`_reiniciar_webapp.py`); aqui a allowlist do ai-pc nega o
`taskkill`, por isso o proprio serve tem um POST `/reiniciar` (so do PC, com o
token de `data/serve.token`) que responde e sai. Sem `os.kill`, sem `netstat`.

Uso: `py scripts\\reiniciar_serve.py` (na raiz do baiakvault). Relancar ja:
`py C:\\Users\\Catarina\\Desktop\\ai-pc\\runner.py run baiakvault-serve`.
"""
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PORT = 8774
TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "serve.token"


def alive(port=PORT):
    s = socket.socket()
    s.settimeout(2)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def main():
    if not alive():
        print("nada a ouvir no %d" % PORT)
        return 0
    if not TOKEN_PATH.is_file():
        print("sem %s: nao consigo pedir o reinicio" % TOKEN_PATH)
        return 1
    token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    data = urllib.parse.urlencode({"token": token}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/reiniciar" % PORT, data=data), timeout=10) as r:
            print(r.read().decode("utf-8", "replace").strip())
    except urllib.error.HTTPError as e:
        print("o serve recusou (%s): e o codigo antigo sem /reiniciar? Entao so o vigia ou um reboot." % e.code)
        return 1
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        print("sem resposta (%s)" % e)
    for _ in range(15):
        if not alive():
            print("porto %d livre — o vigia `baiakvault-serve` relanca em <= 5 min "
                  "(ou: py C:\\Users\\Catarina\\Desktop\\ai-pc\\runner.py run baiakvault-serve)" % PORT)
            return 0
        time.sleep(1)
    print("o porto %d continua ocupado" % PORT)
    return 1


if __name__ == "__main__":
    sys.exit(main())
