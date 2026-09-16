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
    tests/                 unittest, sem rede; fixtures: personagem.json (1), personagens.json (1 por vocacao), codigos.json (os 5 codigos de build do supervisor)
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

## Esquema da vault.db (v5)

Chaves sao as dos catalogos e validam-se ao escrever (chave desconhecida =
`VaultError`, nao insercao). `source` e 'manual' ou 'captura'; NULL onde nao
se sabe. `seen_at` = quando era verdade no jogo; `updated_at` = quando se
escreveu.

| tabela | chave | o que guarda |
|---|---|---|
| `characters` | name (unico), slug | vocation, level, current_hunt (hunts.id), vip 0/1, goal (v2/v4: best/damage/tank/heal/support, so os da vocacao), notes; v5: fixed_rotation_json (lista ordenada de nomes de feiticos da vocacao, ate 4) e fixed_weapon (itens.nome) — o que ELE fixou; NULL = nao fixou |
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

## Fontes

- Catalogos: bundle publico do cliente, `https://baiakidle.com/jogar/assets/index-DnzxFejS.js` (09/09/2026). Extraccao: `ai-pc\knowledge\baiakidle\` (`_extrair_catalogos.py`, `dados\construir.py`, `dados\validar.py`). Duvidas e o que fica `null`: `ai-pc\knowledge\baiakidle\dados\duvidas.md`.
- Multiplicadores da wave 10 e escaloes de XP: `guiabaiakidle.com` (nao republicar os dados deles; `robots.txt` pede `use=reference`).
- Comunidade: canal CharllonLobo (YouTube), `baiak-builds.com` (nao verificada).
- O Treinador anterior (`Desktop\BaiakIdle\coach\`) e pedreira de codigo; copia-se e adapta-se, nao se importa.
