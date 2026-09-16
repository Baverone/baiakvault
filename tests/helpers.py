"""Apoio aos testes: o catalogo verdadeiro (e o do repo, sem rede) e uma BD
temporaria carregada com a fixture. Sem personagens reais em lado nenhum."""
import json
import tempfile
import time
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


_PLANNER = None
_PLANS = None
PLAN_SECONDS = None


def planner():
    """`(Planner, {(voc, goal, level): build})` — as 8 builds x 8 niveis, calculadas uma vez
    para a bateria toda (uns 8 s) e cronometradas em `PLAN_SECONDS`."""
    global _PLANNER, _PLANS, PLAN_SECONDS
    if _PLANNER is None:
        from baiakvault import builds
        started = time.perf_counter()
        pl = builds.Planner(real_catalog())
        plans = {}
        for voc, goal in builds.BUILDS:
            for level in builds.LEVELS:
                plans[(voc, goal, level)] = pl.plan(voc, goal, level)
        PLAN_SECONDS = time.perf_counter() - started
        _PLANNER, _PLANS = pl, plans
    return _PLANNER, _PLANS


def temp_dir():
    return Path(tempfile.mkdtemp(prefix="baiakvault-test-"))


def fixture():
    return json.loads((FIXTURES / "personagem.json").read_text(encoding="utf-8"))


def load_fixture(vault, data=None):
    """Escreve a fixture pelo `Vault` (o unico caminho de escrita), como fara o
    modo de edicao. Devolve o id do personagem."""
    data = data or fixture()
    cid = vault.upsert_character(**data["character"])
    for t in data.get("tree") or []:
        vault.set_tree_node(cid, **t)
    for e in data.get("equipment") or []:
        vault.set_equipment(cid, **e)
    for c in data.get("charms") or []:
        vault.set_charm(cid, **c)
    if data.get("charm_points"):
        vault.set_charm_points(cid, **data["charm_points"])
    for b in data.get("bestiary") or []:
        vault.set_bestiary(cid, **b)
    for r in data.get("readings") or []:
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
