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
      build.py             o gerador: catalogo + vault.db (+ motor) -> docs/
      html.py              moldura, menu, tabelas, fmt (None -> «?»)
      notes.py             as notas BiS do canal CharllonLobo, por id de hunt, com o video
      formulas.py          as formulas do cliente (HP, arvore, feiticos) e as constantes com fonte
      sim.py               simulador de 60 s (Profile, Target, rotacao, pressao)
      builds.py            o optimizador: Planner.plan(vocacao, objectivo, nivel[, hunt]) -> a build
      pages_builds.py      paginas builds/, cartoes print/ e validacao
      advisor.py           o «proximo passo» de um personagem (puro: catalogo + estado + Planner)
      charms.py            charms por hunt: charm -> criatura com pontuacao, justificacao e mudancas (puro)
      pages_charms.py      guia dos 24 + «os teus charms», regras, seccoes das hunts/personagem/builds, cartoes print
      serve.py             docs/ + modo de edicao em /editar (unica porta de escrita)
      __main__.py          py -m baiakvault build | check | serve
    data/catalogo/         os JSON do jogo (copia do ai-pc) + bruto/charms.json
    data/vault.db          os dados DELE. Vai no git. So o Vault escreve
    data/serve.token       token de escrita do serve (nasce no 1.o arranque; fora do git)
    docs/                  o site gerado (Pages serve main:/docs). Com .nojekyll
    docs/charms.md         as regras dos charms lidas no cliente, com fonte e ⚠ — o contrato do charms.py (a mao)
    scripts/actualizar_catalogo.py   recopia e valida o catalogo a partir do ai-pc
    scripts/_ler_charms_bundle.py    le o bundle local a procura de «charm» (foi com isto que se escreveu o charms.md)
    tests/                 unittest, sem rede; fixtures: personagem.json (1) e personagens.json (1 por vocacao)
    capturas/              Win+Shift+S do Andre (fora do git)

## Como correr

    py -m baiakvault build          # gera docs/ (~10 s: as 64 builds do Planner; < 1 s sem elas)
    py -m baiakvault check          # valida catalogo + BD; sai != 0 se algo estiver mal
    py -m baiakvault serve          # docs/ em http://127.0.0.1:8774/ e o modo de edicao em /editar
    py -m unittest discover -s tests   # ~30 s (o Planner corre uma vez, em helpers.planner())
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

## Esquema da vault.db (v3)

Chaves sao as dos catalogos e validam-se ao escrever (chave desconhecida =
`VaultError`, nao insercao). `source` e 'manual' ou 'captura'; NULL onde nao
se sabe. `seen_at` = quando era verdade no jogo; `updated_at` = quando se
escreveu.

| tabela | chave | o que guarda |
|---|---|---|
| `characters` | name (unico), slug | vocation, level, current_hunt (hunts.id), vip 0/1, goal (v2: damage/tank/heal/support, so os da vocacao), notes |
| `character_tree` | (character_id, node_key) | rank; node_key = arvore.id (ex. `k_fury`), tem de ser da vocacao do personagem, rank <= maximo |
| `character_equipment` | (character_id, slot) | item_key = itens.nome em minusculas, item_name, upgrade_level, imbuements_json, attributes_json. Slots do catalogo + `backpack`/`ammo` |
| `character_charms` | (character_id, charm_key) | tier 1..3, assigned_creature_key (bestiario.chave) |
| `character_charm_points` | character_id | points_available, points_spent; v3: slot_limit (o Y de «X/Y monstros com charm»), expansion 0/1, echoes — leituras do ecra dos Charms; um campo a None nao apaga (`clear_charm_points_field` apaga) |
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
- **16/09/2026 (ordem 2-builds)** — As 8 builds pedidas: knight tank|damage,
  druid heal|damage, sorcerer damage, paladin damage, monk support|damage.
  Metricas: damage = DPS do ciclo (57 normais + boss x3 HP); tank = EHP x
  (1 + sustain) x DPS^0,3; heal/support = cura/s sustentavel em 60 s (propria
  + metade da aliada) x DPS^0,3. Arvore por guloso preguicoso (ganho relativo
  por ponto, com caminho de desbloqueio); equipamento por slot no simulador
  entre os 20 candidatos do pre-filtro; rotacao por forca bruta ate 4
  feiticos. Constantes sem fonte no cliente ficam marcadas «convencao ⚠»
  (`formulas.CONSTANTS`) e a regen base do servidor e desconhecida (None, nao
  entra). Os cartoes `print/` sao de proposito autonomos (sem `estilo.css`).
- **16/09/2026 (ordem 2-personagens)** — **Objectivos por vocacao** (esquema
  v2): knight `tank`|`damage`, druid `heal`|`damage`, sorcerer `damage`,
  paladin `damage`, monk `support`|`damage`; omissao = o primeiro (o que ele
  listou primeiro); `sustain` antigo migra para essa omissao. Mudar de vocacao
  com um objectivo que deixa de valer repoe a omissao da nova.
- **16/09/2026** — **Regras do advisor** (`advisor.py`): a referencia e
  `Planner.plan(voc, goal, nivel exacto, hunt actual)`; cada accao mede-se no
  simulador **com a arvore e o equipamento dele** (ganho % na metrica do
  objectivo). Ordem: medido antes de nao medido; entre medidos por ganho %;
  respec so se a recomendada render >= 5 % com a arvore dele toda gasta, e vale
  metade (custa gold); charm (0,5) e bestiario (0,25) a seguir; «falta
  preencher» (max. 2) fecha a lista; max. 7 linhas; ganhos < 0,5 % nao entram.
  Arvore com pontos por gastar: `builds.next_purchase` (ganho por ponto, com o
  caminho de desbloqueio na propria sugestao); sem pontos: o que comprar no
  nivel seguinte. Charms: o tipo do objectivo (damage -> offensive, resto ->
  defensive), subir um que ja tem antes de abrir outro, depois chance/ponto;
  so os que cabem nos pontos (senao «juntar pontos para»). Bestiario: «perto de
  fechar» = faltam <= 30 % da meta. Upgrade desconhecido conta a 0 e diz-se;
  tier de imbuement desconhecido conta ao minimo e diz-se; mochila nao entra;
  skill nao registado = o tipico do guia (marcado). O Andre vai querer afinar
  estes pesos: estao todos em constantes no topo do `advisor.py`.
- **16/09/2026** — **`serve` como unica porta de escrita**: POST exige sempre
  o token de `data/serve.token` (a pagina aberta de 127.0.0.1 mete-o nos
  formularios; de fora escreve-se a mao). Formularios sem JavaScript; em
  branco = «nao sei» (nao mexe), 0 = afirmacao; arvore e charms gravam-se em
  bloco, tudo ou nada (`set_tree_nodes`, `replace_charms`); apagar exige o
  nome exacto. Cada escrita regenera o site sem as paginas das builds
  (`build(with_builds=False)`, ~1 s), com o `Planner` em memoria.

- **16/09/2026 (ordem 3-charms)** — **As regras dos charms leram-se no
  cliente** (funcoes `d3e`/`l3e`/`c3e`/`OVe`/`Zbe`/`e3e`/`Jbe` e textos) e
  estao em `docs/charms.md` com fonte por regra; o guia nao tem pagina de
  charms e o video do canal nao se leu (sem yt-dlp; nao se instalou). O que
  ficou ⚠ («por confirmar»): se o dano elemental respeita a resistencia (o
  motor assume que sim), charms por conta vs por personagem (quase de certeza
  por conta; a BD continua por personagem), se procam em party, o
  `mainLevel` do custo de mover, e a «charm rune Divine Strike» do canal (nao
  existe no bundle; o mais proximo e Savage Blow T2 = +40 % crit).
- **16/09/2026** — **Regras do motor** (`charms.py`, constantes no topo):
  exposicao de uma criatura = HP abatido por ciclo (57 x peso x HP + boss x3
  HP); elementais = exposicao x min(2 x nivel, 5 % HP) x (1 - resistencia) x
  chance; Carnage = kills x min(15 % HP, 6 x nivel) x vizinhos (pack - 1, max
  4); Overpower/Overflux pelo HP/mana do dono (estimados pelo simulador; sem
  eles «?»); Dodge/Parry/Numb/Adrenaline/Cripple/Void Inversion na criatura
  de que mais dano se apanha (exposicao x dano/s, boss x1,5); Low Blow/Savage
  Blow/Fatal Hold/Vampiric/Void's Call na mais batida; Gut no loot em itens,
  Scavenge nas moedas (gold/platinum/crystal coin); Bless na criatura que
  aparece em mais hunts. Requisitos do equipamento (critico, roubo, escudo)
  so contam quando **conhecidos e > 0**: sem equipamento registado sao «?» e
  o charm fica de fora com o porque. Atribuicao gulosa **pelo arrependimento**
  (quem mais perde sem a 1.a escolha decide primeiro; maiores antes de
  menores) com as regras do jogo: um charm numa criatura, um maior + um menor
  por criatura, limite de criaturas (registado > VIP 6 > minimo 2), maior so
  com bestiario fechado (kills registados abaixo da meta = inelegivel;
  nao registados = aviso ⚠). Mudancas: atribuir (gratis), mover (1 000 x
  nivel, x0,75 com Expansion), fica. Sem pesos de spawn as criaturas contam
  por igual e diz-se.
- **16/09/2026** — **Resistencias**: 154 dos 240 monstros de hunt nao as tem
  no `bestiario.json`; para esses o motor le a **2.a tabela de combate do
  cliente** (`Wy`, guardada em `bosses.json` como `bosses_de_sala` — que
  afinal tem os 386 monstros do jogo, nao so bosses) e marca ⚠ (as duas
  tabelas divergem em 33 dos 86 monstros com ambas). Sem nenhuma: «?».
  Minor charms pagam-se em **echoes**, nao em pontos: o advisor so sugere
  maiores para subir.
- **16/09/2026** — Cartoes `print/charms-<slug>-<hunt>.html` so para a hunt
  actual + 5 vizinhas em nivel (`build.PRINT_NEIGHBOURS`). O «tecto» de uma
  hunt (todos os 24 ao tier 3, sem limite) usa o nivel minimo da hunt e nao
  tem HP/mana do dono (Overpower/Overflux ficam «?» ai). Conflitos entre
  charms de unidades diferentes (dano vs dano apanhado vs gold) resolvem-se
  so pelo arrependimento relativo — e um tecto, nao uma comparacao entre
  charms.
- **16/09/2026 (ordem 4)** — Tres tarefas no runner do ai-pc (`ai-pc\tasks\baiakvault-*`),
  molde `riftvault-serve`/`riftvault-publicar`: `baiakvault-serve` (5 min,
  vigia o `serve` no 8774), `baiakvault-publicar` (30 min, `check` + `build` +
  commit `dados <data>` + push quando o `vault.db` mudou e ja passou o
  sossego — o Pages serve `main:/docs` directo, e o push que publica),
  `baiakvault-leitura` (30 min, Claude local opus com visao le capturas de
  `capturas\` **e** `Desktop\BaiakIdle\capturas\`, valida contra o catalogo em
  Python e escreve na `vault.db` so pelo `db.Vault`, `source='captura'`; sem
  imagens novas nao gasta um token). **A partir desta ordem aplica-se a regra
  dos worktrees** (decisao do Andre, 08/09/2026, "faz logo o merge e push
  sempre"): as tarefas fazem push de `main`, por isso trabalho de codigo faz-se
  num worktree separado (`git -C <repo> worktree add "<repo>\..\_revisao\baiakvault"
  -b ai-pc/revisao-<data>`), merge `--no-ff` e push com a suite verde — nunca
  a meio na propria pasta de trabalho.
- **16/09/2026 (ordem 4)** — Os charms de uma captura do bestiario escrevem-se
  um a um (`set_charm`), nunca por `replace_charms`: o formulario do modo de
  edicao submete os 24 de uma vez (blank = "nao tem"), mas uma captura de ecra
  pode so mostrar um bocado da lista — `replace_charms` apagaria os que nao
  aparecessem nessa imagem.

## Fontes

- Catalogos: bundle publico do cliente, `https://baiakidle.com/jogar/assets/index-DnzxFejS.js` (09/09/2026). Extraccao: `ai-pc\knowledge\baiakidle\` (`_extrair_catalogos.py`, `dados\construir.py`, `dados\validar.py`). Duvidas e o que fica `null`: `ai-pc\knowledge\baiakidle\dados\duvidas.md`.
- Multiplicadores da wave 10 e escaloes de XP: `guiabaiakidle.com` (nao republicar os dados deles; `robots.txt` pede `use=reference`).
- Comunidade: canal CharllonLobo (YouTube), `baiak-builds.com` (nao verificada).
- O Treinador anterior (`Desktop\BaiakIdle\coach\`) e pedreira de codigo; copia-se e adapta-se, nao se importa.
