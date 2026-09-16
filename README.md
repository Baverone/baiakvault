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
- **Builds** — as 8 builds (vocacao + objectivo) por nivel: arvore por ordem
  de compra, equipamento BiS, rotacao do Helper, cartao para copiar.
- **Hunts** — as 79 hunts pelos indices do proprio jogo: nivel, monstros,
  boss da wave 10 com o loot, drops que mais valem, lista do Codex. Com o
  aviso: os indices sao **eficiencia, nao XP/h** — XP/h so medindo.
- **Charms** — os 24 charms como estao no jogo: tipo, elemento, chance e
  pontos por tier, descricao.

## Adicionar ou corrigir um personagem

    py -m baiakvault serve

e abrir `http://127.0.0.1:8774/editar` no PC. Formularios simples, sem
JavaScript: personagem (vocacao, nivel, hunt, VIP, objectivo), arvore (rank
por no), equipamento (item por slot com lista filtrada, upgrade, imbuements,
atributos da forja), charms (tier e criatura, charm points) e bestiario. Cada
gravacao valida contra o catalogo (nome errado = erro, nada gravado), fica com
fonte «manual» e a data «visto a», e regenera o site. **Em branco e «nao sei»,
nunca 0.** Apagar um personagem exige escrever o nome exacto.

No telemovel (com `BAIAKVAULT_BIND=0.0.0.0` no PC): ler e livre; gravar pede o
token que a pagina `/editar` mostra quando aberta no PC (`data\serve.token`,
fora do git).

Depois de editar, publicar e `git add -A`, `git commit`, `git push` (o Pages
serve `docs/`).

Alternativa que fica pronta na **ordem 4**: tirar **Win+Shift+S** ao painel do
personagem, a arvore, ao equipamento, aos charms ou ao bestiario e guardar em
`capturas\`. O Claude local le a imagem e escreve na base com `fonte: captura`.
Podes ja ir deixando capturas la — ficam a espera.

## Como e que o «proximo passo» e calculado

A referencia e a build que o motor (`builds.py`) recomenda para a tua vocacao,
objectivo e nivel exacto, na tua hunt actual. Cada accao e medida no simulador
**com a tua arvore e o teu equipamento**: o ganho e a diferenca, em %, na
metrica do objectivo (dano: DPS do ciclo; tank: EHP x sustain x DPS^0,3; cura e
support: cura/s sustentavel x DPS^0,3). Ordem da lista: medido antes de nao
medido, por ganho; respec vale metade (custa gold); charms e bestiario a seguir;
o que falta preencher no fim. Objectivos por vocacao: knight tank|dano, druid
cura|dano, sorcerer dano, paladin dano, monk support|dano — sem objectivo
gravado usa-se o primeiro. Os numeros sao estimativas (as convencoes estao
marcadas nas paginas das builds); nada foi medido na conta.

## Correr no PC

    py -m baiakvault build     # gera docs/
    py -m baiakvault check     # valida tudo; sai com erro se algo estiver mal
    py -m unittest discover -s tests

Python 3.14, so biblioteca padrao. Sem instalar nada.

## Quando o jogo actualizar

Os catalogos vem do ai-pc (`knowledge\baiakidle\dados\`). Refaz-se la a
extraccao e depois `py scripts\actualizar_catalogo.py` traz os ficheiros para
`data\catalogo\` e valida-os. Detalhe em `CLAUDE.md`.
