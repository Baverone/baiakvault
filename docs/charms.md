# Charms no Baiak Idle — as regras, com fonte

Lido a **16/09/2026** do bundle publico do cliente (`index-DnzxFejS.js`,
09/09/2026), em ficheiro local, sem sessao. Ninguem tinha documentado isto: o
guia (`guiabaiakidle.com`) nao tem pagina de charms e o video do canal
(`CRYJ1hS8iNA`) nao foi lido (sem `yt-dlp` no PC; nao se instalou). Cada regra
diz de onde vem. O que esta com **⚠ por confirmar** nao se conseguiu ler no
cliente: o motor (`baiakvault/charms.py`) trata-o da forma mais conservadora e
di-lo na pagina. Nada disto foi verificado dentro do jogo.

Legenda das fontes: **[codigo]** = logica do cliente (funcoes `d3e`, `l3e`,
`c3e`, `OVe`, `Zbe`, `e3e`, `Jbe`); **[texto]** = textos do cliente (i18n e
descricoes); **[loja]** = catalogo da loja de coins no cliente; **[canal]** =
CharllonLobo, opiniao.

## Os 24 charms

- **10 maiores** (`major`): Wound, Enflame, Poison, Freeze, Zap, Curse, Divine
  Wrath, Carnage, Overpower, Overflux (ofensivos); Parry, Dodge (defensivos);
  Low Blow, Savage Blow (passivos). **14 menores** (`minor`): Cripple
  (ofensivo); Adrenaline Burst, Numb (defensivos); Bless, Scavenge, Gut,
  Vampiric Embrace, Void's Call, Fatal Hold, Void Inversion (passivos).
  Chance, pontos por tier e descricao a letra: `data/catalogo/bruto/charms.json`
  e a pagina Charms do site. [texto]
- **Tier maximo 3** (`Bh=3`). A chance do tier e `chance[tier-1]`. [codigo]
- Os elementais (Wound fisico, Enflame fogo, Poison terra, Freeze gelo, Zap
  energia, Curse morte, Divine Wrath sagrado) fazem, ao acertar, dano extra do
  elemento = **min(2 x nivel, 5 % do HP maximo do alvo)**. Carnage, ao matar,
  estoira nas 4 casas coladas: **min(15 % do HP dele, 6 x nivel)**, dano puro.
  Overpower: **min(8 % do HP do alvo, 5 % do TEU HP maximo)**; Overflux:
  **min(8 % do HP do alvo, 2,5 % da TUA mana maxima)**. [texto]
- Low Blow e Savage Blow **so valem se o equipamento ja da critico**; Vampiric
  Embrace e Void's Call **so com roubo de vida/mana** e so no ataque normal e
  magias de alvo unico; Void Inversion so com escudo de mana. [texto]
- ⚠ **por confirmar**: se o dano extra do elemento respeita a resistencia do
  monstro a esse elemento. O cliente nao o diz. O motor **assume que sim**
  (como qualquer dano elemental do jogo) e por isso poe cada elemental na
  criatura com **menor resistencia** ao elemento — se afinal ignorar
  resistencias, a escolha certa passa a ser so a criatura mais gorda/mais
  batida, que e a segunda coisa que o motor ja pesa.

## Atribuir

- Cada charm ocupa **um slot proprio** com `{tier, monsterKey}`: um charm
  esta **numa so criatura de cada vez**. [codigo `jde`/`l3e`]
- Uma criatura pode ter **um charm maior e um charm menor** ao mesmo tempo,
  **nunca dois da mesma categoria** (a lista de criaturas para atribuir exclui
  as que ja tem um charm dessa categoria). [codigo `d3e`]
- **Limite de criaturas com charm**: **2** por omissao, **6 com VIP**, **25
  com a Charm Expansion** (200 coins, permanente, **por conta**; so se compra
  fora da party). Ao chegar ao limite, so se pode atribuir a uma criatura que
  **ja tem outro charm**. [texto + loja]
- **Charm maior so em criatura com o bestiario fechado** (kills >= meta da
  entrada); **charm menor basta ter matado 1**. Meta por XP da criatura: < 100
  XP -> 250 kills; < 500 -> 500; < 2000 -> 1000; senao 2500. [codigo `d3e`, `o7`]
- **Bosses diarios e nemesis nao recebem charms** (lista `MN`). Os bosses da
  wave 10 sao monstros normais da hunt com x3 HP e contam como esse monstro.
  [codigo; multiplicador do guia]
- **Comprar tier 1 e preciso antes de atribuir**. [texto]

## Pontos, echoes e custos

- **Charm Points** pagam os **maiores**; **Minor Charm Echoes** pagam os
  **menores**. Cada subida de tier de um maior devolve echoes «de troco»:
  **50** (tier 0->1), **100** (1->2), **200** (2->3) (`25t^2+25t+50`).
  [codigo `OVe`, `Jbe`]
- O tecto de Charm Points e «derivado do bestiary» — **⚠ a tabela e do
  servidor**, o cliente nao a tem. Le-se no ecra dos Charms (a BD guarda o que
  ele ler). O motor nunca inventa pontos: sem leitura fica «?».
- **Remover um charm de uma criatura custa gold**: **1 000 x nivel do
  personagem principal da conta** (x0,75 com a Charm Expansion). Depois
  atribui-se a outra — «retarget nao e gratis». [codigo `Zbe`, texto]
- **Resetar todos**: **1 000 000 + (nivel > 100 ? nivel x 110 000 : 0)** gold
  (x0,75 com a Expansion); apaga tiers e atribuicoes, devolve os Charm Points e
  zera os echoes. [codigo `e3e`, texto]
- ⚠ **por confirmar**: o «nivel do personagem principal» (`mainLevel`) e o
  nivel do main da conta, nao necessariamente o do personagem que se ve. O
  motor usa o nivel do personagem registado e diz que e aproximacao.

## Por conta ou por personagem?

- **⚠ por confirmar, mas quase de certeza por conta**: a Charm Expansion e
  «por conta»; o custo de remover usa o nivel do **main** da conta; o
  bestiario vem no mesmo bloco de estado que o `accountLevel` e os coins; o
  Codex e «bonus da conta». Ou seja, os charms atribuidos aplicam-se a
  **todos** os personagens e os slots sao **partilhados**. A `vault.db` guarda
  charms por personagem (esquema da ordem 1) — se ele confirmar que e por
  conta, os charms registam-se num so personagem e os outros ficam vazios; o
  motor de cada hunt calcula na mesma com os charms desse personagem.
- ⚠ **Em party**: o Charm Analyzer «so aparece na cacada solo», tal como o
  Proc Analyzer. Nao se sabe se os charms **procam** em party; e so o painel
  que nao aparece. O motor nao assume nada sobre isso.

## O que o canal chama «charm rune Divine Strike»

- O canal fala de uma «charm rune Divine Strike, +40 % de dano em critico,
  escolher a raca». **Nao existe nada com esse nome no bundle de 09/09/2026.**
  O que bate certo e o **Savage Blow tier 2 = +40 % de dano critico** contra a
  criatura escolhida. O motor trata-o como Savage Blow. ⚠ por confirmar. [canal
  q3eBC2GvwIg + bruto/charms.json]

## Dados de que o motor precisa e de onde vem

- **Resistencias** por elemento: `bestiario.json` (`Et` do cliente, a mesma
  tabela que o jogo usa para a dificuldade da hunt). **154 dos 240 monstros de
  hunt nao tem resistencias declaradas ai**; para esses o motor le a **segunda
  tabela de combate do cliente** (`Wy`, guardada em `bosses.json` como
  `bosses_de_sala`, que afinal tem os 386 monstros do jogo, nao so bosses) e
  marca-o com ⚠ — as duas tabelas **divergem em 33 dos 86 monstros** que tem
  ambas. Sem nenhuma das duas: «?», sem pontuacao.
- **Pesos de spawn**: so 1 das 79 hunts os publica; sem pesos, as criaturas
  contam por igual e a pagina di-lo.
- **Exposicao** de uma criatura = quanto HP dela se abate por ciclo (57 kills
  normais + o boss da wave 10 com x3 HP): e a fraccao dos golpes que lhe
  acertam e do tempo que se passa a apanhar dela. E a base de tudo.
- **Critico, roubo de vida/mana, HP e mana** do personagem: do simulador com a
  arvore e o equipamento **registados** (marcado «estimado»); sem equipamento
  registado, critico e roubo sao «?» e Low Blow / Savage Blow / Vampiric
  Embrace / Void's Call **nao se recomendam**.
