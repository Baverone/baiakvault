# Validacao cruzada das builds

Gerada pelo build a partir de `baiakvault/validation.py` (16/09/2026). Tres verificacoes: as contas de um perfil fixo refeitas a mao so com os JSON do catalogo, sem o simulador; a curva de DPS que o guia publica ao lado do DPS do ciclo do simulador; e as constantes em que o guia e o cliente do jogo discordam.

## 1. Contas a mao vs simulador

Perfil: **sorcerer nivel 50 em Crawler**, arvore de 16 nos (Arcane Power 4, Wildfire 4, Pyromancy 2, Ignite 2, Inferno 2, Archmage 1, Arcane Focus 1, Death Chill 1, Bottomless Well 1, Essence Drain 1, Voltaics 1, Reaper 1, Scholar 1, Scorch 1, Stormcall 1, Energy Ward 1), equipamento void wand, cobra crown, void robe, void legs, void galoshes, amulet of earth, ring of earth, imbuements weapon: strike T3, vampirism T3; armor: vampirism T3, rotacao Great Fire Wave + Great Energy Beam, cura Ultimate Healing. A conta a mao usa so `vocacoes.json` (formulas dos feiticos), `arvore.json` (custos e efeitos), `itens.json`, `bestiario.json` e `hunts.json`, com estas constantes: hp_base = 100 (guia: 100 + hpPerLevel x nivel); mana_base = 90 (guia: 90 + manaPerLevel x nivel); hp_per_level = 5 (cliente j0.sorcerer); mana_per_level = 30 (cliente j0.sorcerer); skill_base = 15 (guia: magic level = 15 + 0,1 x nivel); skill_per_level = 0.1 (guia); gcd_s = 2 (cliente QO=2e3); auto_interval_s = 2 (convencao ⚠ (o mesmo intervalo dos monstros)); crit_base = 50 (guia: critico = 1 + chance x (50 + critDmg)/10000); imbuement_crit_chance = 5 (cliente FY=5); area_targets_radius_2 = 5 (convencao ⚠, limitado ao pack); cycle_kills = 57 (guia L=57); boss_hp_mult = 3 (guia te=3).

Tolerancia: 1,0 %.

| numero | a mao | simulador | diferenca | |
|---|---|---|---|---|
| cura por lancamento (exura vita) | 445,8 | 445,8 | +0,00 % | ok |
| custo da arvore (pontos) | 50 | 50 | +0,00 % | ok |
| HP maximo | 350,0 | 350,0 | +0,00 % | ok |
| mana maxima | 1.621,8 | 1.621,8 | +0,00 % | ok |
| magic level (guia + itens) | 30,0 | 30,0 | +0,00 % | ok |
| DPS contra o pack | 487,5 | 487,5 | -0,00 % | ok |
| DPS contra o boss (x3 HP) | 168,4 | 168,4 | -0,00 % | ok |
| DPS do ciclo | 427,4 | 427,4 | -0,00 % | ok |
| dano/s do ataque automatico | 31,1 | 31,1 | +0,00 % | ok |
| mana/s gasta pela rotacao | 57,5 | 57,5 | +0,00 % | ok |

**Tudo dentro da tolerancia.**

## 2. A curva de DPS do guia vs o DPS do ciclo do simulador

Curva do guia: `7,012 x nivel^0,948` (guiabaiakidle.com/_astro/character-planner.D0n3Vxn3.js — `F=7.012,I=.948` (lido a 2026-09-16)). E uma referencia sem vocacao, hunt nem equipamento; a razao mostra quanto cada build se afasta dela — nao ha «certo» aqui, ha o que cada um diz.

| build | nivel | hunt | DPS ciclo (simulador) | curva do guia | razao |
|---|---|---|---|---|---|
| Knight (EK) — Sobreviver | 50 | Crawler | 892 | 286 | x3,12 |
| Knight (EK) — Sobreviver | 100 | Orclops | 1.389 | 552 | x2,52 |
| Knight (EK) — Sobreviver | 200 | Undead Dragon | 1.914 | 1.065 | x1,80 |
| Knight (EK) — Sobreviver | 300 | Naga Lair | 2.336 | 1.564 | x1,49 |
| Knight (EK) — Sobreviver | 500 | Livraria EARTH | 2.950 | 2.538 | x1,16 |
| Knight (EK) — Sobreviver | 800 | Bony Sea Devil | 6.277 | 3.963 | x1,58 |
| Knight (EK) — Sobreviver | 1200 | Bony Sea Devil | 10.920 | 5.820 | x1,88 |
| Knight (EK) — Sobreviver | 1500 | Rotten man-maggot | 14.684 | 7.191 | x2,04 |
| Knight (EK) — Dar dano | 50 | Crawler | 1.016 | 286 | x3,55 |
| Knight (EK) — Dar dano | 100 | Orclops | 1.674 | 552 | x3,03 |
| Knight (EK) — Dar dano | 200 | Undead Dragon | 2.444 | 1.065 | x2,30 |
| Knight (EK) — Dar dano | 300 | Naga Lair | 3.210 | 1.564 | x2,05 |
| Knight (EK) — Dar dano | 500 | Livraria EARTH | 5.071 | 2.538 | x2,00 |
| Knight (EK) — Dar dano | 800 | Bony Sea Devil | 9.326 | 3.963 | x2,35 |
| Knight (EK) — Dar dano | 1200 | Bony Sea Devil | 18.134 | 5.820 | x3,12 |
| Knight (EK) — Dar dano | 1500 | Rotten man-maggot | 23.618 | 7.191 | x3,28 |
| Druid (ED) — Curar bastante | 50 | Crawler | 342 | 286 | x1,20 |
| Druid (ED) — Curar bastante | 100 | Orclops | 680 | 552 | x1,23 |
| Druid (ED) — Curar bastante | 200 | Undead Dragon | 748 | 1.065 | x0,70 |
| Druid (ED) — Curar bastante | 300 | Naga Lair | 1.728 | 1.564 | x1,11 |
| Druid (ED) — Curar bastante | 500 | Livraria EARTH | 2.150 | 2.538 | x0,85 |
| Druid (ED) — Curar bastante | 800 | Bony Sea Devil | 3.964 | 3.963 | x1,00 |
| Druid (ED) — Curar bastante | 1200 | Bony Sea Devil | 8.253 | 5.820 | x1,42 |
| Druid (ED) — Curar bastante | 1500 | Rotten man-maggot | 13.367 | 7.191 | x1,86 |
| Druid (ED) — Dar dano | 50 | Crawler | 411 | 286 | x1,44 |
| Druid (ED) — Dar dano | 100 | Orclops | 892 | 552 | x1,62 |
| Druid (ED) — Dar dano | 200 | Undead Dragon | 1.047 | 1.065 | x0,98 |
| Druid (ED) — Dar dano | 300 | Naga Lair | 2.223 | 1.564 | x1,42 |
| Druid (ED) — Dar dano | 500 | Livraria EARTH | 3.383 | 2.538 | x1,33 |
| Druid (ED) — Dar dano | 800 | Bony Sea Devil | 5.849 | 3.963 | x1,48 |
| Druid (ED) — Dar dano | 1200 | Bony Sea Devil | 10.813 | 5.820 | x1,86 |
| Druid (ED) — Dar dano | 1500 | Rotten man-maggot | 16.028 | 7.191 | x2,23 |
| Sorcerer (MS) — Dar dano | 50 | Crawler | 427 | 286 | x1,49 |
| Sorcerer (MS) — Dar dano | 100 | Orclops | 1.009 | 552 | x1,83 |
| Sorcerer (MS) — Dar dano | 200 | Undead Dragon | 1.909 | 1.065 | x1,79 |
| Sorcerer (MS) — Dar dano | 300 | Naga Lair | 3.033 | 1.564 | x1,94 |
| Sorcerer (MS) — Dar dano | 500 | Livraria EARTH | 5.019 | 2.538 | x1,98 |
| Sorcerer (MS) — Dar dano | 800 | Bony Sea Devil | 10.916 | 3.963 | x2,75 |
| Sorcerer (MS) — Dar dano | 1200 | Bony Sea Devil | 21.629 | 5.820 | x3,72 |
| Sorcerer (MS) — Dar dano | 1500 | Rotten man-maggot | 25.717 | 7.191 | x3,58 |
| Paladin (RP) — Dar dano | 50 | Crawler | 829 | 286 | x2,90 |
| Paladin (RP) — Dar dano | 100 | Orclops | 1.209 | 552 | x2,19 |
| Paladin (RP) — Dar dano | 200 | Undead Dragon | 2.301 | 1.065 | x2,16 |
| Paladin (RP) — Dar dano | 300 | Naga Lair | 3.105 | 1.564 | x1,99 |
| Paladin (RP) — Dar dano | 500 | Livraria EARTH | 4.779 | 2.538 | x1,88 |
| Paladin (RP) — Dar dano | 800 | Bony Sea Devil | 9.565 | 3.963 | x2,41 |
| Paladin (RP) — Dar dano | 1200 | Bony Sea Devil | 15.673 | 5.820 | x2,69 |
| Paladin (RP) — Dar dano | 1500 | Rotten man-maggot | 23.304 | 7.191 | x3,24 |
| Monk — Curar (support) | 50 | Crawler | 377 | 286 | x1,32 |
| Monk — Curar (support) | 100 | Orclops | 840 | 552 | x1,52 |
| Monk — Curar (support) | 200 | Undead Dragon | 1.350 | 1.065 | x1,27 |
| Monk — Curar (support) | 300 | Naga Lair | 1.698 | 1.564 | x1,09 |
| Monk — Curar (support) | 500 | Livraria EARTH | 2.347 | 2.538 | x0,92 |
| Monk — Curar (support) | 800 | Bony Sea Devil | 5.496 | 3.963 | x1,39 |
| Monk — Curar (support) | 1200 | Bony Sea Devil | 10.874 | 5.820 | x1,87 |
| Monk — Curar (support) | 1500 | Rotten man-maggot | 13.186 | 7.191 | x1,83 |
| Monk — Dar dano | 50 | Crawler | 400 | 286 | x1,40 |
| Monk — Dar dano | 100 | Orclops | 645 | 552 | x1,17 |
| Monk — Dar dano | 200 | Undead Dragon | 1.368 | 1.065 | x1,28 |
| Monk — Dar dano | 300 | Naga Lair | 1.896 | 1.564 | x1,21 |
| Monk — Dar dano | 500 | Livraria EARTH | 3.085 | 2.538 | x1,22 |
| Monk — Dar dano | 800 | Bony Sea Devil | 5.561 | 3.963 | x1,40 |
| Monk — Dar dano | 1200 | Bony Sea Devil | 11.215 | 5.820 | x1,93 |
| Monk — Dar dano | 1500 | Rotten man-maggot | 13.234 | 7.191 | x1,84 |

## 3. Onde o guia e o cliente discordam

| o que | guia | cliente | o que se segue |
|---|---|---|---|
| HP por nivel do monk | 12 | 13 (`j0.monk.hpPerLevel`) | cliente |
| mana por nivel do monk | 10 | 8 (`j0.monk.manaPerLevel`) | cliente |
| base de HP / mana ao nivel 0 | 100 / 90 | nao esta no cliente | guia (unica fonte) |
| regeneracao base de HP/mana | nao publica | nao esta no cliente (e do servidor) | nenhum: fica desconhecida e nao entra |
| golpe do ataque automatico | curva 7,012 x nivel^0,948 sem factores | so a formula dos feiticos | convencao ⚠ (formula do Tibia) |

Fontes: guia = `guiabaiakidle.com` (planner, lido a 16/09/2026); cliente = bundle publico `index-DnzxFejS.js` (09/09/2026). Nada disto foi medido na conta.
