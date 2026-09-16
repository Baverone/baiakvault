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
| Knight (EK) — Dar dano | 50 | Crawler | 392 | 286 | x1,37 |
| Knight (EK) — Dar dano | 100 | Orclops | 436 | 552 | x0,79 |
| Knight (EK) — Dar dano | 200 | Undead Dragon | 904 | 1.065 | x0,85 |
| Knight (EK) — Dar dano | 300 | Naga Lair | 2.324 | 1.564 | x1,49 |
| Knight (EK) — Dar dano | 500 | Livraria EARTH | 3.769 | 2.538 | x1,48 |
| Knight (EK) — Dar dano | 800 | Bony Sea Devil | 7.576 | 3.963 | x1,91 |
| Knight (EK) — Dar dano | 1200 | Bony Sea Devil | 9.625 | 5.820 | x1,65 |
| Knight (EK) — Dar dano | 1500 | Rotten man-maggot | 13.094 | 7.191 | x1,82 |
| Druid (ED) — Dar dano | 50 | Crawler | 347 | 286 | x1,21 |
| Druid (ED) — Dar dano | 100 | Orclops | 715 | 552 | x1,30 |
| Druid (ED) — Dar dano | 200 | Undead Dragon | 982 | 1.065 | x0,92 |
| Druid (ED) — Dar dano | 300 | Naga Lair | 2.225 | 1.564 | x1,42 |
| Druid (ED) — Dar dano | 500 | Livraria EARTH | 2.936 | 2.538 | x1,16 |
| Druid (ED) — Dar dano | 800 | Bony Sea Devil | 5.960 | 3.963 | x1,50 |
| Druid (ED) — Dar dano | 1200 | Bony Sea Devil | 11.298 | 5.820 | x1,94 |
| Druid (ED) — Dar dano | 1500 | Rotten man-maggot | 16.094 | 7.191 | x2,24 |
| Sorcerer (MS) — Dar dano | 50 | Crawler | 352 | 286 | x1,23 |
| Sorcerer (MS) — Dar dano | 100 | Orclops | 785 | 552 | x1,42 |
| Sorcerer (MS) — Dar dano | 200 | Undead Dragon | 1.522 | 1.065 | x1,43 |
| Sorcerer (MS) — Dar dano | 300 | Naga Lair | 2.421 | 1.564 | x1,55 |
| Sorcerer (MS) — Dar dano | 500 | Livraria EARTH | 4.069 | 2.538 | x1,60 |
| Sorcerer (MS) — Dar dano | 800 | Bony Sea Devil | 9.179 | 3.963 | x2,32 |
| Sorcerer (MS) — Dar dano | 1200 | Bony Sea Devil | 18.301 | 5.820 | x3,14 |
| Sorcerer (MS) — Dar dano | 1500 | Rotten man-maggot | 21.731 | 7.191 | x3,02 |
| Paladin (RP) — Dar dano | 50 | Crawler | 689 | 286 | x2,41 |
| Paladin (RP) — Dar dano | 100 | Orclops | 986 | 552 | x1,79 |
| Paladin (RP) — Dar dano | 200 | Undead Dragon | 1.741 | 1.065 | x1,64 |
| Paladin (RP) — Dar dano | 300 | Naga Lair | 2.310 | 1.564 | x1,48 |
| Paladin (RP) — Dar dano | 500 | Livraria EARTH | 3.282 | 2.538 | x1,29 |
| Paladin (RP) — Dar dano | 800 | Bony Sea Devil | 5.666 | 3.963 | x1,43 |
| Paladin (RP) — Dar dano | 1200 | Bony Sea Devil | 10.417 | 5.820 | x1,79 |
| Paladin (RP) — Dar dano | 1500 | Rotten man-maggot | 14.077 | 7.191 | x1,96 |
| Monk — Dar dano | 50 | Crawler | 230 | 286 | x0,80 |
| Monk — Dar dano | 100 | Orclops | 384 | 552 | x0,70 |
| Monk — Dar dano | 200 | Undead Dragon | 766 | 1.065 | x0,72 |
| Monk — Dar dano | 300 | Naga Lair | 1.179 | 1.564 | x0,75 |
| Monk — Dar dano | 500 | Livraria EARTH | 1.870 | 2.538 | x0,74 |
| Monk — Dar dano | 800 | Bony Sea Devil | 4.241 | 3.963 | x1,07 |
| Monk — Dar dano | 1200 | Bony Sea Devil | 7.140 | 5.820 | x1,23 |
| Monk — Dar dano | 1500 | Rotten man-maggot | 9.366 | 7.191 | x1,30 |
| Knight (EK) — A melhor possivel | 50 | Crawler | 403 | 286 | x1,41 |
| Knight (EK) — A melhor possivel | 100 | Orclops | 409 | 552 | x0,74 |
| Knight (EK) — A melhor possivel | 200 | Undead Dragon | 1.024 | 1.065 | x0,96 |
| Knight (EK) — A melhor possivel | 300 | Naga Lair | 2.164 | 1.564 | x1,38 |
| Knight (EK) — A melhor possivel | 500 | Livraria EARTH | 4.786 | 2.538 | x1,89 |
| Knight (EK) — A melhor possivel | 800 | Bony Sea Devil | 8.397 | 3.963 | x2,12 |
| Knight (EK) — A melhor possivel | 1200 | Bony Sea Devil | 13.586 | 5.820 | x2,33 |
| Knight (EK) — A melhor possivel | 1500 | Rotten man-maggot | 15.307 | 7.191 | x2,13 |
| Druid (ED) — A melhor possivel | 50 | Crawler | 313 | 286 | x1,09 |
| Druid (ED) — A melhor possivel | 100 | Orclops | 650 | 552 | x1,18 |
| Druid (ED) — A melhor possivel | 200 | Undead Dragon | 916 | 1.065 | x0,86 |
| Druid (ED) — A melhor possivel | 300 | Naga Lair | 2.112 | 1.564 | x1,35 |
| Druid (ED) — A melhor possivel | 500 | Livraria EARTH | 2.583 | 2.538 | x1,02 |
| Druid (ED) — A melhor possivel | 800 | Bony Sea Devil | 5.743 | 3.963 | x1,45 |
| Druid (ED) — A melhor possivel | 1200 | Bony Sea Devil | 10.930 | 5.820 | x1,88 |
| Druid (ED) — A melhor possivel | 1500 | Rotten man-maggot | 15.591 | 7.191 | x2,17 |
| Sorcerer (MS) — A melhor possivel | 50 | Crawler | 352 | 286 | x1,23 |
| Sorcerer (MS) — A melhor possivel | 100 | Orclops | 785 | 552 | x1,42 |
| Sorcerer (MS) — A melhor possivel | 200 | Undead Dragon | 1.522 | 1.065 | x1,43 |
| Sorcerer (MS) — A melhor possivel | 300 | Naga Lair | 2.421 | 1.564 | x1,55 |
| Sorcerer (MS) — A melhor possivel | 500 | Livraria EARTH | 4.069 | 2.538 | x1,60 |
| Sorcerer (MS) — A melhor possivel | 800 | Bony Sea Devil | 9.179 | 3.963 | x2,32 |
| Sorcerer (MS) — A melhor possivel | 1200 | Bony Sea Devil | 18.301 | 5.820 | x3,14 |
| Sorcerer (MS) — A melhor possivel | 1500 | Rotten man-maggot | 21.731 | 7.191 | x3,02 |
| Paladin (RP) — A melhor possivel | 50 | Crawler | 689 | 286 | x2,41 |
| Paladin (RP) — A melhor possivel | 100 | Orclops | 986 | 552 | x1,79 |
| Paladin (RP) — A melhor possivel | 200 | Undead Dragon | 1.741 | 1.065 | x1,64 |
| Paladin (RP) — A melhor possivel | 300 | Naga Lair | 2.310 | 1.564 | x1,48 |
| Paladin (RP) — A melhor possivel | 500 | Livraria EARTH | 3.282 | 2.538 | x1,29 |
| Paladin (RP) — A melhor possivel | 800 | Bony Sea Devil | 5.666 | 3.963 | x1,43 |
| Paladin (RP) — A melhor possivel | 1200 | Bony Sea Devil | 10.417 | 5.820 | x1,79 |
| Paladin (RP) — A melhor possivel | 1500 | Rotten man-maggot | 14.077 | 7.191 | x1,96 |
| Monk — A melhor possivel | 50 | Crawler | 222 | 286 | x0,78 |
| Monk — A melhor possivel | 100 | Orclops | 381 | 552 | x0,69 |
| Monk — A melhor possivel | 200 | Undead Dragon | 738 | 1.065 | x0,69 |
| Monk — A melhor possivel | 300 | Naga Lair | 1.063 | 1.564 | x0,68 |
| Monk — A melhor possivel | 500 | Livraria EARTH | 1.717 | 2.538 | x0,68 |
| Monk — A melhor possivel | 800 | Bony Sea Devil | 3.391 | 3.963 | x0,86 |
| Monk — A melhor possivel | 1200 | Bony Sea Devil | 7.797 | 5.820 | x1,34 |
| Monk — A melhor possivel | 1500 | Rotten man-maggot | 8.692 | 7.191 | x1,21 |
| Knight (EK) — Sobreviver | 50 | Crawler | 339 | 286 | x1,19 |
| Knight (EK) — Sobreviver | 100 | Orclops | 392 | 552 | x0,71 |
| Knight (EK) — Sobreviver | 200 | Undead Dragon | 794 | 1.065 | x0,75 |
| Knight (EK) — Sobreviver | 300 | Naga Lair | 1.588 | 1.564 | x1,02 |
| Knight (EK) — Sobreviver | 500 | Livraria EARTH | 2.433 | 2.538 | x0,96 |
| Knight (EK) — Sobreviver | 800 | Bony Sea Devil | 6.807 | 3.963 | x1,72 |
| Knight (EK) — Sobreviver | 1200 | Bony Sea Devil | 11.977 | 5.820 | x2,06 |
| Knight (EK) — Sobreviver | 1500 | Rotten man-maggot | 16.922 | 7.191 | x2,35 |
| Druid (ED) — Curar bastante | 50 | Crawler | 290 | 286 | x1,01 |
| Druid (ED) — Curar bastante | 100 | Orclops | 566 | 552 | x1,03 |
| Druid (ED) — Curar bastante | 200 | Undead Dragon | 706 | 1.065 | x0,66 |
| Druid (ED) — Curar bastante | 300 | Naga Lair | 1.653 | 1.564 | x1,06 |
| Druid (ED) — Curar bastante | 500 | Livraria EARTH | 1.759 | 2.538 | x0,69 |
| Druid (ED) — Curar bastante | 800 | Bony Sea Devil | 3.317 | 3.963 | x0,84 |
| Druid (ED) — Curar bastante | 1200 | Bony Sea Devil | 8.406 | 5.820 | x1,44 |
| Druid (ED) — Curar bastante | 1500 | Rotten man-maggot | 13.727 | 7.191 | x1,91 |
| Monk — Curar (support) | 50 | Crawler | 233 | 286 | x0,82 |
| Monk — Curar (support) | 100 | Orclops | 519 | 552 | x0,94 |
| Monk — Curar (support) | 200 | Undead Dragon | 902 | 1.065 | x0,85 |
| Monk — Curar (support) | 300 | Naga Lair | 1.319 | 1.564 | x0,84 |
| Monk — Curar (support) | 500 | Livraria EARTH | 2.265 | 2.538 | x0,89 |
| Monk — Curar (support) | 800 | Bony Sea Devil | 4.617 | 3.963 | x1,17 |
| Monk — Curar (support) | 1200 | Bony Sea Devil | 9.014 | 5.820 | x1,55 |
| Monk — Curar (support) | 1500 | Rotten man-maggot | 13.273 | 7.191 | x1,85 |

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
