"""O modo de edicao, com `http.client` num porto livre: GET das paginas, POST
valido grava (e regenera a pagina do personagem), POST sem token nao grava,
chave invalida nao grava e devolve erro legivel. Tudo numa BD temporaria."""
import http.client
import threading
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer

import helpers
from baiakvault import db, serve


class _Server:
    def __init__(self, cfg):
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(cfg))
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def request(self, method, path, fields=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        body = urllib.parse.urlencode(fields or {}) if fields is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded"} if body is not None else {}
        conn.request(method, path, body=body, headers=headers)
        r = conn.getresponse()
        data = r.read().decode("utf-8")
        location = r.getheader("Location")
        conn.close()
        return r.status, data, location

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class EditMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn, vault, cls.db_path = helpers.temp_vault(with_fixture=True)
        conn.close()
        cls.docs = helpers.temp_dir() / "docs"
        cls.docs.mkdir()
        (cls.docs / "index.html").write_text("<html>site</html>", encoding="utf-8")
        cls.token_path = helpers.temp_dir() / "serve.token"
        cfg = serve.Config(cls.docs, cls.db_path, helpers.ROOT / "data" / "catalogo", cls.token_path)
        cfg.planner = helpers.planner()[0]
        cls.cfg = cfg
        cls.token = cfg.token
        cls.server = _Server(cfg)

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def vault(self):
        conn = db.connect(self.db_path)
        return conn, db.Vault(conn, helpers.real_catalog())

    def test_token_file_is_created_and_shown_locally(self):
        self.assertTrue(self.token_path.is_file())
        self.assertGreater(len(self.token), 16)
        status, body, _ = self.server.request("GET", "/editar")
        self.assertEqual(status, 200)
        self.assertIn(self.token, body)  # pedido de 127.0.0.1: a pagina mostra-o

    def test_get_pages(self):
        status, body, _ = self.server.request("GET", "/")
        self.assertEqual(status, 200)  # o docs/ estatico (o placeholder, ou o site ja regenerado por outro teste)
        self.assertRegex(body, "site|BaiakVault")
        status, body, _ = self.server.request("GET", "/editar/teste-knight")
        self.assertEqual(status, 200)
        for text in ("Teste Knight", "Arvore", "Fury", "Equipamento", "eldritch tome", "Charms", "Wound", "Apagar"):
            self.assertIn(text, body)
        self.assertNotRegex(body, r"\b(None|nan|undefined)\b")
        status, _, _ = self.server.request("GET", "/editar/nao-existe")
        self.assertEqual(status, 404)
        status, body, _ = self.server.request("GET", "/saude")
        self.assertEqual(status, 200)

    def test_post_without_token_does_not_write(self):
        status, body, _ = self.server.request("POST", "/editar/teste-knight/personagem", {"level": "999"})
        self.assertEqual(status, 403)
        self.assertIn("token", body)
        conn, vault = self.vault()
        try:
            self.assertEqual(vault.character("teste-knight")["level"], 312)
        finally:
            conn.close()
        status, _, _ = self.server.request("POST", "/editar/teste-knight/personagem", {"level": "999", "token": "errado"})
        self.assertEqual(status, 403)

    def test_valid_post_writes_and_rebuilds(self):
        before = self.cfg.rebuilds
        status, body, location = self.server.request(
            "POST", "/editar/teste-knight/personagem",
            {"token": self.token, "level": "320", "vocation": "knight", "goal": "damage", "seen_at": "2026-09-16", "notes": ""})
        self.assertEqual(status, 303, body)
        self.assertTrue(location.startswith("/editar/teste-knight?ok="), location)
        conn, vault = self.vault()
        try:
            c = vault.character("teste-knight")
            self.assertEqual(c["level"], 320)
            self.assertEqual(c["goal"], "damage")
            self.assertEqual(c["source"], "manual")
            self.assertEqual(c["seen_at"], "2026-09-16")
            self.assertEqual(c["notes"], "fixture")  # em branco nao apaga
        finally:
            conn.close()
        self.assertEqual(self.cfg.rebuilds, before + 1)
        page = self.docs / "personagens" / "teste-knight.html"
        self.assertTrue(page.is_file())
        text = page.read_text(encoding="utf-8")
        self.assertIn("320", text)
        self.assertIn("Proximo passo", text)
        self.assertNotRegex(text, r"\b(None|nan|undefined)\b")
        self.assertIn("Teste Knight", (self.docs / "index.html").read_text(encoding="utf-8"))

    def test_invalid_key_is_rejected_readably_and_nothing_written(self):
        conn, vault = self.vault()
        try:
            cid = vault.character("teste-knight")["id"]
            tree_before = [(t["node_key"], t["rank"]) for t in vault.tree_of(cid)]
        finally:
            conn.close()
        # um no de outra vocacao no meio de nos validos: nada entra
        status, body, _ = self.server.request(
            "POST", "/editar/teste-knight/arvore",
            {"token": self.token, "rank_k_fury": "6", "rank_k_toughness": "3", "rank_s_fury": "1", "seen_at": "2026-09-16"})
        self.assertEqual(status, 400)
        self.assertIn("Nao gravado", body)
        self.assertIn("s_fury", body)
        # rank acima do maximo
        status, body, _ = self.server.request(
            "POST", "/editar/teste-knight/arvore", {"token": self.token, "rank_k_fury": "99"})
        self.assertEqual(status, 400)
        self.assertIn("rank maximo", body)
        # item de outro slot
        status, body, _ = self.server.request(
            "POST", "/editar/teste-knight/equipamento", {"token": self.token, "slot": "helmet", "item": "eldritch tome"})
        self.assertEqual(status, 400)
        self.assertIn("shield", body)
        # hunt desconhecida
        status, body, _ = self.server.request(
            "POST", "/editar/teste-knight/personagem", {"token": self.token, "current_hunt": "narnia"})
        self.assertEqual(status, 400)
        self.assertIn("hunt desconhecida", body)
        conn, vault = self.vault()
        try:
            cid = vault.character("teste-knight")["id"]
            self.assertEqual([(t["node_key"], t["rank"]) for t in vault.tree_of(cid)], tree_before)
            self.assertNotIn("helmet", [e["slot"] for e in vault.equipment_of(cid)])
        finally:
            conn.close()

    def test_tree_equipment_charms_bestiary_forms(self):
        t = self.token
        status, _, loc = self.server.request(
            "POST", "/editar/teste-knight/arvore",
            {"token": t, "rank_k_fury": "7", "rank_k_toughness": "", "rank_k_vigor": "0", "seen_at": "2026-09-16"})
        self.assertEqual(status, 303)
        status, _, _ = self.server.request(
            "POST", "/editar/teste-knight/equipamento",
            {"token": t, "slot": "helmet", "item": "Cobra Hood", "upgrade": "3", "imbuements": "Vampirism:2, strike",
             "attr_crit_chance": "2,5", "seen_at": "2026-09-16"})
        self.assertEqual(status, 303)
        status, _, _ = self.server.request(
            "POST", "/editar/teste-knight/equipamento", {"token": t, "slot": "boots", "vazio": "on", "imbuements": "nenhum",
                                                          "sem_atributos": "on"})
        self.assertEqual(status, 303)
        status, _, _ = self.server.request(
            "POST", "/editar/teste-knight/charms",
            {"token": t, "tier_wound": "3", "criatura_wound": "Cobra Vizier", "tier_dodge": "", "tier_parry": "1",
             "points_available": "120", "points_spent": "", "seen_at": "2026-09-16"})
        self.assertEqual(status, 303)
        status, _, _ = self.server.request(
            "POST", "/editar/teste-knight/bestiario", {"token": t, "criatura": "Cobra Scout", "kills": "2400"})
        self.assertEqual(status, 303)
        conn, vault = self.vault()
        try:
            cid = vault.character("teste-knight")["id"]
            tree = {r["node_key"]: r for r in vault.tree_of(cid)}
            self.assertEqual(tree["k_fury"]["rank"], 7)
            self.assertEqual(tree["k_toughness"]["rank"], 2)   # em branco nao mexe
            self.assertEqual(tree["k_vigor"]["rank"], 0)       # 0 e uma afirmacao
            self.assertEqual(tree["k_fury"]["source"], "manual")
            eq = {e["slot"]: e for e in vault.equipment_of(cid)}
            self.assertEqual(eq["helmet"]["item_key"], "cobra hood")
            self.assertEqual(eq["helmet"]["upgrade_level"], 3)
            self.assertEqual(eq["helmet"]["imbuements"], ["vampirism:2", "strike"])
            self.assertEqual(eq["helmet"]["attributes"], {"crit_chance": 2.5})
            self.assertIsNone(eq["boots"]["item_key"])
            self.assertEqual(eq["boots"]["imbuements"], [])
            self.assertEqual(eq["boots"]["attributes"], {})
            charms = {c["charm_key"]: c for c in vault.charms_of(cid)}
            self.assertEqual(set(charms), {"wound", "parry"})   # dodge saiu: «nao tem»
            self.assertEqual(charms["wound"]["tier"], 3)
            self.assertEqual(charms["wound"]["assigned_creature_key"], "cobra_vizier")
            points = vault.charm_points_of(cid)
            self.assertEqual(points["points_available"], 120)
            self.assertIsNone(points["points_spent"])
            best = {b["creature_key"]: b["kills"] for b in vault.bestiary_of(cid)}
            self.assertEqual(best["cobra_scout"], 2400)
        finally:
            conn.close()

    def test_delete_needs_exact_name(self):
        t = self.token
        status, _, _ = self.server.request("POST", "/editar/novo", {"token": t, "name": "Efemero", "vocation": "druid"})
        self.assertEqual(status, 303)
        status, body, _ = self.server.request("POST", "/editar/efemero/apagar", {"token": t, "confirmar": "efemero"})
        self.assertEqual(status, 400)
        status, _, loc = self.server.request("POST", "/editar/efemero/apagar", {"token": t, "confirmar": "Efemero"})
        self.assertEqual(status, 303)
        self.assertTrue(loc.startswith("/editar?ok="))
        conn, vault = self.vault()
        try:
            self.assertIsNone(vault.character("efemero"))
        finally:
            conn.close()


class Choices(unittest.TestCase):
    def test_item_choices_respect_slot_vocation_level(self):
        cat = helpers.real_catalog()
        names = serve.item_choices(cat, "shield", "knight", 100)
        self.assertTrue(names)
        for n in names:
            item = cat.item_by_key[n.lower()]
            self.assertEqual(item["slot"], "shield")
            self.assertLessEqual(item.get("nivel") or 0, 100)
            self.assertTrue(not item.get("vocacoes") or "knight" in item["vocacoes"])
        self.assertIn("ghost backpack", serve.item_choices(cat, "backpack"))
        ammo = serve.item_choices(cat, "ammo")
        self.assertTrue(ammo)
        self.assertTrue(all(cat.item_by_key[n.lower()].get("municao") for n in ammo))


if __name__ == "__main__":
    unittest.main()
