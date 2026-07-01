"""
Calibração estatística do modelo.

4. RHO DE DIXON-COLES via MLE
   O rho=-0.06 foi estimado no futebol inglês dos anos 90. Este módulo estima
   o rho ótimo para os nossos dados reais usando Maximum Likelihood.

5. PLATT SCALING (calibração de probabilidades)
   Quando dizemos "70% de chance", o resultado real ocorre 70% das vezes?
   Platt scaling aplica uma correção logística se houver viés sistemático.
   Precisa de ≥50 jogos conferidos para ser confiável.

Uso em atualizar.py:
    from motor.calibrar import carregar_rho, calibrar_e_salvar_rho
    rho = carregar_rho(liga_key)          # usa cache JSON
    p_cal = aplicar_platt(p_raw, coefs)  # corrige probabilidade
"""
from __future__ import annotations

import json
from math import exp, factorial, log
from pathlib import Path

_CACHE_DIR = Path(__file__).parent.parent / "cache" / "calibracao"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers Poisson + Dixon-Coles ─────────────────────────────────────────────

def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * exp(-lam) / factorial(k)


def _tau(i: int, j: int, lm: float, lv: float, rho: float) -> float:
    if i == 0 and j == 0:
        return 1.0 - lm * lv * rho
    if i == 0 and j == 1:
        return 1.0 + lm * rho
    if i == 1 and j == 0:
        return 1.0 + lv * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


# ── Golden-section search (sem scipy) ─────────────────────────────────────────

def _golden_min(f, a: float, b: float, tol: float = 1e-5) -> float:
    phi = (3 - 5 ** 0.5) / 2
    c, d = a + phi * (b - a), b - phi * (b - a)
    fc, fd = f(c), f(d)
    while abs(b - a) > tol:
        if fc < fd:
            b = d; d = c; fd = fc
            c = a + phi * (b - a); fc = f(c)
        else:
            a = c; c = d; fc = fd
            d = b - phi * (b - a); fd = f(d)
    return (a + b) / 2


# ── 4. Calibração do rho Dixon-Coles ─────────────────────────────────────────

def mle_rho(
    jogos: list[tuple[float, float, int, int]],  # (lam_m, lam_v, gm, gv)
) -> float:
    """
    Maximiza log-likelihood de Dixon-Coles sobre rho ∈ [-0.4, 0.4].
    Usa só placares baixos (≤3 gols/time) onde a correção DC é relevante.
    """
    filtrados = [(lm, lv, gm, gv) for lm, lv, gm, gv in jogos
                 if gm <= 3 and gv <= 3]
    if len(filtrados) < 20:
        return -0.06  # padrão seguro se dados insuficientes

    def neg_ll(rho: float) -> float:
        total = 0.0
        for lm, lv, gm, gv in filtrados:
            tau = _tau(gm, gv, lm, lv, rho)
            if tau <= 0:
                return 1e9
            p = _poisson_pmf(gm, lm) * _poisson_pmf(gv, lv) * tau
            total += log(max(p, 1e-15))
        return -total

    return _golden_min(neg_ll, -0.4, 0.4)


def calibrar_rho_de_jogos_brutos(
    jogos_brutos: list[tuple[str, str, float, float, float]],  # (m, v, gm, gv, peso)
    media_m: float,
    media_v: float,
) -> float:
    """
    Estima rho usando os resultados brutos da liga.
    lam_m e lam_v são aproximados pelas médias da liga (rápido, sem recalcular
    o modelo completo para cada jogo histórico).
    """
    entradas = [(media_m, media_v, int(gm), int(gv))
                for _, _, gm, gv, _ in jogos_brutos
                if gm == int(gm) and gv == int(gv)]
    return mle_rho(entradas)


def salvar_rho(liga_key: str, rho: float) -> None:
    p = _CACHE_DIR / f"rho_{liga_key}.json"
    p.write_text(json.dumps({"rho": rho, "liga": liga_key}), encoding="utf-8")


def carregar_rho(liga_key: str, default: float = -0.06) -> float:
    p = _CACHE_DIR / f"rho_{liga_key}.json"
    if p.exists():
        try:
            return float(json.loads(p.read_text(encoding="utf-8"))["rho"])
        except Exception:
            pass
    return default


# ── 5. Platt Scaling (calibração de probabilidades) ──────────────────────────

_MIN_JOGOS_CALIBRACAO = 20


def _sigmoid(x: float, a: float, b: float) -> float:
    return 1.0 / (1.0 + exp(-(a * x + b)))


def _logit(p: float) -> float:
    p = max(1e-6, min(1 - 1e-6, p))
    return log(p / (1 - p))


def treinar_platt(registros: list[dict]) -> dict | None:
    """
    registros: lista de dicts do CSV de previsões com p1/px/p2 e gm/gv.
    Retorna {"a": float, "b": float} ou None se dados insuficientes.
    Usa gradiente descendente simples (sem scipy).
    """
    conferidos = [r for r in registros
                  if r.get("gm") not in (None, "", "—")
                  and r.get("gv") not in (None, "", "—")]
    if len(conferidos) < _MIN_JOGOS_CALIBRACAO:
        return None

    # Monta pares (logit(p_previsto), resultado_ocorreu) para cada mercado 1X2
    dados: list[tuple[float, float]] = []
    for r in conferidos:
        try:
            gm, gv = float(r["gm"]), float(r["gv"])
        except (ValueError, KeyError):
            continue
        resultado = 0 if gm > gv else (1 if gm == gv else 2)
        for i, col in enumerate(["p1", "px", "p2"]):
            try:
                p = float(r.get(col) or 0)
            except ValueError:
                continue
            if 0.02 < p < 0.98:
                dados.append((_logit(p), 1.0 if resultado == i else 0.0))

    if len(dados) < 30:
        return None

    # Gradiente descendente
    a, b = 1.0, 0.0
    lr = 0.05
    for _ in range(300):
        da = db = 0.0
        for x, y in dados:
            p_hat = _sigmoid(x, a, b)
            err = p_hat - y
            da += err * x
            db += err
        n = len(dados)
        a -= lr * da / n
        b -= lr * db / n

    return {"a": round(a, 6), "b": round(b, 6)}


def aplicar_platt(p: float, coefs: dict | None) -> float:
    """Aplica calibração Platt a uma probabilidade. Sem coefs → passthrough."""
    if coefs is None or p <= 0 or p >= 1:
        return p
    return _sigmoid(_logit(p), coefs["a"], coefs["b"])


def salvar_platt(liga_key: str, coefs: dict) -> None:
    p = _CACHE_DIR / f"platt_{liga_key}.json"
    p.write_text(json.dumps(coefs), encoding="utf-8")


def carregar_platt(liga_key: str) -> dict | None:
    p = _CACHE_DIR / f"platt_{liga_key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


# ── CLI de diagnóstico ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Calibração Dixon-Coles (rho MLE) ===\n")
    # Simula jogos com gols reais para testar o MLE
    import random
    random.seed(42)

    def _sim(lm, lv, n=200):
        """Simula n jogos com Poisson(lm, lv) e rho corrigido."""
        jogos = []
        for _ in range(n):
            gm = sum(1 for _ in range(20) if random.random() < lm / 20)
            gv = sum(1 for _ in range(20) if random.random() < lv / 20)
            jogos.append((lm, lv, gm, gv))
        return jogos

    for lm, lv in [(1.5, 1.1), (1.8, 1.0), (1.3, 1.3)]:
        jogos = _sim(lm, lv, 300)
        rho = mle_rho(jogos)
        print(f"  λ=({lm},{lv})  rho_estimado={rho:+.4f}  (esperado ≈ −0.06)")

    print("\n=== Platt Scaling (necessita ≥50 jogos conferidos) ===")
    print(f"  Mínimo para calibrar: {_MIN_JOGOS_CALIBRACAO} jogos")
