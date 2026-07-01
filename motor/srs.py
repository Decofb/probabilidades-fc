"""
SRS — Simple Rating System ajustado por força de adversário.

Problema que resolve: gols marcados contra adversários fracos inflam o ataque
do time (Bélgica 3-0 Panamá parece melhor do que é; Flamengo 2-1 Grêmio parece
pior do que é contra um time forte). O SRS itera até convergir em ratings onde:

  fator_ataque[t]  = quanto o time marca ÷ quanto os adversários deixam marcar
  fator_defesa[t]  = quanto o time sofre ÷ quanto os adversários costumam marcar

Resultado normalizado: fator=1.0 é a média da liga. Belgica ataque=1.3 significa
que ela marca 30% acima do esperado contra aqueles adversários específicos.

Uso:
    jogos = coletar_jogos_brutos_srs(comp, d1, d2, lambda_decay=0.007)
    srs   = calcular_srs(jogos)
    times = aplicar_srs(times, srs, media_gols_liga)
"""
from __future__ import annotations

from math import exp


def calcular_srs(
    jogos: list[tuple[str, str, float, float, float]],  # (mand, vis, gm, gv, peso)
    n_iter: int = 50,
    suavizacao: float = 0.15,
) -> dict[str, tuple[float, float]]:
    """
    Itera até convergir em (fator_ataque, fator_defesa) para cada time.
    peso = time-decay weight (exp(-λ * dias_atras)).
    Retorna {team: (fator_ataque, fator_defesa)} — média normalizada = 1.0.
    """
    teams: set[str] = set()
    for m, v, *_ in jogos:
        teams.add(m)
        teams.add(v)

    if not teams:
        return {}

    atk = {t: 1.0 for t in teams}
    def_ = {t: 1.0 for t in teams}

    for _ in range(n_iter):
        new_atk: dict[str, float] = {}
        new_def: dict[str, float] = {}

        for team in teams:
            numerador_atk = denominador = 0.0
            numerador_def = 0.0

            for m, v, gm, gv, peso in jogos:
                if m == team:
                    adv_def = def_.get(v, 1.0)
                    adv_atk = atk.get(v, 1.0)
                    numerador_atk += peso * gm / max(adv_def, suavizacao)
                    numerador_def += peso * gv / max(adv_atk, suavizacao)
                    denominador += peso
                elif v == team:
                    adv_def = def_.get(m, 1.0)
                    adv_atk = atk.get(m, 1.0)
                    numerador_atk += peso * gv / max(adv_def, suavizacao)
                    numerador_def += peso * gm / max(adv_atk, suavizacao)
                    denominador += peso

            if denominador > 0:
                new_atk[team] = numerador_atk / denominador
                new_def[team] = numerador_def / denominador
            else:
                new_atk[team] = 1.0
                new_def[team] = 1.0

        # Normaliza para média = 1.0 (garante estabilidade numérica)
        avg_atk = sum(new_atk.values()) / len(new_atk)
        avg_def = sum(new_def.values()) / len(new_def)
        atk = {t: v / max(avg_atk, 1e-6) for t, v in new_atk.items()}
        def_ = {t: v / max(avg_def, 1e-6) for t, v in new_def.items()}

    return {t: (atk.get(t, 1.0), def_.get(t, 1.0)) for t in teams}


def aplicar_srs(
    times: dict,
    srs: dict[str, tuple[float, float]],
    media_gols: float,
    peso_srs: float = 0.6,
) -> dict:
    """
    Substitui gols_feitos/sofridos_por_jogo pelos valores SRS-ajustados.
    Blend: (1-peso_srs)*raw + peso_srs*(media*fator_srs).
    peso_srs=0.6 → SRS tem 60% do peso; raw 40%.
    Mantém todas as outras estatísticas intactas (xG, escanteios, cartões).
    """
    from dataclasses import replace as _replace

    resultado = {}
    for nome, t in times.items():
        fator_atk, fator_def = srs.get(nome, (1.0, 1.0))
        gf_srs = media_gols * fator_atk
        gs_srs = media_gols * fator_def
        gf_blend = (1 - peso_srs) * t.gols_feitos_por_jogo + peso_srs * gf_srs
        gs_blend = (1 - peso_srs) * t.gols_sofridos_por_jogo + peso_srs * gs_srs
        resultado[nome] = _replace(t,
                                   gols_feitos_por_jogo=round(gf_blend, 4),
                                   gols_sofridos_por_jogo=round(gs_blend, 4))
    return resultado


# ── CLI de diagnóstico ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # Exemplo sintético para verificar convergência
    jogos_ex = [
        ("A", "B", 3.0, 0.0, 1.0),
        ("A", "C", 2.0, 1.0, 1.0),
        ("B", "C", 1.0, 1.0, 1.0),
        ("B", "A", 0.0, 2.0, 1.0),
        ("C", "A", 0.0, 3.0, 1.0),
        ("C", "B", 1.0, 1.0, 1.0),
    ]
    srs = calcular_srs(jogos_ex)
    print("SRS sintético:")
    for t, (fa, fd) in sorted(srs.items()):
        print(f"  {t}: ataque={fa:.3f}  defesa={fd:.3f}")
