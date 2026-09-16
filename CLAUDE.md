# BaiakVault — CLAUDE.md

Ferramenta do Andre para o **Baiak Idle** (idle de browser, baiakidle.com), ao
estilo dos outros vaults dele (tibiavault, mtgvault, riftvault): um site
estatico proprio, gerado no PC por Python e publicado no GitHub Pages, feito
passo a passo. A v0.1 responde a duas coisas:

1. **Builds** — a build actual de cada personagem dele (arvore, equipamento,
   charms) e **o proximo passo**: o que comprar/subir/trocar a seguir, com o
   porque numa linha e a fonte.
2. **Charms por hunt** — que charm por em que criatura para cada hunt, a
   partir dos charms que ele tem.

Repo `Baverone/baiakvault` (publico). Site `https://baverone.github.io/baiakvault/`.

## A regra que nao se discute

**NADA toca na conta do Andre nem no servidor do jogo.** Sem Playwright, sem
`/api/trpc`, sem extensao, sem userscript, sem pedido HTTP a baiakidle.com com
sessao, sem clicar no jogo. Regras do servidor do jogo, seccao «Jogo limpo»
(extraidas do bundle do cliente, ver `Desktop\BaiakIdle\docs\termos.md`):

> «Bots externos, macros, scripts ou qualquer automacao de terceiros sao
> proibidos. O helper e as automacoes oficiais do Baiak Idle (combate,
> rotacao, coleta etc.) sao permitidos.»

Termos de Uso, seccao 3: «Contas que violarem as regras podem ser suspensas ou
removidas sem reembolso.» O servidor tem bot-score por conta e enumera
extensoes do browser. Decisao do Andre de 09/09/2026, reconfirmada a
16/09/2026.

Os dados do **jogo** vem dos catalogos ja extraidos do bundle publico (ficheiro
estatico, sem sessao) e de sites da comunidade. Os dados **dele** vem so do que
ele da: capturas de ecra lidas por visao pelo Claude local (ordem 4) ou o
formulario local do proprio BaiakVault (ordem 2).

## Estrutura

    baiakvault/            pacote Python (stdlib)
      catalog.py           le data/catalogo, indexa por chave, valida contagens e referencias
      schema.sql, db.py    esquema da vault.db (migracoes por PRAGMA user_version) e o Vault: unico sitio que escreve
      build.py             o gerador: catalogo + vault.db -> docs/
      html.py              moldura, menu, tabelas, fmt (None -> «?»)
      notes.py             as notas BiS do canal CharllonLobo, por id de hunt, com o video
      __main__.py          py -m baiakvault build | check | serve
    data/catalogo/         os JSON do jogo (copia do ai-pc) + bruto/charms.json
    data/vault.db          os dados DELE. Vai no git. So o Vault escreve
    docs/                  o site gerado (Pages serve main:/docs). Com .nojekyll
    scripts/actualizar_catalogo.py   recopia e valida o catalogo a partir do ai-pc
    tests/                 unittest, sem rede; fixture de personagem de exemplo
    capturas/              Win+Shift+S do Andre (fora do git)

## Como correr

    py -m baiakvault build          # gera docs/ (< 1 s)
    py -m baiakvault check          # valida catalogo + BD; sai != 0 se algo estiver mal
    py -m baiakvault serve          # serve docs/ em http://127.0.0.1:8774/ (so leitura na ordem 1)
    py -m unittest discover -s tests
    py scripts\actualizar_catalogo.py   # quando o jogo actualizar (a extraccao faz-se no ai-pc)

**Portos fixos no PC**: 8770 riftvault, 8771 mtgvault, 8773 o Treinador
antigo. **O BaiakVault usa o 8774.** Nao se trocam.

## Convencoes

- Python 3.14 **so biblioteca padrao**: sem pip, sem npm, sem build, sem
  frameworks/CDN no HTML. JavaScript vanilla minimo so quando fizer falta.
- Codigo, tabelas e funcoes em ingles; tudo o que o Andre le em **portugues de
  Portugal**. Commits curtos em portugues **sem acentos**. Um comando `git` de
  cada vez, nunca compostos nem `$(...)`.
- **Commit cedo e a cada passo estavel.**
- **Verdade acima de verde**: um passo que nao fez o que devia falha alto;
  nunca «ok» sem confirmar o efeito. Nunca inventar dados.
- **Desconhecido nao e zero**: o que nao se sabe fica NULL na BD e sai «?» na
  pagina, nao entra em conta nenhuma e nunca e substituido por um palpite.
- Comentarios explicam porque, nao o que. Decisoes com data aqui.
- Sem «None»/«nan»/«undefined» em pagina nenhuma (ha um teste a garantir).

## Esquema da vault.db (v1)

Chaves sao as dos catalogos e validam-se ao escrever (chave desconhecida =
`VaultError`, nao insercao). `source` e 'manual' ou 'captura'; NULL onde nao
se sabe. `seen_at` = quando era verdade no jogo; `updated_at` = quando se
escreveu.

| tabela | chave | o que guarda |
|---|---|---|
| `characters` | name (unico), slug | vocation, level, current_hunt (hunts.id), vip 0/1, goal damage/tank/sustain, notes |
| `character_tree` | (character_id, node_key) | rank; node_key = arvore.id (ex. `k_fury`), tem de ser da vocacao do personagem, rank <= maximo |
| `character_equipment` | (character_id, slot) | item_key = itens.nome em minusculas, item_name, upgrade_level, imbuements_json, attributes_json. Slots do catalogo + `backpack`/`ammo` |
| `character_charms` | (character_id, charm_key) | tier 1..3, assigned_creature_key (bestiario.chave) |
| `character_charm_points` | character_id | points_available, points_spent |
| `character_bestiary` | (character_id, creature_key) | kills |
| `readings` | id | historico: at, level, xp, gold, stamina (min), hunt — so se acrescenta, para o XP/h futuro |

Migracoes: `db.MIGRATIONS` e uma lista de scripts por versao; a v1 e o
`schema.sql` inteiro. Acrescenta-se ao fim, nunca se mexe nas anteriores.

## Decisoes (com data)

- **16/09/2026** — Site estatico no GitHub Pages a servir `main:/docs`, sem
  Actions (o build corre no PC). `vault.db` vai no git, como no riftvault.
  Stdlib only. **Uma so porta de escrita** na vault.db: o `serve` (modo de
  edicao, ordem 2) e a leitura de capturas (ordem 4) — ambos pelo `db.Vault`.
- **16/09/2026** — O catalogo vive **dentro do repo** (`data/catalogo/`),
  copiado do ai-pc por `scripts/actualizar_catalogo.py`, para o build nao
  depender de outra pasta. `catalog.EXPECTED` fixa as contagens de 09/09/2026;
  uma actualizacao do jogo tem de ser vista e registada aqui, nao absorvida.
- **16/09/2026** — Chave de item = `nome` em minusculas: o cliente nao da
  outra. Slots `backpack` e `ammo` aceitam-se na BD apesar de o catalogo nao
  dar slot a mochilas nem municao (existem no boneco).
- **16/09/2026** — O `upsert_character` com um campo a `None` **nao apaga** o
  que la estava (uma captura parcial nao pode limpar o resto); apagar de
  proposito e `clear_character_field`.
- **16/09/2026** — A ordem falava em 107 feiticos; o catalogo tem **187**
  (31+35+29+46+46). Testa-se o numero real.
- **16/09/2026** — `personagens/<slug>.html` ja se gera na ordem 1 (mostra o
  que esta na BD, com «?» no que falta); o «proximo passo» chega na ordem 2.
- **16/09/2026** — Notas do canal (`notes.py`) sao opiniao, saem sempre com o
  id do video e «nao medido» ao lado. XP/h e gold/h nao existem em fonte
  nenhuma e ficam «?» ate haver leituras.

## Fontes

- Catalogos: bundle publico do cliente, `https://baiakidle.com/jogar/assets/index-DnzxFejS.js` (09/09/2026). Extraccao: `ai-pc\knowledge\baiakidle\` (`_extrair_catalogos.py`, `dados\construir.py`, `dados\validar.py`). Duvidas e o que fica `null`: `ai-pc\knowledge\baiakidle\dados\duvidas.md`.
- Multiplicadores da wave 10 e escaloes de XP: `guiabaiakidle.com` (nao republicar os dados deles; `robots.txt` pede `use=reference`).
- Comunidade: canal CharllonLobo (YouTube), `baiak-builds.com` (nao verificada).
- O Treinador anterior (`Desktop\BaiakIdle\coach\`) e pedreira de codigo; copia-se e adapta-se, nao se importa.
