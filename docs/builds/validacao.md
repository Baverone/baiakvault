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

## 1b. Contas a mao com uma runa e Battle Tactics (ordem 8, 16/09/2026)

Perfil: **sorcerer nivel 471 em Livraria FIRE**, a rotacao que o Andre fixou (Rage of the Skies + Avalanche — a Avalanche e uma runa: 64 gold por lancamento, mana 5, cooldown 2 s), Battle Tactics 7, arvore de 12 nos (Arcane Power 10, Arcane Focus 4, Voltaics 5, Devastation 2, Ignite 1, Wildfire 10, Conduit 5, Focus Mastery 1, Overchannel 7, Necromancy 1, Soul Harvest 1, Battle Tactics 7), o equipamento e os imbuements do perfil de cima. Sem cura e com pocoes: o que se confere e a rotacao na grelha de 2 s (a magia com mais dano por lancamento primeiro: Rage of the Skies cabe 6 vezes em 60 s, a runa apanha os outros 24 slots), o gold/h das runas e o das pocoes de mana **em regime** (deficit de mana x preco por mana da ultimate mana potion, 488 gold por 800). As pocoes de vida dependem do ciclo de cura do simulador e nao se validam a mao. Constantes proprias desta conta: rune_mana = 5 (cliente: `mana: 5` nas runas (bruto/feiticos.json)); rune_cd_s = 2 (cliente: `cd: 2000` nas runas); area_targets_radius_3plus = 9 (convencao ⚠ AREA_TARGETS: raio 3+ (com o raio de procura da IA somado) = 9, limitado ao pack); ultimate_mana_potion = (800, 488) (cliente: ultimate mana potion, 800 de mana por 488 gold (sorcerer/druid, nivel 130+)).

| numero | a mao | simulador | diferenca | |
|---|---|---|---|---|
| custo da arvore (pontos) | 320 | 320 | +0,00 % | ok |
| factor da IA de combate (Battle Tactics 7) | 0,9 | 0,9 | +0,00 % | ok |
| magic level (guia + itens) | 72,1 | 72,1 | +0,00 % | ok |
| HP maximo | 2.455,0 | 2.455,0 | +0,00 % | ok |
| mana maxima | 14.220,0 | 14.220,0 | +0,00 % | ok |
| lancamentos de Rage of the Skies em 60 s | 6 | 6 | +0,00 % | ok |
| lancamentos de Avalanche (runa) em 60 s | 24 | 24 | +0,00 % | ok |
| DPS contra o pack | 1.851,5 | 1.851,5 | -0,00 % | ok |
| DPS contra o boss (x3 HP) | 472,7 | 472,7 | -0,00 % | ok |
| DPS do ciclo | 1.576,3 | 1.576,3 | -0,00 % | ok |
| dano/s do ataque automatico (wand) | 37,5 | 37,5 | +0,00 % | ok |
| mana/s gasta pela rotacao | 62,0 | 62,0 | +0,00 % | ok |
| gold/h das runas | 92.160,0 | 92.160,0 | +0,00 % | ok |
| gold/h das pocoes de mana em regime | 136.152,0 | 136.152,0 | +0,00 % | ok |

**Tudo dentro da tolerancia.**

## 1c. O Avatar: o caminho ligado mais barato + 300, a mao, por vocacao (ordem 9, 21/09/2026)

A 1.a prioridade do Andre e o notable de tier 11. A conta a mao (`validation.avatar_reach_by_hand`) e um Dijkstra proprio sobre o `arvore.json` cru — um rank por no, a ligacao e o `requer` nos dois sentidos (cliente `MK`), a partir dos nos de tier 0 — sem importar o motor; ao lado o que o motor (`builds.avatar_reach`) deu. O nivel em que cabe = caminho + 300, porque cada nivel da um ponto.

| vocacao | caminho a mao (pontos) | nivel em que cabe (a mao) | motor: pontos / nivel | ok | o caminho |
|---|---|---|---|---|---|
| Knight (EK) | 16 | 316 | 16 / 316 | sim | Plating, Fire Ward, Resilience, Guardian, Energy Ward, Fortress, Iron Will, Colossus |
| Paladin (RP) | 19 | 319 | 19 / 319 | sim | Faith, Holy Ward, Blessed Ammunition, Lifesteal Shot, Sanctify, Divine Grace, Reprisal, Crusader, Relentless, Lightbringer |
| Sorcerer (MS) | 16 | 316 | 16 / 316 | sim | Deep Well, Mind Spring, Energy Ward, Bottomless Well, Fire Ward, Lichform, Nether Ward, Cataclysm |
| Druid (ED) | 20 | 320 | 20 / 320 | sim | Nature's Wrath, Frost Attunement, Frostbite, Glacier, Winter Heart, Nature's Bond, Overgrowth, Elder Wisdom, Lifekeeper, Evergreen |
| Monk | 19 | 319 | 19 / 319 | sim | Inner Focus, Chi Drain, Pressure Points, Meditation, Still Mind, Soul Flow, Spirit Guard, Zenith, Transcendence, Enlightened |

## 1d. As rotas ate ao Avatar: quantas sao e a mais barata, a mao, por vocacao (ordem 9b, 21/09/2026)

Desde a correccao do Andre (21/09/2026) a rota ate ao Avatar e a mais util pelas prioridades, nao a mais barata: o motor enumera todas as rotas que so sobem (cada passo vai de um no para um que o `requer`) e avalia cada uma. A conta a mao (`validation.avatar_routes_by_hand`) conta as rotas por programacao dinamica sobre o `arvore.json` cru, por tier crescente, e o custo da mais barata pelo mesmo caminho — sem importar o motor; ao lado o que o motor (`builds.avatar_routes`) deu, e a rota que ele escolheu ao nivel de cada build dele.

| vocacao | rotas (a mao) | mais barata (a mao) | motor: rotas / mais barata | ok | escolhida na build de nivel 500 (pontos, Avatar ao nivel) |
|---|---|---|---|---|---|
| Knight (EK) | 299 | 16 | 299 / 16 | sim | 19 pontos, Avatar ao nivel 319 (Fury, Sharpened Steel, Vampiric Blows, Second Wind, Bloodlust, Cold Precision, Overpower, Smite, Warlust, Carnage) |
| Paladin (RP) | 304 | 19 | 304 / 19 | sim | 21 pontos, Avatar ao nivel 321 (Might, Rapid Fire, Piercing Bolts, Precision, Swift Quiver, Marksman, Deadly Aim, Zealot, Crusader, Relentless, Lightbringer) |
| Sorcerer (MS) | 513 | 16 | 513 / 16 | sim | 20 pontos, Avatar ao nivel 320 (Arcane Focus, Devastation, Quickened Casting, Necromancy, Soul Harvest, Reaper, Death Chill, Archmage, Void Touch, Cataclysm) |
| Druid (ED) | 820 | 20 | 820 / 20 | sim | 21 pontos, Avatar ao nivel 321 (Nature's Wrath, Terra Attunement, Fortune, Herbalist, Lucky Charm, Windfall, Ice Ward, Stone Skin, Grove Guardian, Lifekeeper, Evergreen) |
| Monk | 908 | 19 | 908 / 19 | sim | 21 pontos, Avatar ao nivel 321 (Inner Focus, Chi Drain, Pressure Points, Crane Style, Swift Strikes, Sacred Fist, Flurry, Inner Peace, Ascendant, Harmony, Enlightened) |

## 1e. Chance de critico vs dano critico: +1 % de cada, a mao, no sorcerer dele (ordem 10, 21/09/2026)

A regra de 21/09/2026 («Avatar, e depois o que e melhor: Atk, Chance Critico ou Dano Critico») responde-se com o valor marginal de cada stat medido no simulador sobre a arvore «rota + Avatar». Aqui a mesma conta a mao (`validation.crit_marginals_by_hand`, so com o `arvore.json`, os itens e a formula do critico `1 + chance x (50 + critDmg)/10000` do guia, mais o Avatar «crita sempre» 15 s do cliente): como o critico multiplica todo o dano que sai, +1 de chance na arvore vale (1 − uptime) × (50 + critDmg)/10000 / M e +1 de dano critico vale chance efectiva/10000 / M. Tolerancia 5 %.

Sorcerer nivel 481, rotacao Rage of the Skies, Avalanche, arvore das etapas antes do dano «rota + Avatar + Exp + Loot» (12 nos, 375 pontos): chance da arvore + itens 11,3 %, dano critico 62,5 %, attack speed 0,0 %, Avatar 5,0 % por golpe → uptime 42,9 %, chance efectiva 49,3 %, multiplicador 1,5548.

| o que | a mao | simulador | diferenca | ok |
|---|---|---|---|---|
| +1 % de chance de critico (fraccao do DPS) | 0,413 % | 0,413 % | -0,00 % | sim |
| +1 % de dano critico (fraccao do DPS) | 0,317 % | 0,317 % | 0,00 % | sim |

## 1f. Exp e Loot antes do dano: os pontos de cada etapa, a mao, por vocacao (ordem 10b, 21/09/2026)

A regra precisada pelo Andre («Avatar, Exp, Loot, e tu decides o resto»): a Exp e o Loot esgotam-se antes de um ponto ir ao dano. A conta a mao (`validation.exp_loot_by_hand`, so com o `arvore.json` cru) soma o +% exp e o +% loot da arvore final e os pontos gastos nos nos de cada um (cliente `z3e`), e verifica na arvore das etapas 1-3 (rota + Avatar + Exp + Loot, antes do dano) que o rank de Exp/Loot mais barato que ainda se podia comprar (o proximo rank mais o caminho, Dijkstra proprio) nao cabia nos pontos que sobravam. Ao lado o que o motor deu. Build «prioridades» de nivel 500.

| vocacao | +% exp a mao / motor | pontos em nos de Exp | +% loot a mao / motor | pontos em nos de Loot | antes do dano: sobravam / rank de Exp ou Loot mais barato | esgotadas | ok |
|---|---|---|---|---|---|---|---|
| Knight (EK) | 0,0 / 0,0 | sem nos de Exp | 0,0 / 0,0 | sem nos de Loot | 181 / nenhum por comprar | sim | sim |
| Paladin (RP) | 10,0 / 10,0 | 55 | 10,0 / 10,0 | 55 | 66 / nenhum por comprar | sim | sim |
| Sorcerer (MS) | 10,0 / 10,0 | 55 | 0,0 / 0,0 | sem nos de Loot | 125 / nenhum por comprar | sim | sim |
| Druid (ED) | 22,0 / 22,0 | 165 | 6,4 / 6,4 | 16 | 4 / 5 pontos | sim | sim |
| Monk | 5,0 / 5,0 | 100 | 5,0 / 5,0 | 100 | 77 / nenhum por comprar | sim | sim |

## 2. A curva de DPS do guia vs o DPS do ciclo do simulador

Curva do guia: `7,012 x nivel^0,948` (guiabaiakidle.com/_astro/character-planner.D0n3Vxn3.js — `F=7.012,I=.948` (lido a 2026-09-16)). E uma referencia sem vocacao, hunt nem equipamento; a razao mostra quanto cada build se afasta dela — nao ha «certo» aqui, ha o que cada um diz.

| build | nivel | hunt | DPS ciclo (simulador) | curva do guia | razao |
|---|---|---|---|---|---|
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 50 | Crawler | 398 | 286 | x1,39 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 100 | Orclops | 402 | 552 | x0,73 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 200 | Undead Dragon | 1.097 | 1.065 | x1,03 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 300 | Naga Lair | 3.034 | 1.564 | x1,94 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 500 | Livraria EARTH | 5.313 | 2.538 | x2,09 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 800 | Bony Sea Devil | 8.821 | 3.963 | x2,23 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1200 | Bony Sea Devil | 18.790 | 5.820 | x3,23 |
| Knight (EK) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1500 | Rotten man-maggot | 25.650 | 7.191 | x3,57 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 50 | Crawler | 290 | 286 | x1,01 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 100 | Orclops | 539 | 552 | x0,98 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 200 | Undead Dragon | 632 | 1.065 | x0,59 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 300 | Naga Lair | 1.289 | 1.564 | x0,82 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 500 | Livraria EARTH | 1.861 | 2.538 | x0,73 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 800 | Bony Sea Devil | 4.455 | 3.963 | x1,12 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1200 | Bony Sea Devil | 9.762 | 5.820 | x1,68 |
| Druid (ED) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1500 | Rotten man-maggot | 16.468 | 7.191 | x2,29 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 50 | Crawler | 307 | 286 | x1,07 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 100 | Orclops | 621 | 552 | x1,13 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 200 | Undead Dragon | 1.416 | 1.065 | x1,33 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 300 | Naga Lair | 2.277 | 1.564 | x1,46 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 500 | Livraria EARTH | 3.757 | 2.538 | x1,48 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 800 | Bony Sea Devil | 9.199 | 3.963 | x2,32 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1200 | Bony Sea Devil | 19.741 | 5.820 | x3,39 |
| Sorcerer (MS) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1500 | Rotten man-maggot | 25.477 | 7.191 | x3,54 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 50 | Crawler | 635 | 286 | x2,22 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 100 | Orclops | 855 | 552 | x1,55 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 200 | Undead Dragon | 1.656 | 1.065 | x1,56 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 300 | Naga Lair | 2.367 | 1.564 | x1,51 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 500 | Livraria EARTH | 3.733 | 2.538 | x1,47 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 800 | Bony Sea Devil | 8.126 | 3.963 | x2,05 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1200 | Bony Sea Devil | 15.172 | 5.820 | x2,61 |
| Paladin (RP) — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1500 | Rotten man-maggot | 23.329 | 7.191 | x3,24 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 50 | Crawler | 228 | 286 | x0,80 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 100 | Orclops | 535 | 552 | x0,97 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 200 | Undead Dragon | 674 | 1.065 | x0,63 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 300 | Naga Lair | 1.214 | 1.564 | x0,78 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 500 | Livraria EARTH | 2.320 | 2.538 | x0,91 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 800 | Bony Sea Devil | 5.358 | 3.963 | x1,35 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1200 | Bony Sea Devil | 11.529 | 5.820 | x1,98 |
| Monk — Prioridades do Andre: Avatar › Exp › Loot › dano (o simulador decide) | 1500 | Rotten man-maggot | 14.698 | 7.191 | x2,04 |
| Knight (EK) — Dar dano | 50 | Crawler | 428 | 286 | x1,50 |
| Knight (EK) — Dar dano | 100 | Orclops | 510 | 552 | x0,92 |
| Knight (EK) — Dar dano | 200 | Undead Dragon | 1.194 | 1.065 | x1,12 |
| Knight (EK) — Dar dano | 300 | Naga Lair | 2.324 | 1.564 | x1,49 |
| Knight (EK) — Dar dano | 500 | Livraria EARTH | 4.043 | 2.538 | x1,59 |
| Knight (EK) — Dar dano | 800 | Bony Sea Devil | 8.495 | 3.963 | x2,14 |
| Knight (EK) — Dar dano | 1200 | Bony Sea Devil | 17.228 | 5.820 | x2,96 |
| Knight (EK) — Dar dano | 1500 | Rotten man-maggot | 24.301 | 7.191 | x3,38 |
| Druid (ED) — Dar dano | 50 | Crawler | 347 | 286 | x1,21 |
| Druid (ED) — Dar dano | 100 | Orclops | 728 | 552 | x1,32 |
| Druid (ED) — Dar dano | 200 | Undead Dragon | 1.012 | 1.065 | x0,95 |
| Druid (ED) — Dar dano | 300 | Naga Lair | 2.227 | 1.564 | x1,42 |
| Druid (ED) — Dar dano | 500 | Livraria EARTH | 2.395 | 2.538 | x0,94 |
| Druid (ED) — Dar dano | 800 | Bony Sea Devil | 5.960 | 3.963 | x1,50 |
| Druid (ED) — Dar dano | 1200 | Bony Sea Devil | 11.298 | 5.820 | x1,94 |
| Druid (ED) — Dar dano | 1500 | Rotten man-maggot | 17.583 | 7.191 | x2,45 |
| Sorcerer (MS) — Dar dano | 50 | Crawler | 352 | 286 | x1,23 |
| Sorcerer (MS) — Dar dano | 100 | Orclops | 785 | 552 | x1,42 |
| Sorcerer (MS) — Dar dano | 200 | Undead Dragon | 1.540 | 1.065 | x1,45 |
| Sorcerer (MS) — Dar dano | 300 | Naga Lair | 2.434 | 1.564 | x1,56 |
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
| Monk — Dar dano | 50 | Crawler | 230 | 286 | x0,81 |
| Monk — Dar dano | 100 | Orclops | 499 | 552 | x0,90 |
| Monk — Dar dano | 200 | Undead Dragon | 865 | 1.065 | x0,81 |
| Monk — Dar dano | 300 | Naga Lair | 1.275 | 1.564 | x0,82 |
| Monk — Dar dano | 500 | Livraria EARTH | 1.871 | 2.538 | x0,74 |
| Monk — Dar dano | 800 | Bony Sea Devil | 4.282 | 3.963 | x1,08 |
| Monk — Dar dano | 1200 | Bony Sea Devil | 10.893 | 5.820 | x1,87 |
| Monk — Dar dano | 1500 | Rotten man-maggot | 15.114 | 7.191 | x2,10 |
| Knight (EK) — A melhor possivel | 50 | Crawler | 428 | 286 | x1,50 |
| Knight (EK) — A melhor possivel | 100 | Orclops | 422 | 552 | x0,76 |
| Knight (EK) — A melhor possivel | 200 | Undead Dragon | 1.025 | 1.065 | x0,96 |
| Knight (EK) — A melhor possivel | 300 | Naga Lair | 1.814 | 1.564 | x1,16 |
| Knight (EK) — A melhor possivel | 500 | Livraria EARTH | 4.338 | 2.538 | x1,71 |
| Knight (EK) — A melhor possivel | 800 | Bony Sea Devil | 8.397 | 3.963 | x2,12 |
| Knight (EK) — A melhor possivel | 1200 | Bony Sea Devil | 17.228 | 5.820 | x2,96 |
| Knight (EK) — A melhor possivel | 1500 | Rotten man-maggot | 24.301 | 7.191 | x3,38 |
| Druid (ED) — A melhor possivel | 50 | Crawler | 313 | 286 | x1,09 |
| Druid (ED) — A melhor possivel | 100 | Orclops | 714 | 552 | x1,29 |
| Druid (ED) — A melhor possivel | 200 | Undead Dragon | 1.012 | 1.065 | x0,95 |
| Druid (ED) — A melhor possivel | 300 | Naga Lair | 2.227 | 1.564 | x1,42 |
| Druid (ED) — A melhor possivel | 500 | Livraria EARTH | 2.395 | 2.538 | x0,94 |
| Druid (ED) — A melhor possivel | 800 | Bony Sea Devil | 5.960 | 3.963 | x1,50 |
| Druid (ED) — A melhor possivel | 1200 | Bony Sea Devil | 11.298 | 5.820 | x1,94 |
| Druid (ED) — A melhor possivel | 1500 | Rotten man-maggot | 17.583 | 7.191 | x2,45 |
| Sorcerer (MS) — A melhor possivel | 50 | Crawler | 352 | 286 | x1,23 |
| Sorcerer (MS) — A melhor possivel | 100 | Orclops | 785 | 552 | x1,42 |
| Sorcerer (MS) — A melhor possivel | 200 | Undead Dragon | 1.540 | 1.065 | x1,45 |
| Sorcerer (MS) — A melhor possivel | 300 | Naga Lair | 2.434 | 1.564 | x1,56 |
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
| Monk — A melhor possivel | 50 | Crawler | 227 | 286 | x0,79 |
| Monk — A melhor possivel | 100 | Orclops | 381 | 552 | x0,69 |
| Monk — A melhor possivel | 200 | Undead Dragon | 699 | 1.065 | x0,66 |
| Monk — A melhor possivel | 300 | Naga Lair | 1.075 | 1.564 | x0,69 |
| Monk — A melhor possivel | 500 | Livraria EARTH | 1.462 | 2.538 | x0,58 |
| Monk — A melhor possivel | 800 | Bony Sea Devil | 4.092 | 3.963 | x1,03 |
| Monk — A melhor possivel | 1200 | Bony Sea Devil | 10.893 | 5.820 | x1,87 |
| Monk — A melhor possivel | 1500 | Rotten man-maggot | 15.114 | 7.191 | x2,10 |
| Knight (EK) — Sobreviver | 50 | Crawler | 339 | 286 | x1,19 |
| Knight (EK) — Sobreviver | 100 | Orclops | 404 | 552 | x0,73 |
| Knight (EK) — Sobreviver | 200 | Undead Dragon | 1.055 | 1.065 | x0,99 |
| Knight (EK) — Sobreviver | 300 | Naga Lair | 1.588 | 1.564 | x1,02 |
| Knight (EK) — Sobreviver | 500 | Livraria EARTH | 2.449 | 2.538 | x0,96 |
| Knight (EK) — Sobreviver | 800 | Bony Sea Devil | 6.863 | 3.963 | x1,73 |
| Knight (EK) — Sobreviver | 1200 | Bony Sea Devil | 11.977 | 5.820 | x2,06 |
| Knight (EK) — Sobreviver | 1500 | Rotten man-maggot | 16.922 | 7.191 | x2,35 |
| Druid (ED) — Curar bastante | 50 | Crawler | 290 | 286 | x1,01 |
| Druid (ED) — Curar bastante | 100 | Orclops | 566 | 552 | x1,03 |
| Druid (ED) — Curar bastante | 200 | Undead Dragon | 718 | 1.065 | x0,67 |
| Druid (ED) — Curar bastante | 300 | Naga Lair | 1.755 | 1.564 | x1,12 |
| Druid (ED) — Curar bastante | 500 | Livraria EARTH | 1.879 | 2.538 | x0,74 |
| Druid (ED) — Curar bastante | 800 | Bony Sea Devil | 3.317 | 3.963 | x0,84 |
| Druid (ED) — Curar bastante | 1200 | Bony Sea Devil | 8.788 | 5.820 | x1,51 |
| Druid (ED) — Curar bastante | 1500 | Rotten man-maggot | 14.542 | 7.191 | x2,02 |
| Monk — Curar (support) | 50 | Crawler | 243 | 286 | x0,85 |
| Monk — Curar (support) | 100 | Orclops | 519 | 552 | x0,94 |
| Monk — Curar (support) | 200 | Undead Dragon | 902 | 1.065 | x0,85 |
| Monk — Curar (support) | 300 | Naga Lair | 1.316 | 1.564 | x0,84 |
| Monk — Curar (support) | 500 | Livraria EARTH | 2.310 | 2.538 | x0,91 |
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
