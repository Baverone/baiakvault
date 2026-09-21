# BaiakVault

Os teus personagens do **Baiak Idle** num site so teu: a build de cada um, o
proximo passo, e que charm por em que criatura para cada hunt.

**Nada aqui toca no jogo nem na conta.** O BaiakVault le os catalogos publicos
do jogo e o que tu lhe das (formulario local ou capturas de ecra), e escreve
paginas. O clique e sempre teu.

## Ver o site

- Na net: <https://baverone.github.io/baiakvault/>
- Em casa, no telemovel: `py -m baiakvault serve` no PC e abrir
  `http://<ip-do-pc>:8774/` (com `BAIAKVAULT_BIND=0.0.0.0`).

O que ja la esta (v0.1):

- **Inicio** — os personagens, cada um com o 1.o proximo passo.
- **Personagem** — a build actual (arvore com pontos gastos, equipamento por
  slot, charms, bestiario) e o **proximo passo**: ate 7 accoes concretas, cada
  uma com o porque, o custo e a fonte, medidas no simulador com o que tens
  registado; ao lado, a build recomendada para a tua vocacao/objectivo/nivel.
  O que nao esta registado sai «?» e a lista diz o que falta preencher.
- **Builds** — a build das **prioridades do Andre** de cada vocacao (a omissao
  desde 21/09/2026): **Avatar › Exp › Loot › dano** (regra dele de 21/09/2026,
  13:05: «No caso seria assim: Avatar, Exp, Loot, e tu decides o resto»). O
  Avatar e o notable de tier 11 pela rota mais util pelas prioridades (todas as
  rotas do tier 0 ate la, cada uma avaliada por Avatar, +% exp, +% loot e o DPS
  de um modelo linear medido no simulador, as melhores confirmadas nele — a
  pagina mostra a escolhida, a mais barata e a de maior DPS; se ainda nao cabe,
  diz a que nivel cabe, a rota por ordem de clique para ir ja pondo pontos e os
  dois planos ate la, sem respec ou com respec ao chegar, com os numeros e o
  recomendado, e da a build e o codigo desse nivel); depois a **Exp** e o
  **Loot** esgotam-se (todos os ranks que os pontos deixem, pelo efeito por
  ponto; quem nao tem esses nos, como o knight, ve-o dito) e so entao **todos os
  pontos vao ao que rende mais DPS** medido no simulador com a rotacao/arma
  fixadas (ranks do mesmo stat pelo modelo por ponto exacto, stats diferentes
  pelo simulador em pacotes do mesmo tamanho), e o bloco **«Depois do Avatar,
  Exp e Loot: o que rende mais»**
  responde com numeros a Ataque vs Chance de critico vs Dano critico (o que
  +1 % rende, o melhor rank agora, o que a build comprou e o veredicto — o
  dano critico so vale a chance); com a ordem de compra por etapas, os totais
  por categoria e, ao lado em numero, o que a build de **dano** daria a mais; a
  build de dano de cada vocacao (o maior DPS do ciclo = XP/h, sem tecto de
  gold — pocoes e runas a vontade nos mages e no paladin, a mana como limite no
  knight e no monk, sobreviver so como restricao minima), a **melhor**
  (equilibrada) e as builds por objectivo, por nivel:
  arvore por ordem de compra, equipamento BiS, rotacao do Helper com o custo
  por lancamento e o **gold/h (pocoes + runas)**, cartao para copiar. E a
  **validacao cruzada** (`builds/validacao.html`): as contas de um perfil fixo
  refeitas a mao so com os JSON do jogo, ao lado do simulador (o teste chumba
  se divergirem mais de 1 %), a curva de DPS do guia ao lado de cada build, e
  onde o guia e o cliente do jogo discordam.
- **Hunts** — as 79 hunts pelos indices do proprio jogo: nivel, monstros,
  boss da wave 10 com o loot, drops que mais valem, lista do Codex. Com o
  aviso: os indices sao **eficiencia, nao XP/h** — XP/h so medindo.
- **Charms** — os 24 charms como estao no jogo (tipo, elemento, chance e
  pontos por tier), **os teus charms** por personagem (tier, pontos, echoes,
  limite, o proximo a subir) e as **regras do jogo com fonte**
  (`charms/regras.html`): um charm por criatura, um maior e um menor por
  criatura, limite de 2 / 6 (VIP) / 25 (Charm Expansion) criaturas, maior so
  com bestiario fechado, mover custa 1 000 gold x nivel. O que nao se
  conseguiu confirmar esta marcado ⚠.
- **Charms para esta hunt** — em cada hunt, por personagem: que charm por em
  que criatura, o porque numa linha e **o que mudar** face ao que tens (com o
  custo); mais o tecto com os 24 charms. Na pagina do personagem, a hunt actual
  em destaque e as 5 hunts vizinhas em nivel; cada uma com um **cartao**
  (`print/charms-<personagem>-<hunt>.html`, 390 px, nomes do jogo) para tirar
  screenshot e copiar para o jogo. Nas builds, os charms ideais por nivel.
- **Codex** (`codex/index.html`) — o plano de ordenacao das missoes pelo
  **ganho de DPS da party por hora**, com a XP perdida ao lado: (a) o Auto
  Collect de agora com o que falta (kills e horas, com os contadores do ecra),
  (b) a rotacao das quatro Livrarias, (c) as hunts 600-610 «quando subirem»,
  (d) os bosses pelos elementos das rotacoes, (e) os sets ao tier Comum, (f) os
  degraus II e III com o gold e as horas (x5, x15). As recompensas
  **calculam-se no cliente** (deterministicas; `codex.py` transcreve-as, e a
  validacao cruzada da tres numeros para comparar no ecra) e os bonus sao por
  conta (por confirmar). `codex/missoes.html` tem as 686 missoes com filtro por
  categoria e stat; `print/codex-plano.html` e o cartao.

## Adicionar ou corrigir um personagem

    py -m baiakvault serve

e abrir `http://127.0.0.1:8774/editar` no PC. Formularios simples, sem
JavaScript: personagem (vocacao, nivel, hunt, VIP, objectivo), arvore (rank
por no), equipamento (item por slot com lista filtrada, upgrade, imbuements,
atributos da forja), charms (tier e criatura, charm points, echoes, o limite
«X/Y monstros com charm» do ecra e se tens a Charm Expansion), bestiario e, por
conta, o progresso do Codex (o numero da missao no ecra e as contagens coladas
«599/3.500» na ordem da lista). Cada
gravacao valida contra o catalogo (nome errado = erro, nada gravado), fica com
fonte «manual» e a data «visto a», e regenera o site. **Em branco e «nao sei»,
nunca 0.** Apagar um personagem exige escrever o nome exacto.

No telemovel (com `BAIAKVAULT_BIND=0.0.0.0` no PC): ler e livre; gravar pede o
token que a pagina `/editar` mostra quando aberta no PC (`data\serve.token`,
fora do git).

Depois de editar, publicar e `git add -A`, `git commit`, `git push` (o Pages
serve `docs/`).

**A melhor forma de dar a arvore (ordem 8, 16/09/2026)**: no jogo, na arvore
do personagem, carrega em **«Exportar»** (copia um codigo `BT1-…` para o
clipboard) e cola-o em `/editar` no campo «Cola aqui o codigo Exportar da tua
arvore». E exacto, nao precisa de capturas e nao toca no jogo — e so texto que
tu copias do cliente. O BaiakVault valida como o cliente (vocacao, ligacao ao
tier 0, pontos ≤ nivel) e grava a arvore inteira. No sentido contrario, cada
build e cada personagem mostram o codigo da arvore recomendada com um botao
«Copiar»: no jogo e «Colar codigo para importar… → Carregar» (substitui a tua
e custa `1000 + 200 x pontos gastos agora` de gold, o mesmo do Reset All —
por confirmar no jogo). Em `/editar` tambem podes **fixar a rotacao de hunt e
a arma** de um personagem: sao dados teus, a arvore recomendada e calculada
para elas, e a pagina mostra ao lado o que o modelo escolheria com a diferenca
em numero.

Alternativa (ordem 4, 16/09/2026): tirar **Win+Shift+S** ao painel do
personagem, a arvore, ao equipamento, ou ao bestiario/charms, e guardar a
imagem em `capturas\` (aqui no baiakvault) ou em
`Desktop\BaiakIdle\capturas\` — a pasta que ja conheces do Treinador. De 30
em 30 minutos, a tarefa `baiakvault-leitura` do ai-pc olha para as duas
pastas: sem imagens novas nao gasta nada; com imagens, o Claude local (visao)
le cada uma, valida contra o catalogo e escreve na base com `fonte:
captura`, arrumando a imagem em `capturas\lidas\<AAAA-MM>\` a seguir (as que
nao conseguir ler ficam em `capturas\duvidas\`, com o motivo num `.txt` ao
lado). Se o nome do personagem na captura ainda nao existir na base, cria-se.
Podes ir deixando capturas la a qualquer altura — ficam a espera da proxima
corrida.

## Como e que o «proximo passo» e calculado

A referencia e a build que o motor (`builds.py`) recomenda para a tua vocacao,
objectivo e nivel exacto, na tua hunt actual. Cada accao e medida no simulador
**com a tua arvore e o teu equipamento**: o ganho e a diferenca, em %, na
metrica do objectivo (dano: DPS do ciclo; tank: EHP x sustain x DPS^0,3; cura e
support: cura/s sustentavel x DPS^0,3). Ordem da lista: medido antes de nao
medido, por ganho; respec vale metade (custa gold); charms e bestiario a seguir;
o que falta preencher no fim. Objectivos por vocacao: **prioridades** (a
omissao em todas, 21/09/2026), dano, melhor, e knight tank | druid cura | monk
support — sem objectivo gravado usa-se o primeiro. Com «prioridades» o proximo
no da arvore e o proximo da ordem de compra por etapas (nao o de maior ganho
medido; o ganho vai ao lado como informacao) e, se o Avatar ainda nao cabe, a
lista diz a que nivel cabe e que o passo la e importar a build desse nivel
(respec). Os numeros sao estimativas (as convencoes estao marcadas nas paginas
das builds); nada foi medido na conta.

## Como e que os charms por hunt sao escolhidos

Cada criatura da hunt tem uma **exposicao**: quanto HP dela se abate num ciclo
(57 kills mais o boss da wave 10 com x3 HP) — e a fraccao dos golpes que lhe
acertam e do tempo que se passa a apanhar dela. Os elementais (Wound, Enflame,
Poison, Freeze, Zap, Curse, Divine Wrath) vao para a criatura gorda, fraca ao
elemento e muito batida: exposicao x min(2 x nivel, 5 % do HP) x (1 -
resistencia). Carnage para a de mais kills em pack denso; Overpower/Overflux
pelo teu HP/mana (estimados); Dodge, Parry, Numb, Adrenaline Burst, Cripple e
Void Inversion para a criatura de que mais dano apanhas; Low Blow, Savage
Blow, Fatal Hold, Vampiric Embrace e Void's Call para a mais batida — **e so
se o teu equipamento registado der critico / roubo / escudo**; Gut para o
melhor loot, Scavenge para as moedas, Bless para a criatura que aparece em
mais hunts. Depois cumprem-se as regras do jogo (um charm por criatura, um
maior e um menor por criatura, o limite de criaturas, bestiario fechado para
os maiores) e lista-se o que mudar e quanto custa. Nunca se atribui um charm
que nao tens; onde falta um dado (resistencia, HP) a criatura nao pontua e
sai «?». Regras e fontes: `docs/charms.md`.

## Correr no PC

    py -m baiakvault build     # gera docs/
    py -m baiakvault check     # valida tudo; sai com erro se algo estiver mal
    py -m unittest discover -s tests

Python 3.14, so biblioteca padrao. Sem instalar nada.

## Quando o jogo actualizar

Os catalogos vem do ai-pc (`knowledge\baiakidle\dados\`). Refaz-se la a
extraccao e depois `py scripts\actualizar_catalogo.py` traz os ficheiros para
`data\catalogo\` e valida-os. Detalhe em `CLAUDE.md`.
