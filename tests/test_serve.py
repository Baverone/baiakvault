"""O modo de edicao, com `http.client` num porto livre: GET das paginas, POST
valido grava (e regenera a pagina do personagem), POST sem token nao grava,
chave invalida nao grava e devolve erro legivel. Tudo numa BD temporaria."""
import http.client
import threading
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer

import helpers
from baiakvault import db, html as h, serve, treecode


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
             "points_available": "120", "points_spent": "", "slot_limit": "6", "expansion": "0", "echoes": "",
             "seen_at": "2026-09-16"})
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
            self.assertEqual(points["slot_limit"], 6)
            self.assertEqual(points["expansion"], 0)
            self.assertIsNone(points["echoes"])
            best = {b["creature_key"]: b["kills"] for b in vault.bestiary_of(cid)}
            self.assertEqual(best["cobra_scout"], 2400)
        finally:
            conn.close()

    def test_tree_code_import_and_fixed_rotation(self):
        """Ordem 8: o codigo «Exportar» do cliente grava a arvore inteira (validado como o
        cliente valida: vocacao, ligacao, orcamento); a rotacao e a arma fixadas gravam-se e
        a pagina do personagem mostra o codigo da recomendada com o custo de importar."""
        t = self.token
        cat = helpers.real_catalog()
        status, _, _ = self.server.request("POST", "/editar/novo", {"token": t, "name": "Codigo", "vocation": "sorcerer"})
        self.assertEqual(status, 303)
        status, _, _ = self.server.request("POST", "/editar/codigo/personagem", {"token": t, "level": "471", "vocation": "sorcerer",
                                                                                "current_hunt": "livrariafire-cave"})
        self.assertEqual(status, 303)
        # codigo invalido, de outra vocacao e acima do nivel: nada gravado, erro legivel
        for code, why in (("lixo", "invalido"), (treecode.encode(cat, "druid", 471, {"d_nature": 1}), "vocacao"),
                          (treecode.encode(cat, "sorcerer", 471, {"s_arcane": 10, "s_wildfire": 10, "s_energy": 10} | {
                              n["id"]: n["rank_maximo"] for n in cat.tree_by_vocation["sorcerer"]["nos"] if n["tier"] <= 2}), "nivel")):
            status, body, _ = self.server.request("POST", "/editar/codigo/arvore/codigo", {"token": t, "codigo": code})
            self.assertEqual(status, 400, why)
            self.assertIn("Nao gravado", body)
        conn, vault = self.vault()
        try:
            cid = vault.character("codigo")["id"]
            self.assertEqual(vault.tree_of(cid), [])
        finally:
            conn.close()
        # o codigo do supervisor para o sorcerer 471: grava os 203... nao, os nos da vocacao todos (0 = afirmacao)
        alloc = {"s_arcane": 10, "s_wildfire": 10, "s_energy": 5, "s_conduit": 5, "s_crit": 4, "s_soulharvest": 1, "s_reaper": 1,
                 "s_deathchill": 1, "s_archmage": 5, "s_tactics": 7, "s_voidtouch": 1, "s_cataclysm": 5, "s_stormcall": 3,
                 "s_focus_mastery": 1, "s_overchannel": 7, "s_scorch": 1, "s_inferno": 6, "s_devastate": 2, "s_haste": 1}
        code = treecode.encode(cat, "sorcerer", 471, alloc)
        self.assertEqual(code, "BT1-S471-A50005005410205001100600000007010113710A")
        status, _, loc = self.server.request("POST", "/editar/codigo/arvore/codigo", {"token": t, "codigo": code.lower(),
                                                                                     "seen_at": "2026-09-16"})
        self.assertEqual(status, 303)
        self.assertIn("471 pontos gastos", urllib.parse.unquote(loc))
        conn, vault = self.vault()
        try:
            cid = vault.character("codigo")["id"]
            tree = {r["node_key"]: r["rank"] for r in vault.tree_of(cid)}
            self.assertEqual({k: v for k, v in tree.items() if v}, alloc)
            self.assertEqual(len(tree), len(cat.tree_by_vocation["sorcerer"]["nos"]))
            self.assertEqual(vault.tree_of(cid)[0]["source"], "manual")
        finally:
            conn.close()
        # a rotacao fixada
        status, _, loc = self.server.request("POST", "/editar/codigo/rotacao", {"token": t, "spell_0": "Rage of the Skies",
                                                                               "spell_1": "Avalanche", "spell_2": "", "spell_3": ""})
        self.assertEqual(status, 303)
        status, body, _ = self.server.request("POST", "/editar/codigo/rotacao", {"token": t, "spell_0": "Fierce Berserk"})
        self.assertEqual(status, 400)
        conn, vault = self.vault()
        try:
            c = vault.character("codigo")
            self.assertEqual(c["fixed_rotation"], ["Rage of the Skies", "Avalanche"])
        finally:
            conn.close()
        page = (self.docs / "personagens" / "codigo.html").read_text(encoding="utf-8")
        self.assertIn("Rotacao de hunt fixada por ti", page)
        self.assertIn("Rage of the Skies, Avalanche", page)
        self.assertIn('value="BT1-S471-', page)
        self.assertIn("Copiar", page)
        self.assertIn(h.kk(treecode.import_cost(471)), page)   # o custo de importar pelos 471 pontos que a BD diz
        self.assertIn("pelas regras do cliente", page)
        self.assertTrue((self.docs / "print" / "helper-personagem-codigo.html").is_file())
        self.assertIn("rotacao de hunt fixada por ti", (self.docs / "print" / "helper-personagem-codigo.html").read_text(encoding="utf-8"))
        self.assertNotRegex(page, r"\b(None|nan|undefined)\b")
        status, body, _ = self.server.request("GET", "/editar/codigo")
        self.assertIn("Cola aqui o codigo Exportar", body)
        self.assertIn("Rotacao e arma fixadas", body)
        self.assertIn('selected>Avalanche', body)

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

    def test_concurrent_posts_all_land_and_the_site_regenerates_once_per_post(self):
        # o servidor e multi-thread: duas gravacoes ao mesmo tempo nao podem partilhar o
        # Planner a meio de uma regeneracao (caches sem protecao) — o lock serializa-as
        before = self.cfg.rebuilds
        results = []

        def post(level):
            results.append(self.server.request("POST", "/editar/teste-knight/personagem",
                                               {"token": self.token, "level": str(level)}))
        threads = [threading.Thread(target=post, args=(300 + i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(120)
        self.assertEqual([r[0] for r in results], [303, 303, 303], results)
        self.assertEqual(self.cfg.rebuilds, before + 3)
        conn, vault = self.vault()
        try:
            self.assertIn(vault.character("teste-knight")["level"], (300, 301, 302))
        finally:
            conn.close()
        # repoe o nivel da fixture: os outros testes desta classe contam com ele
        status, _, _ = self.server.request("POST", "/editar/teste-knight/personagem", {"token": self.token, "level": "312"})
        self.assertEqual(status, 303)

    def test_new_character_with_same_name_in_other_case_is_not_a_crash(self):
        t = self.token
        status, _, loc = self.server.request("POST", "/editar/novo", {"token": t, "name": "teste knight", "vocation": "knight"})
        self.assertEqual(status, 303)   # e o Teste Knight da fixture, nao um segundo boneco
        self.assertTrue(loc.startswith("/editar/teste-knight?ok="), loc)
        conn, vault = self.vault()
        try:
            self.assertEqual([c["slug"] for c in vault.characters() if c["slug"] == "teste-knight"], ["teste-knight"])
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
