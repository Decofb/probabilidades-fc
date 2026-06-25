"""
DICAS  ->  o que o Cérebro indica explorar, depois de um estudo CRUZADO.

Antes de soltar uma dica, batemos a probabilidade do MODELO (Poisson+Dixon-Coles)
com o HISTÓRICO real dos dois times naquele mercado. Só vira dica quando os dois
CONCORDAM. Se o modelo diz "over" mas os times são de "under", não há dica.

Confiança:
  - "muito provável": modelo alto E histórico forte confirmam.
  - "provável": consenso moderado.
Conflito (modelo x histórico discordam) => nenhuma dica para aquele mercado.

So mercados validados por backtest (1X2, gols, ambas). Nada de escanteios/cartoes.
"""

from __future__ import annotations

from unidecode import unidecode

H_MIN = 0.52          # histórico mínimo dos times p/ confirmar (não contradizer)
H_FORTE = 0.58        # histórico forte (sobe a confiança)


def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


def _confianca(prob: float, hist: float | None) -> str:
    if prob >= 0.72 and (hist is None or hist >= H_MIN):
        return "muito provável"
    if prob >= 0.64 and hist is not None and hist >= H_FORTE:
        return "muito provável"
    return "provável"


def dicas_do_jogo(j, m, perfis: dict | None = None) -> list[dict]:
    perfis = perfis or {}
    pm = perfis.get(_norm(j.mandante))
    pv = perfis.get(_norm(j.visitante))
    tem = pm is not None and pv is not None
    out = []

    def hmed(campo, inv=False):
        if not tem:
            return None
        v = (pm[campo] + pv[campo]) / 2
        return 1 - v if inv else v

    def flagof(*palavras):
        for p in (pm, pv):
            if p:
                f = next((x for x in p.get("flags", []) if any(w in x for w in palavras)), "")
                if f:
                    return f
        return ""

    def emit(mercado, prob, hist, base, reforco=""):
        partes = [f"modelo {round(prob*100)}%"]
        if hist is not None:
            partes.append(f"{round(hist*100)}% no histórico dos times")
        out.append({
            "mercado": mercado, "p": prob, "confianca": _confianca(prob, hist),
            "motivo": f"{base} — " + " · ".join(partes), "reforco": reforco,
        })

    # ---- RESULTADO (cruza com a taxa de vitória do time) ----
    if m.vitoria_mandante >= 0.62 and (not tem or pm["vit"] >= 0.40):
        emit(f"Vitória {j.mandante}", m.vitoria_mandante, pm["vit"] if tem else None,
             "favorito claro", flagof("Casa-dependente"))
    elif m.vitoria_visitante >= 0.62 and (not tem or pv["vit"] >= 0.40):
        emit(f"Vitória {j.visitante}", m.vitoria_visitante, pv["vit"] if tem else None,
             "favorito mesmo fora de casa")

    # ---- GOLS (modelo E histórico têm que concordar) ----
    ho = hmed("o25")
    hu = hmed("o25", inv=True)
    if m.over_25 >= 0.64 and (ho is None or ho >= H_MIN):
        emit("Over 2.5 gols", m.over_25, ho, "jogo tende a ser aberto", flagof("Over"))
    elif (1 - m.over_25) >= 0.64 and (hu is None or hu >= H_MIN):
        emit("Under 2.5 gols", 1 - m.over_25, hu, "jogo tende a ser truncado",
             flagof("Under", "Muralha"))
    elif m.over_15 >= 0.85:
        emit("Over 1.5 gols", m.over_15, None, "raríssimo sair com menos de 2 gols")

    # ---- AMBAS MARCAM ----
    hb = hmed("btts")
    hnb = hmed("btts", inv=True)
    if m.ambas_marcam >= 0.64 and (hb is None or hb >= H_MIN):
        emit("Ambas marcam", m.ambas_marcam, hb, "os dois costumam balançar a rede",
             flagof("Ambas marcam"))
    elif (1 - m.ambas_marcam) >= 0.66 and (hnb is None or hnb >= H_MIN):
        emit("Ambas NÃO marcam", 1 - m.ambas_marcam, hnb, "um lado tende a zerar",
             flagof("Muralha", "Apagado"))

    # mais confiáveis primeiro
    out.sort(key=lambda d: (0 if d["confianca"] == "muito provável" else 1, -d["p"]))
    return out
