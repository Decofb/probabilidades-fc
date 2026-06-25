"""
DICAS  ->  o que o Cérebro indica explorar em cada partida.

So mercados validados por backtest (resultado, gols, ambas marcam). Cada dica
tem a probabilidade do modelo e, quando existe, um REFORCO do padrao do time
(ex: "Cuiabá é 🧱 Under (93% dos jogos)"). Nada de escanteios/cartoes (reprovados).
"""

from __future__ import annotations

from unidecode import unidecode

# limiares minimos para virar dica (acima disso "vale explorar")
LIM_RESULTADO = 0.60
LIM_OVER = 0.62
LIM_UNDER = 0.66
LIM_BTTS = 0.62
LIM_NOBTTS = 0.66
LIM_OVER15 = 0.82


def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


def dicas_do_jogo(j, m, dna: dict | None = None) -> list[dict]:
    dna = dna or {}
    fm = dna.get(_norm(j.mandante), [])
    fv = dna.get(_norm(j.visitante), [])
    out = []

    def flag(flags, *palavras):
        return next((f for f in flags if any(p in f for p in palavras)), "")

    def add(mercado, p, motivo, reforco=""):
        out.append({"mercado": mercado, "p": p, "motivo": motivo, "reforco": reforco})

    pm, pv = m.vitoria_mandante, m.vitoria_visitante
    if pm >= LIM_RESULTADO:
        rf = flag(fm, "Casa-dependente")
        add(f"Vitória {j.mandante}", pm, "favorito claro pelo modelo",
            f"{j.mandante}: {rf}" if rf else "")
    elif pv >= LIM_RESULTADO:
        add(f"Vitória {j.visitante}", pv, "favorito claro pelo modelo", "")

    if m.over_25 >= LIM_OVER:
        rf = flag(fm, "Over") or flag(fv, "Over")
        add("Over 2.5 gols", m.over_25, "jogo tende a ser aberto", rf)
    elif (1 - m.over_25) >= LIM_UNDER:
        rf = flag(fm, "Under", "Muralha") or flag(fv, "Under", "Muralha")
        add("Under 2.5 gols", 1 - m.over_25, "jogo tende a ser truncado", rf)
    elif m.over_15 >= LIM_OVER15:
        add("Over 1.5 gols", m.over_15, "raro sair com menos de 2 gols", "")

    if m.ambas_marcam >= LIM_BTTS:
        rf = flag(fm, "Ambas marcam") or flag(fv, "Ambas marcam")
        add("Ambas marcam", m.ambas_marcam, "os dois costumam balançar a rede", rf)
    elif (1 - m.ambas_marcam) >= LIM_NOBTTS:
        rf = flag(fm, "Muralha", "Apagado") or flag(fv, "Muralha", "Apagado")
        add("Ambas NÃO marcam", 1 - m.ambas_marcam, "um lado tende a zerar", rf)

    return sorted(out, key=lambda d: -d["p"])
