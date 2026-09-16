# Validacao cruzada das builds

Gerada pelo build a partir de `baiakvault/validation.py` (16/09/2026). Tres verificacoes: as contas de um perfil fixo refeitas a mao so com os JSON do catalogo, sem o simulador; a curva de DPS que o guia publica ao lado do DPS do ciclo do simulador; e as constantes em que o guia e o cliente do jogo discordam.

## 1. Contas a mao vs simulador

Perfil: **sorcerer nivel 50 em Crawler**, arvore de 16 nos (Arcane Power 4, Wildfire 4, Pyromancy 2, Ignite 2, Inferno 2, Archmage 1, Arcane Focus 1, Death Chill 1, Bottomless Well 1, Essence Drain 1, Voltaics 1, Reaper 1, Scholar 1, Scorch 1, Stormcall 1, Energy Ward 1), equipamento void wand, cobra crown, void robe, void legs, void galoshes, amulet of earth, ring of earth, imbuements weapon: strike T3, vampirism T3; armor: vampirism T3, rotacao Great Fire Wave + Great Energy Beam, cura Ultimate Healing. A conta a mao usa so `vocacoes.json` (formulas dos feiticos), `arvore.json` (custos e efeitos), `itens.json`, `bestiario.json` e `hunts.json`, com estas constantes: hp_base = 100 (guia: 100 + hpPerLevel x nivel); mana_base = 90 (guia: 90 + manaPerLevel x nivel); hp_per_level = 5 (cliente j0.sorcerer); mana_per_level = 30 (cliente j0.sorcerer); skill_base = 15 (guia: magic level = 15 + 0,1 x nivel); skill_per_level = 0.1 (guia); gcd_s = 2 (cliente QO=2e3); auto_interval_s = 2 (convencao ⚠ (o mesmo intervalo dos monstros)); crit_base = 50 (guia: critico = 1 + chance x (50 + critDmg)/10000); imbuement_crit_chance = 5 (cliente FY=5); area_targets_radius_2 = 5 (convencao ⚠, limitado ao pack); cycle_kills = 57 (guia L=57); boss_hp_mult = 3 (guia te=3); tactics_aim_base = 0.5 (cliente u4e: aimChance = min(1, 0,5 + 0,025 x qp)); tactics_aim_per_qp = 0.025 (cliente u4e); tactics_imperfect = 0.6 (convencao ⚠: uma decisao imperfeita rende 60 % de uma perfeita).

Tolerancia: 1,0 %.

| numero | a mao | simulador | diferenca | |
|---|---|---|---|---|
| cura por lancamento (exura vita) | 445,8 | 445,8 | +0,00 % | ok |
| custo da arvore (pontos) | 50 | 50 | +0,00 % | ok |
| factor da IA de combate (Battle Tactics) | 0,8 | 0,8 | +0,00 % | ok |
| HP maximo | 350,0 | 350,0 | +0,00 % | ok |
| mana maxima | 1.621,8 | 1.621,8 | +0,00 % | ok |
| magic level (guia + itens) | 30,0 | 30,0 | +0,00 % | ok |
| DPS contra o pack | 390,0 | 390,0 | +0,00 % | ok |
| DPS contra o boss (x3 HP) | 134,7 | 134,7 | +0,00 % | ok |
| DPS do ciclo | 341,9 | 341,9 | +0,00 % | ok |
| dano/s do ataque automatico | 24,9 | 24,9 | +0,00 % | ok |
| mana/s gasta pela rotacao | 57,5 | 57,5 | +0,00 % | ok |

**Tudo dentro da tolerancia.**

## 2. A curva de DPS do guia vs o DPS do ciclo do simulador

Curva do guia: `7,012 x nivel^0,948` (guiabaiakidle.com/_astro/character-planner.D0n3Vxn3.js — `F=7.012,I=.948` (lido a 2026-09-16)). E uma referencia sem vocacao, hunt nem equipamento; a razao mostra quanto cada build se afasta dela — nao ha «certo» aqui, ha o que cada um diz.

| build | nivel | hunt | DPS ciclo (simulador) | curva do guia | razao |
|---|---|---|---|---|---|
| Knight (EK) — Dar dano | 50 | Crawler | 364 | 286 | x1,27 |
| Knight (EK) — Dar dano | 100 | Orclops | 489 | 552 | x0,89 |
| Knight (EK) — Dar dano | 200 | Undead Dragon | 1.194 | 1.065 | x1,12 |
| Knight (EK) — Dar dano | 300 | Naga Lair | 2.324 | 1.564 | x1,49 |
| Knight (EK) — Dar dano | 500 | Livraria EARTH | 3.778 | 2.538 | x1,49 |
| Knight (EK) — Dar dano | 800 | Bony Sea Devil | 8.657 | 3.963 | x2,18 |
| Knight (EK) — Dar dano | 1200 | Bony Sea Devil | 17.228 | 5.820 | x2,96 |
| Knight (EK) — Dar dano | 1500 | Rotten man-maggot | 24.301 | 7.191 | x3,38 |
| Druid (ED) — Dar dano | 50 | Crawler | 347 | 286 | x1,21 |
| Druid (ED) — Dar dano | 100 | Orclops | 727 | 552 | x1,32 |
| Druid (ED) — Dar dano | 200 | Undead Dragon | 1.012 | 1.065 | x0,95 |
| Druid (ED) — Dar dano | 300 | Naga Lair | 2.225 | 1.564 | x1,42 |
| Druid (ED) — Dar dano | 500 | Livraria EARTH | 2.704 | 2.538 | x1,07 |
| Druid (ED) — Dar dano | 800 | Bony Sea Devil | 5.960 | 3.963 | x1,50 |
| Druid (ED) — Dar dano | 1200 | Bony Sea Devil | 11.298 | 5.820 | x1,94 |
| Druid (ED) — Dar dano | 1500 | Rotten man-maggot | 17.583 | 7.191 | x2,45 |
| Sorcerer (MS) — Dar dano | 50 | Crawler | 352 | 286 | x1,23 |
| Sorcerer (MS) — Dar dano | 100 | Orclops | 785 | 552 | x1,42 |
| Sorcerer (MS) — Dar dano | 200 | Undead Dragon | 1.522 | 1.065 | x1,43 |
| Sorcerer (MS) — Dar dano | 300 | Naga Lair | 2.439 | 1.564 | x1,56 |
| Sorcerer (MS) — Dar dano | 500 | Livraria EARTH | 4.102 | 2.538 | x1,62 |
| Sorcerer (MS) — Dar dano | 800 | Bony Sea Devil | 9.179 | 3.963 | x2,32 |
| Sorcerer (MS) — Dar dano | 1200 | Bony Sea Devil | 18.301 | 5.820 | x3,14 |
| Sorcerer (MS) — Dar dano | 1500 | Rotten man-maggot | 21.731 | 7.191 | x3,02 |
| Paladin (RP) — Dar dano | 50 | Crawler | 689 | 286 | x2,41 |
| Paladin (RP) — Dar dano | 100 | Orclops | 986 | 552 | x1,79 |
| Paladin (RP) — Dar dano | 200 | Undead Dragon | 1.741 | 1.065 | x1,64 |
| Paladin (RP) — Dar dano | 300 | Naga Lair | 2.310 | 1.564 | x1,48 |
| Paladin (RP) — Dar dano | 500 | Livraria EARTH | 3.282 | 2.538 | x1,29 |
| Paladin (RP) — Dar dano | 800 | Bony Sea Devil | 5.666 | 3.963 | x1,43 |
| Paladin (RP) — Dar dano | 1200 | Bony Sea Devil | 10.470 | 5.820 | x1,80 |
| Paladin (RP) — Dar dano | 1500 | Rotten man-maggot | 17.582 | 7.191 | x2,45 |
| Monk — Dar dano | 50 | Crawler | 230 | 286 | x0,80 |
| Monk — Dar dano | 100 | Orclops | 510 | 552 | x0,92 |
| Monk — Dar dano | 200 | Undead Dragon | 708 | 1.065 | x0,66 |
| Monk — Dar dano | 300 | Naga Lair | 1.275 | 1.564 | x0,82 |
| Monk — Dar dano | 500 | Livraria EARTH | 1.887 | 2.538 | x0,74 |
| Monk — Dar dano | 800 | Bony Sea Devil | 4.282 | 3.963 | x1,08 |
| Monk — Dar dano | 1200 | Bony Sea Devil | 10.893 | 5.820 | x1,87 |
| Monk — Dar dano | 1500 | Rotten man-maggot | 15.114 | 7.191 | x2,10 |
| Knight (EK) — A melhor possivel | 50 | Crawler | 427 | 286 | x1,49 |
| Knight (EK) — A melhor possivel | 100 | Orclops | 422 | 552 | x0,76 |
| Knight (EK) — A melhor possivel | 200 | Undead Dragon | 1.024 | 1.065 | x0,96 |
| Knight (EK) — A melhor possivel | 300 | Naga Lair | 1.990 | 1.564 | x1,27 |
| Knight (EK) — A melhor possivel | 500 | Livraria EARTH | 4.786 | 2.538 | x1,89 |
| Knight (EK) — A melhor possivel | 800 | Bony Sea Devil | 8.570 | 3.963 | x2,16 |
| Knight (EK) — A melhor possivel | 1200 | Bony Sea Devil | 17.228 | 5.820 | x2,96 |
| Knight (EK) — A melhor possivel | 1500 | Rotten man-maggot | 24.301 | 7.191 | x3,38 |
| Druid (ED) — A melhor possivel | 50 | Crawler | 313 | 286 | x1,09 |
| Druid (ED) — A melhor possivel | 100 | Orclops | 714 | 552 | x1,29 |
| Druid (ED) — A melhor possivel | 200 | Undead Dragon | 1.012 | 1.065 | x0,95 |
| Druid (ED) — A melhor possivel | 300 | Naga Lair | 2.225 | 1.564 | x1,42 |
| Druid (ED) — A melhor possivel | 500 | Livraria EARTH | 2.704 | 2.538 | x1,07 |
| Druid (ED) — A melhor possivel | 800 | Bony Sea Devil | 5.960 | 3.963 | x1,50 |
| Druid (ED) — A melhor possivel | 1200 | Bony Sea Devil | 11.298 | 5.820 | x1,94 |
| Druid (ED) — A melhor possivel | 1500 | Rotten man-maggot | 17.583 | 7.191 | x2,45 |
| Sorcerer (MS) — A melhor possivel | 50 | Crawler | 352 | 286 | x1,23 |
| Sorcerer (MS) — A melhor possivel | 100 | Orclops | 785 | 552 | x1,42 |
| Sorcerer (MS) — A melhor possivel | 200 | Undead Dragon | 1.522 | 1.065 | x1,43 |
| Sorcerer (MS) — A melhor possivel | 300 | Naga Lair | 2.439 | 1.564 | x1,56 |
| Sorcerer (MS) — A melhor possivel | 500 | Livraria EARTH | 4.102 | 2.538 | x1,62 |
| Sorcerer (MS) — A melhor possivel | 800 | Bony Sea Devil | 9.179 | 3.963 | x2,32 |
| Sorcerer (MS) — A melhor possivel | 1200 | Bony Sea Devil | 18.301 | 5.820 | x3,14 |
| Sorcerer (MS) — A melhor possivel | 1500 | Rotten man-maggot | 21.731 | 7.191 | x3,02 |
| Paladin (RP) — A melhor possivel | 50 | Crawler | 689 | 286 | x2,41 |
| Paladin (RP) — A melhor possivel | 100 | Orclops | 986 | 552 | x1,79 |
| Paladin (RP) — A melhor possivel | 200 | Undead Dragon | 1.741 | 1.065 | x1,64 |
| Paladin (RP) — A melhor possivel | 300 | Naga Lair | 2.310 | 1.564 | x1,48 |
| Paladin (RP) — A melhor possivel | 500 | Livraria EARTH | 3.282 | 2.538 | x1,29 |
| Paladin (RP) — A melhor possivel | 800 | Bony Sea Devil | 5.666 | 3.963 | x1,43 |
| Paladin (RP) — A melhor possivel | 1200 | Bony Sea Devil | 10.470 | 5.820 | x1,80 |
| Paladin (RP) — A melhor possivel | 1500 | Rotten man-maggot | 17.582 | 7.191 | x2,45 |
| Monk — A melhor possivel | 50 | Crawler | 217 | 286 | x0,76 |
| Monk — A melhor possivel | 100 | Orclops | 381 | 552 | x0,69 |
| Monk — A melhor possivel | 200 | Undead Dragon | 699 | 1.065 | x0,66 |
| Monk — A melhor possivel | 300 | Naga Lair | 1.075 | 1.564 | x0,69 |
| Monk — A melhor possivel | 500 | Livraria EARTH | 1.462 | 2.538 | x0,58 |
| Monk — A melhor possivel | 800 | Bony Sea Devil | 4.092 | 3.963 | x1,03 |
| Monk — A melhor possivel | 1200 | Bony Sea Devil | 10.893 | 5.820 | x1,87 |
| Monk — A melhor possivel | 1500 | Rotten man-maggot | 15.114 | 7.191 | x2,10 |
| Knight (EK) — Sobreviver | 50 | Crawler | 339 | 286 | x1,19 |
| Knight (EK) — Sobreviver | 100 | Orclops | 407 | 552 | x0,74 |
| Knight (EK) — Sobreviver | 200 | Undead Dragon | 1.052 | 1.065 | x0,99 |
| Knight (EK) — Sobreviver | 300 | Naga Lair | 1.588 | 1.564 | x1,02 |
| Knight (EK) — Sobreviver | 500 | Livraria EARTH | 2.433 | 2.538 | x0,96 |
| Knight (EK) — Sobreviver | 800 | Bony Sea Devil | 6.876 | 3.963 | x1,74 |
| Knight (EK) — Sobreviver | 1200 | Bony Sea Devil | 11.977 | 5.820 | x2,06 |
| Knight (EK) — Sobreviver | 1500 | Rotten man-maggot | 17.037 | 7.191 | x2,37 |
| Druid (ED) — Curar bastante | 50 | Crawler | 290 | 286 | x1,01 |
| Druid (ED) — Curar bastante | 100 | Orclops | 566 | 552 | x1,03 |
| Druid (ED) — Curar bastante | 200 | Undead Dragon | 718 | 1.065 | x0,67 |
| Druid (ED) — Curar bastante | 300 | Naga Lair | 1.755 | 1.564 | x1,12 |
| Druid (ED) — Curar bastante | 500 | Livraria EARTH | 1.877 | 2.538 | x0,74 |
| Druid (ED) — Curar bastante | 800 | Bony Sea Devil | 3.437 | 3.963 | x0,87 |
| Druid (ED) — Curar bastante | 1200 | Bony Sea Devil | 8.788 | 5.820 | x1,51 |
| Druid (ED) — Curar bastante | 1500 | Rotten man-maggot | 14.542 | 7.191 | x2,02 |
| Monk — Curar (support) | 50 | Crawler | 234 | 286 | x0,82 |
| Monk — Curar (support) | 100 | Orclops | 518 | 552 | x0,94 |
| Monk — Curar (support) | 200 | Undead Dragon | 902 | 1.065 | x0,85 |
| Monk — Curar (support) | 300 | Naga Lair | 1.318 | 1.564 | x0,84 |
| Monk — Curar (support) | 500 | Livraria EARTH | 2.262 | 2.538 | x0,89 |
| Monk — Curar (support) | 800 | Bony Sea Devil | 4.660 | 3.963 | x1,18 |
| Monk — Curar (support) | 1200 | Bony Sea Devil | 9.188 | 5.820 | x1,58 |
| Monk — Curar (support) | 1500 | Rotten man-maggot | 13.434 | 7.191 | x1,87 |

## 3. Onde o guia e o cliente discordam

| o que | guia | cliente | o que se segue |
|---|---|---|---|
| HP por nivel do monk | 12 | 13 (`j0.monk.hpPerLevel`) | cliente |
| mana por nivel do monk | 10 | 8 (`j0.monk.manaPerLevel`) | cliente |
| base de HP / mana ao nivel 0 | 100 / 90 | nao esta no cliente | guia (unica fonte) |
| regeneracao base de HP/mana | nao publica | nao esta no cliente (e do servidor) | nenhum: fica desconhecida e nao entra |
| golpe do ataque automatico | curva 7,012 x nivel^0,948 sem factores | so a formula dos feiticos | convencao ⚠ (formula do Tibia) |

## 4. A IA de combate (Battle Tactics): o que e cliente e o que e convencao

O cliente calcula a IA em `u4e(nivel, ranks)`: `a = floor(nivel/100)`; `tier = a + ranks`; `qp = min(10, 0,5 x a) + min(10, ranks)`; **chance de decisao perfeita** = `min(1, 0,5 + 0,025 x qp)` (e o «Tactica: nivel N · X %» do painel); **raio de procura dos casts** = `min(1 + floor(qp/7), 3)`; reposicionamento minimo = `max(4000, 5000 - 50 x qp)` ms; kite infinito a partir do tier 3. Texto do cliente: «cada rank vale +100 niveis de IA e afia a CHANCE de jogar perfeito — mira, posicionamento e reacao»; sobre as pranchas: «Nunca decide magia, cura nem pocao: so ONDE».

| o que | valor | fonte |
|---|---|---|
| chance de decisao perfeita | 0,5 + 0,025 x qp (tecto 1) | cliente `u4e` |
| raio de procura dos casts | 1 + floor(qp/7), tecto 3 | cliente `u4e` |
| o que uma decisao imperfeita rende | 60 % do dano de uma perfeita; o dano recebido x (1 + 0,4 x imperfeitas) | **convencao ⚠** (`formulas.TACTICS_IMPERFECT_FACTOR`) |
| raio de procura -> alvos das areas | soma-se ao raio da magia (raio 1 = 3 alvos, 2 = 5, 3+ = o pack) | **convencao ⚠** (`formulas.TACTICS_RADIUS_TO_TARGETS`) |

| nivel | sem o no | Battle Tactics 5 | Battle Tactics 10 |
|---|---|---|---|
| 50 | 50,0 % (raio 1, factor 0,800) | 62,5 % (raio 1, factor 0,850) | 75,0 % (raio 2, factor 0,900) |
| 100 | 51,2 % (raio 1, factor 0,805) | 63,7 % (raio 1, factor 0,855) | 76,2 % (raio 2, factor 0,905) |
| 200 | 52,5 % (raio 1, factor 0,810) | 65,0 % (raio 1, factor 0,860) | 77,5 % (raio 2, factor 0,910) |
| 300 | 53,8 % (raio 1, factor 0,815) | 66,2 % (raio 1, factor 0,865) | 78,8 % (raio 2, factor 0,915) |
| 500 | 56,2 % (raio 1, factor 0,825) | 68,8 % (raio 2, factor 0,875) | 81,2 % (raio 2, factor 0,925) |
| 800 | 60,0 % (raio 1, factor 0,840) | 72,5 % (raio 2, factor 0,890) | 85,0 % (raio 3, factor 0,940) |
| 1200 | 65,0 % (raio 1, factor 0,860) | 77,5 % (raio 2, factor 0,910) | 90,0 % (raio 3, factor 0,960) |
| 1500 | 68,8 % (raio 2, factor 0,875) | 81,2 % (raio 2, factor 0,925) | 93,8 % (raio 3, factor 0,975) |

Fontes: guia = `guiabaiakidle.com` (planner, lido a 16/09/2026); cliente = bundle publico `index-DnzxFejS.js` (09/09/2026). Nada disto foi medido na conta.
