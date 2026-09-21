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
      treecode.py          o codigo de build do cliente (BT1-…, V3e/U3e) e as regras da arvore (MK/LK/O3e/yD/Ik/z3e/Up/F3e/j3e/fD) a letra
      builds.py            o optimizador: Planner.plan(vocacao, objectivo, nivel[, hunt, rotacao/arma fixadas]) -> a build
      pages_builds.py      paginas builds/, cartoes print/ e a validacao cruzada (markdown gerado)
      validation.py        contas a mao so com os JSON (NAO importa formulas/sim: e a verificacao independente), curva do guia, discordancias guia/cliente
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
    docs/builds/validacao.md   GERADO pelo build (validation.py): nao se edita a mao
    scripts/actualizar_catalogo.py   recopia e valida o catalogo a partir do ai-pc
    scripts/_ler_charms_bundle.py    le o bundle local a procura de «charm» (foi com isto que se escreveu o charms.md)
    tests/                 unittest, sem rede; fixtures: personagem.json (1), personagens.json (1 por vocacao), codigos.json (os 5 codigos de build do supervisor); test_priority.py = as prioridades do Andre (ordem 9) e a migracao v6
    capturas/              Win+Shift+S do Andre (fora do git)

## Como correr

    py -m baiakvault build          # gera docs/ (~2 min desde a ordem 8: 104 builds a ~1,2 s cada; ~10 s sem elas)
    py -m baiakvault check          # valida catalogo + BD; sai != 0 se algo estiver mal
    py -m baiakvault serve          # docs/ em http://127.0.0.1:8774/ e o modo de edicao em /editar
    py -m unittest discover -s tests   # ~5 min (o Planner corre uma vez, em helpers.planner())
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

## Esquema da vault.db (v6)

Chaves sao as dos catalogos e validam-se ao escrever (chave desconhecida =
`VaultError`, nao insercao). `source` e 'manual' ou 'captura'; NULL onde nao
se sabe. `seen_at` = quando era verdade no jogo; `updated_at` = quando se
escreveu.

| tabela | chave | o que guarda |
|---|---|---|
| `characters` | name (unico), slug | vocation, level, current_hunt (hunts.id), vip 0/1, goal (v2/v4: best/damage/tank/heal/support, so os da vocacao; v6: mais `priority`, a omissao de todas), notes; v5: fixed_rotation_json (lista ordenada de nomes de feiticos da vocacao, ate 4) e fixed_weapon (itens.nome) — o que ELE fixou; NULL = nao fixou |
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
- **16/09/2026 (ordem 5, revisao)** — **Resistencias tambem no simulador**: o
  `sim.Target` contava a 0 % os 154 monstros de hunt sem resistencias no
  bestiario (47 das 79 hunts; Elder Wyrm 75 % terra, Werelion 50 % terra...)
  enquanto o motor dos charms ja lia a 2.a tabela. Agora ha **uma so leitura**,
  `catalog.Catalog.resistances(criatura)` (bestiario > 2.a tabela ⚠ > `None`),
  usada pelos dois; um monstro sem nenhuma nao entra na media (nao e zero) e a
  pagina da build diz de onde vieram. As 64 builds foram regeneradas com isto.
- **16/09/2026 (ordem 5)** — **Um charm que pontua zero nao se atribui**
  (ex.: Poison numa hunt onde tudo e imune a terra): com opcoes todas a 0 o
  arrependimento «1 - 0» punha-o a decidir primeiro e a ocupar a melhor
  criatura sem fazer nada, empurrando Wound e Dodge. Sai «nao faz nada nesta
  hunt» com o porque. Um **menor exige 1 kill** registado (cliente `d3e`);
  loot desconhecido e «?» para Gut/Scavenge, nao 0.
- **16/09/2026 (ordem 5)** — **`docs/builds/validacao.md` e gerado** por
  `validation.py` + `pages_builds.validation_markdown` (o placeholder apontava
  para um `scripts/validar_guia.py` que nunca existiu). Tres partes: contas a
  mao de um perfil fixo (sorcerer 50 em Crawler, a arvore/equipamento da
  pagina de 16/09) refeitas **so com os JSON e sem importar `formulas`/`sim`**
  (o teste `test_validation` prova a independencia e chumba acima de 1 % de
  diferenca); a curva de DPS do guia (`7,012 x nivel^0,948`) ao lado do DPS do
  ciclo de cada build/nivel, sem tolerancia (e para ver, nao para esconder); e
  as constantes em que o guia e o cliente discordam. Pedido do Andre: «quero
  que isto seja sempre validado».
- **16/09/2026 (ordem 5)** — `db.upsert_character`: um nome que so difere em
  maiusculas/minusculas (**mesmo slug**) e o mesmo personagem — actualiza-se,
  o nome guardado fica o primeiro (antes rebentava com `IntegrityError` cru no
  UNIQUE do slug, sem passar pelo «nao gravado» do serve). **Mudar a vocacao
  com nos da arvore registados e `VaultError`** («limpa a arvore primeiro»):
  a arvore da vocacao antiga ficava impossivel na BD e o `check` chumbava a
  publicacao a seguir. O `serve` apanha `sqlite3.Error` como «nao gravado»
  (rede de seguranca) e serializa as regeneracoes com um lock (o `Planner`
  tem caches sem protecao e o servidor e multi-thread).
- **16/09/2026 (ordem 5)** — O build **apaga o que e dele e ficou orfao**
  (`personagens/*.html`, `print/charms-*.html`, `hunts/*.html`; com builds
  tambem `builds/*.html` e `print/helper-*.html`): um personagem apagado ou
  renomeado deixava a pagina antiga em `docs/` e ia para o Pages. Nunca toca
  em ficheiros fora dessas pastas/padroes.

- **16/09/2026 (ordem 6, supervisao — fechada na ordem 7)** — A ordem 6 morreu por
  timeout com o codigo a meio (sem commit, `build.py` sem compilar); a ordem 7
  fechou-a ao minimo. (1) **Leech so no ataque normal e nos strikes** (`sim`: nunca
  areas nem curas; fonte: texto dos charms Vampiric Embrace/Void's Call,
  `formulas.LEECH_SCOPE`). (2) **Poupar para um notable** so quando o pacote rende
  >= 1,1x o que os mesmos pontos rendem nos outros nos, medidos no simulador ao
  nivel em que se chega la (`builds.SAVE_*`; a regra «<= 15 % do nivel ou <= 60
  niveis» proibiria para sempre notables acima de 60 pontos). (3) **Build «best»**
  por vocacao, omissao de cada uma (esquema **v4**): DPS do ciclo x (fraccao
  cumprida de cada condicao)^2 — aguentar o pack inteiro e o boss > 10 min (60 s
  simulados com curas/pocoes, tendencia extrapolada), mana sustentavel
  (knight/monk sem pocoes; os outros sem esgotar), druid a cobrir a pressao do
  pack sobre o knight «best» da mesma party. O caminho da arvore pode ser por hunt
  (`Planner.path(..., hunt_id)`), so acima do nivel minimo dela. (4) Os 5
  personagens dele na `vault.db` com os niveis que deu (Knight 527, Druid 488,
  Sorcerer 471, Monk 306, Paladin 226), Livraria FIRE, `best`, nomes provisorios =
  vocacao; arvore/equipamento/charms vazios ate haver capturas. 13 builds x 8
  niveis = 104 (tecto do teste: 60 s).
- **16/09/2026 (ordem 7, regra do Andre 13:00)** — **Beams so no boss**: «usar
  beams para hunt nao serve; beam so serve para boss». Energy Beam, Great Energy
  Beam e Great Death Beam (`builds.BEAM_SPELLS`) ficam fora da rotacao de hunt; no
  boss continuam candidatos. A pagina diz «beams: so no boss (decisao do Andre,
  16/09/2026)».
- **16/09/2026 (ordem 7)** — **Elemento a que a hunt e imune fica fora da rotacao
  de hunt**: multiplicador medio de elemento no pack (1 - resistencia media, com
  pierce) < 0,5 (`builds.HUNT_ELEMENT_MIN_MULT`) exclui o feitico (na Livraria
  FIRE, Hell's Core e Great Fire Wave). Se a regra nao deixasse nenhum, fica so a
  dos beams. O simulador ja pesava as resistencias por feitico (`hit_vs`); isto e
  a trava para a optimizacao «a qualquer mana». A pagina e o cartao dizem o que
  saiu e porque (`helper["hunt_excluded"]`).
- **16/09/2026 (ordem 7)** — **Battle Tactics entra no motor**: `formulas.battle_tactics`
  e o `u4e(level, ranks)` do cliente a letra (tier, qp, `aimChance` = chance de
  decisao perfeita, `castSearchRadius`, `repositionMinMs`, kite infinito a tier 3).
  **Convencao ⚠** (`TACTICS_IMPERFECT_FACTOR` = 0,6): uma decisao imperfeita rende
  60 % do dano de uma perfeita — factor `aim + (1-aim) x 0,6` em todo o dano que
  sai (`Profile.ai_quality`, em `hit_vs`) e o simetrico `1 + (1-aim) x 0,4` no
  dano/s que entra (`Profile.ai_taken`, em `pressure`; o maior golpe nao muda).
  `castSearchRadius` soma-se ao raio das areas para contar alvos
  (`TACTICS_RADIUS_TO_TARGETS`, convencao). A conta a mao da validacao aplica o
  mesmo factor de forma independente (os numeros de referencia de 16/09 de manha
  x 0,8). A pagina mostra «Tactica: nivel N · X % (raio Y)» com e sem o no;
  `validacao.md` §4 separa cliente de convencao.
- **16/09/2026 (ordem 7)** — Pagina da hunt: bloco «Helper e Tacticas» com o Helper
  de cada personagem dele que a tem como actual (o plano vem do advisor, nao se
  recalcula; sem cartao print porque so existem nos niveis representativos) e as
  quatro pranchas do canal (h8KqkibxfOc: encerramento, UE, waves, main; 4+ vivos =
  UE + main) com o aviso de exportar antes de importar. Hunts sem personagem
  mostram so as Tacticas e dizem porque.
- **16/09/2026 (ordem 7, decisao do Andre 13:30 — sobrepoe-se ao ponto 3 da ordem 6)**
  — **«Quero dano, nao importa o custo, importa e o dano e a XP.»** A omissao das
  builds, do Inicio e da BD (`db.GOALS_BY_VOCATION`, `builds.DEFAULT_GOAL`) passa a
  **`damage`**; a `best` (equilibrada) e as outras ficam disponiveis. Metrica de
  `damage`: DPS do ciclo (= XP/h) **sustentado** x (fraccao cumprida de «nao morrer
  no pack inteiro» e «nao morrer no boss»)^2 — sobrevivencia so como restricao
  minima, sem pesos de cura nem de tank. Mages e paladin: pocoes de mana e runas a
  vontade, **sem tecto de gold** (o tecto existe como parametro,
  `Planner(gold_cap=…)`/`choose_rotation(gold_cap=…)`, omissao `None`). Knight e
  monk: a mana continua a ser o limite (o cliente nao lhes da pocoes de mana) e
  entra no proprio DPS: `sim.simulate` devolve `dps_sustained` = ataque normal +
  runas + feiticos de mana x min(1, mana ganha/mana gasta) — substitui a
  penalizacao «DPS x (fraccao)^2» na escolha da rotacao (que, com runas a nao
  gastar mana, deixava o monk so com Sudden Death no boss); a arvore da `best`
  mantem a penalizacao quadratica da ordem 6. Os 5 personagens dele ficaram com
  `goal` NULL (= omissao; nunca escolheram). Sem migracao de esquema.
- **16/09/2026 (ordem 7, ponto 6 — teste do Andre 13:20)** — **Runas na rotacao**:
  as runas de area (`adori mas *`) e a Sudden Death sao candidatas normais da
  rotacao de hunt e de boss, com o `goldCost` do cliente por lancamento (Avalanche
  64, Thunderstorm 52, Stone Shower 41, Great Fireball 64, Sudden Death 162; mana 5
  e cd 2 s tambem do cliente). A pool da forca bruta = os 5 feiticos de mana com
  mais dano por lancamento + **a melhor runa de area + a melhor de alvo unico**
  contra o alvo (as runas de area tem todas a mesma formula e so mudam de
  elemento: entra a do elemento da hunt, nao quatro iguais); as exclusoes da hunt
  (beams, elemento imune) aplicam-se-lhes. **gold/h em regime** (`sim.simulate`):
  runas ao gold por lancamento + pocoes de vida bebidas + **pocoes de mana pelo
  deficit** (mana gasta − mana ganha, ao preco por mana da pocao; a regen base do
  servidor desconhecida conta a 0 = tecto) — nao o que os 60 s a partir da pool
  cheia beberam. A pagina da rotacao tem custo por lancamento, lancamentos/min,
  gold/h por feitico e a linha «gold/h (pocoes + runas)», mais «sem runas: …» ao
  lado (a mesma escolha so de mana). Convencoes ⚠ (`formulas`): «≥N» de uma runa de
  area = 2 (`RUNE_AREA_MIN_MOBS`); as runas apanham o `spellDmgPct` e o elemento da
  arvore (`RUNES_USE_SPELL_BONUSES`); ocupam o cooldown de grupo de ataque
  (`RUNES_SHARE_ATTACK_GCD`). A cura do Helper continua sem runa (UH e alternativa).
- **16/09/2026 (ordem 7)** — Limite conhecido: o guloso da arvore depende do
  caminho — o knight `damage` a 527 na Livraria FIRE fica ~25 % abaixo do knight
  `best` em DPS (o Avatar of Steel entra aos 477 num caminho e so aos 531 no outro).
  Nao esta corrigido; esta no relatorio-7.

- **16/09/2026 (ordem 8, ponto 1)** — **O codigo de build do cliente** (`treecode.py`):
  `V3e`/`U3e` transcritos a letra — `BT1-<KPSDM><nivel|F>-<hex>`, um digito hex por no
  da vocacao **ordenado por `id`** (ordem de string), `min(rank, max)`, zeros finais
  fora, maiusculas; `decode` devolve `None` a tudo o que nao bate na regex (digitos a
  mais ignoram-se, a menos valem 0). Os 5 codigos do supervisor
  (`tests/fixtures/codigos.json`) batem nos dois sentidos. As regras da arvore do
  cliente vivem no mesmo modulo (`MK` adjacencia nos dois sentidos, `LK`/`O3e`
  ligacao a partir do tier 0, `yD` pode-se por um ponto, `Ik`/`z3e`/`Up` custos, `F3e`
  tirar o ultimo rank, `j3e` deitar fora o desligado, `fD` custo de importar = 0 se 0
  senao 1 000 + 200 x pontos **actualmente** gastos). Cada build e cada personagem
  mostram o codigo da arvore recomendada com «Copiar» (JS vanilla, `navigator.clipboard`
  com fallback de seleccao), a frase para colar no jogo e o custo `fD` (no personagem
  com os pontos que a BD diz que tem gastos; sem arvore registada, «?»). Em `/editar`
  o campo «Cola aqui o codigo Exportar da tua arvore» faz `decode`, valida (vocacao do
  personagem, ligacao, `Up <= nivel`) e grava a arvore inteira em bloco — **e a melhor
  fonte de dados dele**: exacta e sem tocar no jogo (e ele a copiar um texto do
  cliente). O advisor passa a dizer a diferenca entre a arvore importada e a
  recomendada em pontos e em gold de respec. **Por confirmar no jogo**: se importar
  cobra mesmo `fD` e se o «Exportar» do cliente actual ainda da `BT1-`.
- **16/09/2026 (ordem 8, ponto 2 — decisao do Andre 14:30)** — **Rotacoes fixadas
  sao dados, nao sugestoes** (esquema **v5**: `characters.fixed_rotation_json`,
  `fixed_weapon`; NULL = nao fixou). Na Livraria FIRE: Sorcerer Rage of the Skies +
  Avalanche; Druid Eternal Winter + Avalanche; Knight Fierce Berserk + Groundshaker
  com o **Soulmaimer**; Monk e Paladin sem rotacao fixada (fica a do optimizador).
  Ja gravadas na `vault.db`. A arvore recomendada do personagem calcula-se **para a
  rotacao fixada** (a partilha de elementos da rotacao decide os nos de elemento) e a
  arma fixada fica no slot (o advisor nunca sugere troca-la); ao lado a pagina mostra
  a rotacao que o modelo escolheria com a diferenca de DPS e de gold/h em numero —
  nunca se substitui a escolha dele. O cartao print do Helper sai com a fixada.
- **16/09/2026 (ordem 8, ponto 3)** — **Toda a arvore que sai do `Planner` passa
  pelas regras do cliente** (`builds.tree_check`: O3e ligada, ranks <= maximo,
  `Up <= nivel`) e a **ordem de compra e clicavel a mao** (`treecode.
  purchase_order_is_clickable`: cada no, quando entra, ja tem um vizinho comprado —
  `yD`); ha um teste de propriedade sobre as builds e os 5 personagens. A pagina tem
  a linha «valida pelas regras do cliente: ligada a partir do tier 0, ranks ≤
  maximo, N de L pontos».
- **16/09/2026 (ordem 8, ponto 4)** — **Podar os nos de ligacao redundantes**
  (`builds.prune_and_refill`, constantes `PRUNE_*`): um rank cujo ganho na metrica e
  < 0,05 % e cuja remocao mantem a arvore ligada sai (rank a rank, com fila
  preguicosa; apanha tambem o que o caminho comprou para sobreviver e deixou de
  fazer falta), e os pontos libertados voltam ao guloso sem recomprar o podado, ate
  3 voltas. Salvaguardas: se o refill so encontra pontos a render ~0 ou a metrica
  fica > 0,5 % abaixo do que estava (ruido de grelha do simulador), **fica como
  estava**. Cada no leva um **papel** na ordem de compra: `dano` / `so ligacao`
  (rende ~0 mas tira-lo desligava a arvore) / `tactica` / `ponto que sobrou` (o
  refill comprou-o a render ~0; 1-2 pontos sem rank de dano que os aceite vao para
  HP/absorcao e diz-se). Wildfire/Inferno/Cataclysm (`spellDmgPct`, nome de fogo mas
  efeito generico) levam uma nota.
- **16/09/2026 (ordem 8, ponto 5)** — **Guloso dependente do caminho**: o `plan()`
  avalia, com a metrica pedida, o prefixo do proprio caminho e o do caminho da
  `best` (ou da `damage` quando se pede a `best`) e fica com o melhor
  (`PATH_CANDIDATES`; empate ate 0,5 % fica com o proprio, porque e a ordem de compra
  dele que a pagina conta); sobre o vencedor correm a melhoria local e o
  `prune_and_refill`. A rotacao final so substitui a que a arvore foi optimizada para
  se nao piorar a metrica com as condicoes (o monk «dano» 306 caia de 1 110 para 264
  com a nova a gastar a mana das curas). **Validacao cruzada com runa e Battle
  Tactics** (`validation.hand_calculation_rune`, §1b do `validacao.md`): sorcerer 471
  Rage + Avalanche na Livraria FIRE, Battle Tactics 7 — casts (6 + 24 na grelha de
  2 s), DPS, mana/s, gold/h das runas e das pocoes de mana em regime, a mao e so com
  os JSON. Custo: o build passou de ~10 s para ~2 min (104 builds a ~1,2 s) e a suite
  para ~3,5 min; o plano de um personagem numa hunt nova custa ate ~20 s a frio (o
  caminho da `best` com o «poupar para um notable») e ~1,5 s com o `Planner` quente
  (o `serve` guarda-o em memoria: so a primeira gravacao paga). A 8 esgotou os 2 700 s
  antes do merge; a **8b** fechou-a sem alargar (tectos dos testes: 256 KiB por pagina,
  30 s o build com personagem; o teste de contagens do catalogo passava a construir um
  `Catalog` sem o bruto sobre o raw partilhado e deixava as runas sem `custo_gold` para
  os testes seguintes — corrigido no teste).

- **21/09/2026 (ordem 9, decisao do Andre)** — **Niveis novos** dados por ele: Knight 548,
  Monk 336, Paladin 284, Druid 498, Sorcerer 481 (gravados em `main` pelo `db.Vault`,
  `source='manual'`, `seen_at` 2026-09-21, com uma `reading` por personagem na Livraria
  FIRE — a primeira serie para o XP/h). **Objectivo `priority`** («Prioridades do Andre:
  Avatar › Exp › Loot › Crit › Ataque › Dano critico › Elemento»), **omissao de todas as
  vocacoes** (`builds.DEFAULT_GOAL`, primeiro em `db.GOALS_BY_VOCATION`, esquema **v6**
  para o CHECK; os 5 continuam com `goal` NULL). Sobrepoe-se a omissao «dano» de 16/09
  13:30 so na omissao: `damage`/`best`/`tank`/`heal`/`support` ficam para comparacao.
  **Regras** (`builds.PRIORITY_ORDER`, `PRIORITY_STAT_CATEGORY`, `AVATAR_NODE` — para ele
  afinar): uma etapa esgota-se (todos os ranks de todos os nos dela que os pontos deixem
  comprar) antes da seguinte; um no pertence a categoria de MAIOR prioridade entre os seus
  efeitos (Berserk Mastery -> Ataque, Lord of Destruction -> Crit, Guiding Presence -> Exp,
  Rage of the Skies/Hell's Core/Divine Caldera -> Ataque, Twin Bursts -> Elemento);
  `elementDmgPct` so conta nos elementos que a rotacao de hunt e a arma usam
  (`priority_elements`: feiticos da rotacao + fisico/arma ou o elemento da wand), os outros
  ficam no «resto». Etapa 1 = Avatar (tier 11, 300) + o caminho ligado mais barato (**sobreposto
  pela 9b**: passou a ser a rota mais util, ver abaixo)
  (`avatar_reach`, Dijkstra de `unlock_path` a partir do tier 0: knight 16, paladin 19,
  sorcerer 16, druid 20, monk 19 pontos — **o Avatar cabe aos niveis 316/319/316/320/319**;
  `validacao.md` §1c refaz a conta so com o `arvore.json`); se nao cabe, salta-se AGORA, a
  pagina diz o nivel e mostra a build e o codigo desse nivel (`avatar_plan`), e o advisor
  diz «no nivel X: importar a build com o Avatar (respec fD)» — nunca se poupa. Etapas 2-3
  (Exp, Loot) pelo proprio efeito por ponto (com o caminho que faltar no custo; o simulador
  nao mede XP nem loot); 4-7 pelo guloso de DPS de `optimize_tree` **restrito** aos nos da
  categoria (`only=`), com contexto fixo ao nivel da pagina; 8 o `_refill` de sempre e a
  poda **so aqui** (`prune_and_refill(protected=)` nao toca nas etapas 1-7). Os nos do
  caminho de categoria mais baixa ficam a rank 1 «so ligacao». A build mede-se como a
  «dano» (`metric_goal`), o equipamento optimiza-se para a arvore das prioridades e a
  rotacao volta a escolher-se (a fixada fica); a pagina diz em numero o que a «dano» do
  mesmo nivel daria a mais (knight 548 +27 % de DPS, paladin 284 +22 %, monk 336 +6 % —
  e o preco das prioridades, mostrado, nunca imposto). Ao nivel dele: knight sem nos de
  Exp/Loot (diz-se), crit 170 pontos, ataque 61; paladin 284 sem Avatar (cabe a 319), exp
  58 (Hunter's Pace 10), loot 55 (Scavenger 10), crit 171; monk 336 com Avatar (319) e 17
  pontos a sobrar (crit 15, Iron Fists 1, Flow 1). Cada nivel constroi-se do zero (sem
  caminho por nivel): ~3 s por build, ~10 s com o `avatar_plan`; cache em
  `Planner._priority`. **Limite conhecido**: o guloso preguicoso dentro de uma categoria
  pode preferir um rank caro a dois baratos com mais efeito por ponto (paladin: Hawkeye 2
  em vez de Keen Aim 2 + Precision 2) — e o ganho medido, nao o stat, que decide. A arma
  que entra nos «elementos» e a fixada ou, sem ela, a que o optimizador escolhe (a wand do
  sorcerer no modelo e de morte: «death» entraria na etapa 7; o druid leva «earth» da wand)
  — ele fixa a arma em `/editar` se quiser outra. O advisor da ao proximo no da ordem e ao
  «no nivel X: importar a build com o Avatar» pontuacoes fixas (`PRIORITY_STEP_SCORE`,
  `AVATAR_STEP_SCORE`) para ficarem no topo com o que e medido.
- **21/09/2026 (ordem 9)** — **Reiniciar o `serve`**: o processo do 8774 fica de pe o dia
  todo com o codigo com que arrancou (depois de um merge, e a versao antiga; e se a BD
  subir de esquema, o `db.connect` dele rebenta com «a BD esta na versao 6 e o codigo so
  conhece ate 5»). O mtgvault mata por porto com `taskkill`; a allowlist do ai-pc nega-o,
  por isso o proprio serve tem `POST /reiniciar` (so de 127.0.0.1, com o token de
  `data/serve.token`): responde e faz `os._exit(0)`; o vigia `baiakvault-serve` relanca
  em <= 5 min (`scripts/reiniciar_serve.py` faz o pedido). **O serve que estava de pe a
  21/09 e anterior a rota** — precisa de uma paragem manual ou de um reboot.
- **21/09/2026 (ordem 9b, correccao do Andre a ordem 9)** — «Nao precisa ser o caminho mais
  barato ate Avatar, se ate la conseguires ja dar pontos as outras coisas. Os que ainda nao
  chegam, diz-me a que level vao la chegar e da-me a rota para ir ja colocando pontos la.»
  **A rota ate ao Avatar e a mais util pelas prioridades, nao a mais barata**
  (`builds.avatar_routes` / `route_vector` / `choose_avatar_route`, constantes
  `PRIORITY_ROUTE_*`): enumeram-se todas as rotas **que so sobem** (cada passo de um no para
  um que o `requer`; knight 299, paladin 304, sorcerer 513, druid 820, monk 908 — um desvio
  para baixo nunca faz falta porque um no vizinho da rota compra-se na etapa dele sem custo
  de ligacao; os caminhos simples com a adjacencia nos dois sentidos sao milhoes e
  ziguezagueiam), cada uma avalia-se pelo **vector lexicografico** (Avatar, +% exp, +% loot,
  +% crit, +% atk+magia, +% dano critico, +% elemento util, pontos que sobram para o resto)
  com **contas por stat, sem simulador** (a rota a rank 1 + Avatar + etapas 2-7 pelo efeito
  por ponto; e o que deixa avaliar centenas de rotas em < 0,2 s) e fica a melhor; empate ->
  o simulador desempata (ate 8 rotas) -> a mais barata -> a de menos nos. A build da rota
  escolhida faz-se depois com o simulador como na 9 (os totais da pagina sao os reais; o
  vector «escolhida vs mais barata» e o por stat, e diz-se). Efeito ao nivel dele: knight
  3 426 -> 4 198 DPS (rota Fury/Sharp/…/Carnage, 19 pts, em vez de Plating/…/Colossus 16),
  sorcerer 1 918 -> 2 875, druid 2 103 -> 2 230. Poda por dominancia
  (`_dominated_routes`) so acima de 2 000 rotas (nunca foi precisa). **Abaixo do nivel do
  Avatar** as rotas avaliam-se todas ao mesmo nivel (mais barata + 300 + 5) e so as que nao
  atrasam o Avatar mais de `PRIORITY_ROUTE_MAX_DELAY = 5` niveis; o nivel X = rota escolhida
  + 300 (`info["avatar_level"]`; a mais barata em `info["route"]["cheapest_level"]`;
  `avatar_reach` continua a dar a mais barata para a validacao 1c). A build «agora» **compra
  a rota** (rank 1, etapa «avatar») e as etapas 2-8 seguem com o que sobra (= plano B); a
  build do nivel X leva a **mesma rota forcada** (`plan_priority(route=)`, senao a esse nivel
  a mais barata ganhava por deixar pontos para a Exp). `avatar_plans`: **plano A** (so a rota,
  guardar o resto, 0 gold, DPS medido com a rota so e o equipamento/rotacao do B) vs
  **plano B** (gastar tudo pela ordem e importar ao nivel X, fD com X pontos gastos);
  **recomendado o B** (gold nao conta, 16/09). Paladin 284: X = 319 (a escolhida custa 19
  como a mais barata mas passa por Aim em vez de Might: +0,5 % crit), plano A 1 230 vs B
  1 349 DPS, 64 800 gold ao importar. O advisor poe «Avatar ao nivel X: plano B» na 1.a
  linha (`AVATAR_STEP_SCORE = 20 > PRIORITY_STEP_SCORE`) com a rota por ordem de clique.
  Um no da rota com categoria mostra a categoria como papel (nao «so ligacao»).
  `validacao.md` §1d conta as rotas e a mais barata a mao (programacao dinamica so com o
  `arvore.json`). Custo: build de um personagem abaixo do Avatar ~2,5 s, os outros 3-10 s.
- **21/09/2026 (ordem 9c)** — **Dentro de uma categoria, o mesmo stat decide-se pela conta por
  stat, nao pelo simulador** (`builds.PRIORITY_GREEDY_BY_STAT = True`; `_stage_by_effect(score_fn=)`).
  Causa encontrada (`ai-pc\work\baiakvault\_guloso_9c.py`): as etapas 4-7 usavam o guloso preguicoso
  de `optimize_tree(only=)`, que mede cada rank na grelha de 60 s do simulador — o MESMO +1,5 % de
  ataque (ou +1 % de crit) saia de -0,03 % a +0,15 % por ponto conforme o estado (Cold Precision 4
  media negativo; Sharpened Steel 7 media 2,5x o rank 6), e a fila preguicosa ainda guardava
  ganhos velhos; o custo `custo x n` estava certo. Regra: em Crit/Ataque/Dano critico/Elemento os
  ranks com a mesma assinatura de stats (`_stat_signature`: as chaves do `efeito_por_rank`)
  compram-se por efeito por ponto exacto (com o caminho que faltar no custo; empate -> o mais
  barato -> o id); o simulador so decide entre os melhores ranks de assinaturas diferentes
  (atkPct vs spellDmgPct; Combat Mastery atk+armor vs Fury) e mede **pacotes do mesmo tamanho**
  (o rank mais caro contra ranks do mesmo stat dos outros ate igualar o custo — +1,5 % contra 50
  pontos era ruido outra vez), empate ate `PRIORITY_STAT_SIM_TIE` = 2 % -> o mais barato. Cada
  `TreeStep` das prioridades leva `link` (entrou como caminho). Exp/Loot como estavam; a ordem das
  categorias, as rotas da 9b e o Lord of Destruction do sorcerer nao se tocaram. Knight 548: ataque
  37,5 % -> 40,0 % com 63 pontos em vez de 67 (DPS 3 635 -> 3 675). Teste de propriedade
  (`test_priority.same_stat_violations`, 5 + 8 niveis + paladin 319: chumbava antes no knight) e
  arvore a mao com custos 1 e 3.
- **21/09/2026 (ordem 10, regra nova do Andre 13:00 — sobrepoe-se a ordem de prioridades da 9)** —
  «Desculpa, vamos alterar. Quero Avatar, e depois quero que me indiques o que e melhor: se Atk,
  se Chance Critico, se Dano Critico.» **`PRIORITY_ORDER = ("avatar", "damage")`**: duas etapas
  (a ordem da 9 fica inteira em `PRIORITY_ORDER_ORDEM_9` — voltar a por Exp/Loot e uma linha; a
  estrutura por etapas, os rotulos e a categoria de cada no ficaram). Etapa 2 = **tudo o que
  rende mais DPS no simulador** com a rotacao/arma fixadas (`builds._stage_damage`): a regra da 9c
  sobre TODOS os nos — dentro da mesma assinatura de stats decide o **modelo linear** por ponto
  (`stat_model`: o valor de +1 de cada stat — atkPct, spellDmgPct, critChance, critDmg,
  attackSpeedPct, elementDmgPct util — medido no simulador como fraccao do **DPS do ciclo** (nao
  da metrica com a sobrevivencia: sobre «rota + Avatar» a fraccao de sobreviver e minuscula e +1 %
  dava +60 %), media das perturbacoes +1 e +2, `sim.Profile(extra=)`; volta a medir-se a cada
  `PRIORITY_MODEL_REFRESH = 40` pontos porque crit e dano critico multiplicam-se); entre
  assinaturas diferentes o simulador em pacotes do mesmo tamanho (com fila preguicosa por
  assinatura: o ganho medido so se repete quando o melhor rank dela muda ou o modelo se refresca —
  sem isto eram G simulacoes por rank); os nos que o modelo nao ve (HP, tacticas, notables
  especiais) valem 0 no modelo e so o simulador os mete; para quando nada rende > 0; `_refill` +
  `prune_and_refill(protected=rota+Avatar)` so aqui. Exp/Loot so entram como ligacao ou ponto que
  sobrou (teste). **A rota escolhe-se pelo DPS** (`choose_avatar_route(model=)`): o modelo medido
  uma vez por vocacao sobre «rota mais barata + Avatar» ao nivel de avaliacao ordena as centenas de
  rotas (`route_damage_score`: rota a rank 1 + Avatar + o resto pelo modelo, com `path_cache` dos
  caminhos de desbloqueio — 411 rotas do druid em ~1 s), as `PRIORITY_ROUTE_SIM_TIES = 8` melhores
  **e a mais barata** confirmam-se com a arvore inteira no simulador e ganha a de maior DPS (empate
  -> mais barata -> menos nos); `info["route"]` leva `model_best_route`, `sim_score`,
  `cheapest_sim`, `sim_check` (se o simulador concordou e a diferenca). Abaixo do Avatar o mesmo ao
  nivel «mais barata + 300 + 5» (`PRIORITY_ROUTE_MAX_DELAY` fica): **o paladin 284 passa a X = 321**
  (rota Might/Rapid Fire/…/Lightbringer, 21 pontos; +0,8 % de DPS sobre a de 19). **O bloco
  «Depois do Avatar: o que rende mais»** (`priority_stat_report` + `_finish`, puro; pagina
  `pages_builds.stat_report_block`): Ataque (atkPct no knight/monk, spellDmgPct nos mages, os dois no
  paladin) / Chance de critico / Dano critico — o que +1 % rende no simulador (fraccao e DPS), o
  melhor rank compravel agora com o ganho por ponto, o que a build comprou (% e pontos; um no conta
  no stat de maior contribuicao no modelo), o veredicto gerado da conta («rende mais X (a %/pt) ate
  aos ~N pontos, depois Y; dano critico so vale a chance: com C % de chance efectiva (Avatar «crita
  sempre» u % do tempo) cada 1 % de dano critico vale … e cada 1 % de chance vale …») e a ordem de
  compra da etapa 2 com o stat de cada passo. O advisor poe o stat ao lado do proximo rank da
  etapa 2. `validacao.md` **§1e**: a conta a mao de +1 % de chance vs +1 % de dano critico no
  sorcerer dele (`validation.crit_marginals_by_hand`: formula do critico do guia + Avatar 15 s, so
  JSON) bate no simulador a ~1e-12 (tolerancia 5 %). Ao nivel dele (Livraria FIRE, fixadas): knight
  3 675 -> 5 382 DPS (ataque 43,5 %, dano critico 25,5 %, crit 1,1 %; a «dano» do mesmo nivel da
  4 363 — o guloso por stat + modelo e melhor optimizador do que o guloso do simulador), sorcerer
  1 980 -> 2 557, druid 1 961 -> 3 196, monk 1 434 -> 1 466, paladin 1 550 -> 2 126. Custo: knight
  ~5 s, monk 8, paladin 10, sorcerer 12, druid ~30 s a frio (a maior parte e a build «dano» de
  contexto). Limite conhecido: o modelo e linear e nao ve a sobrevivencia — a confirmacao no
  simulador apanha isso nas rotas (o `sim_check` diz quando discorda), e na etapa 2 e o simulador
  que decide entre assinaturas.
- **21/09/2026 (ordem 10b, o Andre precisou a regra 13:05 — sobrepoe-se a ordem de etapas da 10)** —
  «No caso seria assim: Avatar, Exp, Loot, e tu decides o resto.» **`PRIORITY_ORDER = ("avatar",
  "exp", "loot", "damage")`**: quatro etapas — Avatar como na 9b/10; **Exp** e **Loot** pelo efeito
  por ponto exacto com o caminho no custo (as etapas 2-3 da ordem 9, `_stage_by_effect`), cada uma
  esgotada (todos os ranks que os pontos deixem) antes da seguinte; **«damage» = a etapa 2 da ordem
  10 tal e qual** sobre o que sobra (modelo linear medido sobre a arvore das etapas 1-3,
  `info["pre_damage_tree"]`; 9c dentro do mesmo stat; `prune_and_refill(protected=etapas 1-3)` so
  aqui). Invariante: um rank de Exp/Loot que nao cabia no fim da etapa nunca volta a caber (comprar
  um no do caminho tira ao orcamento o que tira ao caminho); a unica excepcao era a poda a libertar
  pontos, por isso **a poda reverte-se se um rank de Exp/Loot passar a caber** com o que ela libertou
  (`info["prune_reverted"]`; a poda rende ~0 por definicao). **A rota** (`choose_avatar_route`,
  `route_priority_score`): cada rota que so sobe avalia-se pelo vector **(Avatar, +% exp, +% loot,
  DPS do modelo linear)** — Exp/Loot pelas contas por stat sobre «rota + Avatar», o DPS pelo modelo
  sobre o que sobra; fica o grupo de maior (exp, loot), dentro dele o modelo ordena, as
  `PRIORITY_ROUTE_SIM_TIES = 8` melhores (+ a mais barata se estiver no grupo) confirmam-se no
  simulador e ganha a de maior DPS (empate -> mais barata -> menos nos). A rota de maior DPS no
  modelo sem olhar a Exp/Loot (`info["route"]["dps_best"]`, a que a ordem 10 escolhia) mede-se
  tambem no simulador e a pagina mostra «escolhida vs maior DPS» com exp, loot e DPS das duas.
  Efeito ao nivel dele (Livraria FIRE, fixadas): **druid volta a rota Fortune/Lucky Charm** (21
  pontos, +1 % loot sobre a mais barata; Exp 162 pontos = 22 %, Loot 13 = 6,4 %, dano 2; DPS
  3 196 -> 1 981 — e o preco da regra, mostrado); **paladin 284 X = 319** outra vez (ao nivel de
  avaliacao 324 a rota de 19 deixa 5 pontos para a Exp e a de 21 so 3: a regra prefere a Exp; a
  pagina mostra a de 21 como «maior DPS»; Exp 56, Loot 55, DPS 2 126 -> 1 887); sorcerer Scholar 55
  pontos (10 % exp; DPS 2 557 -> 2 560); knight e monk sem alteracao (o knight nao tem nos de Exp
  nem de Loot — diz-se; o Guiding Presence do monk nao cabe aos 336). O bloco passa a «Depois do
  Avatar, Exp e Loot: o que rende mais» (`priority_stages_before_damage()` gera a frase a partir de
  `PRIORITY_ORDER`) e conta-se sobre a arvore das etapas 1-3; o veredicto idem. `validacao.md`
  **§1f**: `validation.exp_loot_by_hand` (so `arvore.json`: +% exp/loot e pontos por no, e o rank
  de Exp/Loot mais barato que ainda cabia antes do dano — Dijkstra proprio) bate nos totais do
  motor e confirma «esgotadas» nas 5 ao nivel 500. Teste de propriedade
  (`test_priority.exp_loot_before_damage_violations`): nenhum passo da etapa «damage» com um rank de
  Exp/Loot compravel nos pontos que sobravam, nas 5 + 8 niveis + paladin 319; e a 9c dentro de
  Exp/Loot (`same_stat_violations(any_signature=True)`). O advisor diz no passo de Exp/Loot «+X %
  exp por rank (Y %/pt)». Custo: build de um personagem 2,5-7 s (a rota do druid avalia as 411
  rotas com as etapas Exp/Loot em ~1 s gracas ao `path_cache` no `_stage_by_effect`).

## Fontes

- Catalogos: bundle publico do cliente, `https://baiakidle.com/jogar/assets/index-DnzxFejS.js` (09/09/2026). Extraccao: `ai-pc\knowledge\baiakidle\` (`_extrair_catalogos.py`, `dados\construir.py`, `dados\validar.py`). Duvidas e o que fica `null`: `ai-pc\knowledge\baiakidle\dados\duvidas.md`.
- Multiplicadores da wave 10 e escaloes de XP: `guiabaiakidle.com` (nao republicar os dados deles; `robots.txt` pede `use=reference`).
- Comunidade: canal CharllonLobo (YouTube), `baiak-builds.com` (nao verificada).
- O Treinador anterior (`Desktop\BaiakIdle\coach\`) e pedreira de codigo; copia-se e adapta-se, nao se importa.
