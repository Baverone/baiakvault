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

O que ja la esta (v0.1, ordem 1):

- **Inicio** — os personagens (por agora nenhum) e os atalhos.
- **Hunts** — as 79 hunts pelos indices do proprio jogo: nivel, monstros,
  boss da wave 10 com o loot, drops que mais valem, lista do Codex. Com o
  aviso: os indices sao **eficiencia, nao XP/h** — XP/h so medindo.
- **Charms** — os 24 charms como estao no jogo: tipo, elemento, chance e
  pontos por tier, descricao.

## Adicionar um personagem

**Chega na ordem 2** (modo de edicao local, no `serve`, porto 8774). Ate la a
base esta vazia de proposito — nao se inventam personagens.

Alternativa que fica pronta na **ordem 4**: tirar **Win+Shift+S** ao painel do
personagem, a arvore, ao equipamento, aos charms ou ao bestiario e guardar em
`capturas\`. O Claude local le a imagem e escreve na base com `fonte: captura`.
Podes ja ir deixando capturas la — ficam a espera.

## Correr no PC

    py -m baiakvault build     # gera docs/
    py -m baiakvault check     # valida tudo; sai com erro se algo estiver mal
    py -m unittest discover -s tests

Python 3.14, so biblioteca padrao. Sem instalar nada.

## Quando o jogo actualizar

Os catalogos vem do ai-pc (`knowledge\baiakidle\dados\`). Refaz-se la a
extraccao e depois `py scripts\actualizar_catalogo.py` traz os ficheiros para
`data\catalogo\` e valida-os. Detalhe em `CLAUDE.md`.
