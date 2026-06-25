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

# MODO RÍGIDO: só sai dica quando o modelo é alto E o histórico dos dois times
# confirma forte. Sem histórico, só near-certezas (Over 1.5 / favorito dominante).
H_MIN = 0.58          # histórico mínimo dos dois times p/ confirmar (forte)
P_RESULT = 0.66       # prob mínima de vitória
P_GOLS = 0.66         # prob mínima over/under/btts
P_NOBTTS = 0.68
P_OVER15 = 0.88       # near-certeza
VIT_MIN = 0.45        # o favorito também precisa vir ganhando


def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


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
            "mercado": mercado, "p": prob, "confianca": "muito provável",
            "motivo": f"{base} — " + " · ".join(partes), "reforco": reforco,
        })

    # ---- RESULTADO ----
    if m.vitoria_mandante >= P_RESULT and (not tem or pm["vit"] >= VIT_MIN):
        emit(f"Vitória {j.mandante}", m.vitoria_mandante, pm["vit"] if tem else None,
             "favorito claro e vem ganhando", flagof("Casa-dependente"))
    elif m.vitoria_visitante >= P_RESULT and (not tem or pv["vit"] >= VIT_MIN):
        emit(f"Vitória {j.visitante}", m.vitoria_visitante, pv["vit"] if tem else None,
             "favorito mesmo fora de casa")

    # ---- GOLS (rígido: histórico é OBRIGATÓRIO e tem que confirmar forte) ----
    ho = hmed("o25")
    hu = hmed("o25", inv=True)
    if m.over_25 >= P_GOLS and ho is not None and ho >= H_MIN:
        emit("Over 2.5 gols", m.over_25, ho, "jogo aberto e confirmado pelo histórico", flagof("Over"))
    elif (1 - m.over_25) >= P_GOLS and hu is not None and hu >= H_MIN:
        emit("Under 2.5 gols", 1 - m.over_25, hu, "jogo truncado e confirmado pelo histórico",
             flagof("Under", "Muralha"))
    elif m.over_15 >= P_OVER15:
        emit("Over 1.5 gols", m.over_15, None, "raríssimo sair com menos de 2 gols")

    # ---- AMBAS MARCAM ----
    hb = hmed("btts")
    hnb = hmed("btts", inv=True)
    if m.ambas_marcam >= P_GOLS and hb is not None and hb >= H_MIN:
        emit("Ambas marcam", m.ambas_marcam, hb, "os dois marcam e o histórico confirma",
             flagof("Ambas marcam"))
    elif (1 - m.ambas_marcam) >= P_NOBTTS and hnb is not None and hnb >= H_MIN:
        emit("Ambas NÃO marcam", 1 - m.ambas_marcam, hnb, "um lado tende a zerar",
             flagof("Muralha", "Apagado"))

    out.sort(key=lambda d: -d["p"])
    return out
