"""Apoio aos testes: o catalogo verdadeiro (e o do repo, sem rede) e uma BD
temporaria carregada com a fixture. Sem personagens reais em lado nenhum."""
import json
import tempfile
from pathlib import Path

from baiakvault import catalog, db

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

_CATALOG = None


def real_catalog():
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = catalog.load(ROOT / "data" / "catalogo")
    return _CATALOG


def temp_dir():
    return Path(tempfile.mkdtemp(prefix="baiakvault-test-"))


def fixture():
    return json.loads((FIXTURES / "personagem.json").read_text(encoding="utf-8"))


def load_fixture(vault, data=None):
    """Escreve a fixture pelo `Vault` (o unico caminho de escrita), como fara o
    modo de edicao. Devolve o id do personagem."""
    data = data or fixture()
    cid = vault.upsert_character(**data["character"])
    for t in data["tree"]:
        vault.set_tree_node(cid, **t)
    for e in data["equipment"]:
        vault.set_equipment(cid, **e)
    for c in data["charms"]:
        vault.set_charm(cid, **c)
    vault.set_charm_points(cid, **data["charm_points"])
    for b in data["bestiary"]:
        vault.set_bestiary(cid, **b)
    for r in data["readings"]:
        vault.add_reading(cid, **r)
    return cid


def temp_vault(with_fixture=False):
    """`(conn, vault, db_path)` numa pasta temporaria."""
    path = temp_dir() / "vault.db"
    conn = db.connect(path)
    vault = db.Vault(conn, real_catalog())
    if with_fixture:
        load_fixture(vault)
    return conn, vault, path
