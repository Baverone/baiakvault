"""O que a comunidade diz de cada hunt — as notas BiS do canal CharllonLobo.

Copiadas (nao importadas) do `coach/hunts.py` do Treinador de 09/09/2026, e
chaveadas pelo `id` do `hunts.json` para o teste poder provar que todas apontam
para uma hunt que existe. Sao **opiniao de um jogador em directo, de memoria**;
os numeros de XP/h e gold/h que dizem nao foram medidos por ninguem. Por isso
cada nota leva o id do video e sai na pagina com a fonte ao lado.
"""

CHANNEL = "canal CharllonLobo (YouTube)"

# hunt id -> (nota, id do video)
HUNT_NOTES = {
    "refiner-cave": ("o primeiro gold a serio", "lJq-PNxptTc"),
    "glooth-cave": ("hunt-ancora: gold e XP ate aos 100k do 3.o personagem", "lJq-PNxptTc"),
    "darktorturer-cave": ("glut bags dao slots de BP", "z_DnumUWUhY"),
    "cobra-cave": ("BiS da fase media: XP boa E dropa SSA e Might Ring", "ICzhKPFcZWE"),
    "dreadintruder-cave": ("BiS de supply: 10 min enchem a party de Plasma Ring. Pouco XP e pouco profit", "ICzhKPFcZWE"),
    "vexclaw-lair": ("BiS de Might Ring; XP e gold decentes", "ICzhKPFcZWE"),
    "trueazura-cave": ("XP da fase 300+", "lJq-PNxptTc"),
    "gazer-lair": ("BiS de SSA (~200/h). NAO e hunt de XP nem de gold", "ICzhKPFcZWE"),
    "livrariafire-cave": ("melhor XP do jogo segundo o canal: 30 kk/h, picos de 40-45 (nao medido)", "ICzhKPFcZWE"),
    "lavafungos-cave": ("melhor gold segundo o canal: 23-24 kk/h (nao medido)", "ICzhKPFcZWE"),
    "infernalmdemon-cave": ("o canal desistiu daqui: demasiado forte", "Q1gi-VqwMuY"),
    "rottengolem-cave": ("1.a bag de Soulwar ~3500 kills, nivel 600+; marcar a bag «nao vender»", "Q1gi-VqwMuY"),
}


def for_hunt(hunt_id):
    """`{"text", "video", "source"}` ou `None`."""
    entry = HUNT_NOTES.get(hunt_id)
    if not entry:
        return None
    text, video = entry
    return {"text": text, "video": video,
            "source": "%s, video %s" % (CHANNEL, video)}
