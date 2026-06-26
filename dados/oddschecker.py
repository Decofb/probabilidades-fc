"""
ODDSCHECKER  ->  odds do mercado para os jogos das nossas ligas.

Usa Playwright (headless Chrome) para carregar as páginas JS do Oddschecker
e extrai as melhores odds disponíveis (as que aparecem no comparador).

Saída de buscar_mercado():
    {id_jogo: MercadoOdds(odd_m, odd_e, odd_v, pm, pe, pv)}
    onde pm/pe/pv = probabilidades implícitas SEM margem (vig normalizada),
    pronta para comparar com o nosso modelo Poisson.

Cache: salvo em dados/cache_mercado.json por até CACHE_HORAS horas.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from unidecode import unidecode

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PASTA_DADOS

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Constantes ──────────────────────────────────────────────────────────────

URLS = {
    "copa_mundo":    "https://www.oddschecker.com/br/futebol/internacional/copa-do-mundo-fifa",
    "brasileirao_a": "https://www.oddschecker.com/br/futebol/brasil/serie-a",
    "brasileirao_b": "https://www.oddschecker.com/br/futebol/brasil/serie-b",
}

CACHE_PATH = PASTA_DADOS / "cache_mercado.json"
CACHE_HORAS = 6     # reutiliza cache se tiver menos de 6h

MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

SKIP_LINES = {"mandante", "empate", "visitante", "mais odds", "ver todos os jogos"}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class MercadoOdds:
    odd_m: float   # melhor odd mandante (decimal)
    odd_e: float   # melhor odd empate
    odd_v: float   # melhor odd visitante
    pm: float      # prob implícita mandante (sem vig)
    pe: float      # prob implícita empate
    pv: float      # prob implícita visitante
    margem: float  # margem total da casa (ex: 0.04 = 4%)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


def _is_hora(s: str) -> bool:
    return bool(re.match(r"^\d{1,2}:\d{2}\s*(?:AM|PM)$", s.strip(), re.IGNORECASE))


def _is_odd(s: str) -> bool:
    try:
        v = float(s.strip().replace(",", "."))
        return 1.01 <= v <= 200.0
    except ValueError:
        return False


def _parse_data_header(linha: str, ano: int) -> Optional[date]:
    """Converte cabeçalho de data do Oddschecker em date."""
    l = linha.strip().upper()
    if l == "HOJE":
        return date.today()
    if l == "AMANHÃ" or l == "AMANHA":
        return date.today() + timedelta(days=1)
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)", linha.lower())
    if m:
        dia = int(m.group(1))
        mes = MESES_PT.get(m.group(2).strip())
        if mes:
            try:
                return date(ano, mes, dia)
            except ValueError:
                pass
    return None


def _implied_probs(odd_m: float, odd_e: float, odd_v: float):
    """Probabilidades implícitas normalizadas (vig removida)."""
    raw_m = 1 / odd_m
    raw_e = 1 / odd_e
    raw_v = 1 / odd_v
    total = raw_m + raw_e + raw_v
    margem = total - 1.0
    return raw_m / total, raw_e / total, raw_v / total, round(margem, 4)


def _id_jogo(data_str: str, mandante: str, visitante: str) -> str:
    return f"{data_str}|{_norm(mandante)}|{_norm(visitante)}"


# ── Parser do texto da página ─────────────────────────────────────────────

def _parsear_texto(texto: str, ano: int) -> dict[str, MercadoOdds]:
    """
    Parseia o texto extraído da página do Oddschecker.
    Retorna {id_jogo: MercadoOdds}.
    """
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]

    resultado = {}
    data_atual: Optional[date] = None
    estado = "aguardando_hora"
    mandante = visitante = ""
    odd_m = odd_e = 0.0

    for linha in linhas:
        l_low = _norm(linha)

        # Pula linhas sempre ignoradas
        if l_low in SKIP_LINES:
            continue

        # Cabeçalho de data?
        dt = _parse_data_header(linha, ano)
        if dt is not None:
            data_atual = dt
            estado = "aguardando_hora"
            continue

        if estado == "aguardando_hora":
            if _is_hora(linha):
                estado = "esperando_mandante"
            # Ignora títulos de liga e outros cabeçalhos

        elif estado == "esperando_mandante":
            if _is_hora(linha):
                # Resetou — outra hora
                estado = "esperando_mandante"
            elif not _is_odd(linha):
                mandante = linha
                estado = "esperando_visitante"

        elif estado == "esperando_visitante":
            if _is_odd(linha):
                # Odd chegou antes do visitante → reset
                estado = "aguardando_hora"
            else:
                visitante = linha
                estado = "esperando_odd_m"

        elif estado == "esperando_odd_m":
            if _is_odd(linha):
                odd_m = float(linha.replace(",", "."))
                estado = "esperando_odd_e"
            else:
                estado = "aguardando_hora"

        elif estado == "esperando_odd_e":
            if _is_odd(linha):
                odd_e = float(linha.replace(",", "."))
                estado = "esperando_odd_v"
            else:
                estado = "aguardando_hora"

        elif estado == "esperando_odd_v":
            if _is_odd(linha) and data_atual is not None:
                odd_v = float(linha.replace(",", "."))
                pm, pe, pv, mg = _implied_probs(odd_m, odd_e, odd_v)
                key = _id_jogo(data_atual.isoformat(), mandante, visitante)
                resultado[key] = MercadoOdds(
                    odd_m=round(odd_m, 3), odd_e=round(odd_e, 3), odd_v=round(odd_v, 3),
                    pm=round(pm, 4), pe=round(pe, 4), pv=round(pv, 4),
                    margem=mg,
                )
            estado = "aguardando_hora"

    return resultado


# ── Playwright (headless) ────────────────────────────────────────────────────

def _fetch_texto_playwright(url: str) -> str:
    """Abre a URL no Chromium headless e retorna o texto do <article> principal."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Aguarda o container de jogos aparecer
            page.wait_for_selector("main article", timeout=15_000)
            texto = page.locator("main article").first.inner_text()
        except PWTimeout:
            texto = page.locator("body").inner_text()
        finally:
            browser.close()

    return texto


# ── Cache ────────────────────────────────────────────────────────────────────

def _carregar_cache() -> Optional[dict]:
    if not CACHE_PATH.exists():
        return None
    try:
        d = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        gerado = datetime.fromisoformat(d.get("gerado_em", "2000-01-01"))
        if (datetime.now() - gerado).total_seconds() < CACHE_HORAS * 3600:
            return d.get("dados", {})
    except Exception:
        pass
    return None


def _salvar_cache(dados: dict) -> None:
    payload = {
        "gerado_em": datetime.now().isoformat(),
        "dados": dados,
    }
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8")


# ── Interface pública ─────────────────────────────────────────────────────────

def buscar_mercado(ligas: list[str] | None = None,
                   usar_cache: bool = True) -> dict[str, MercadoOdds]:
    """
    Busca as odds do Oddschecker para todas as ligas especificadas
    e devolve {id_jogo: MercadoOdds}.

    ligas: lista de chaves de liga (None = todas: copa+a+b)
    usar_cache: se True, usa dados em cache < CACHE_HORAS horas
    """
    if ligas is None:
        ligas = list(URLS.keys())

    # Tenta cache
    if usar_cache:
        cached = _carregar_cache()
        if cached is not None:
            print("  [oddschecker] usando cache")
            return {k: MercadoOdds(**v) for k, v in cached.items()}

    ano = date.today().year
    resultado: dict[str, MercadoOdds] = {}

    for liga in ligas:
        url = URLS.get(liga)
        if not url:
            continue
        print(f"  [oddschecker] {liga}... ", end="", flush=True)
        try:
            texto = _fetch_texto_playwright(url)
            parcial = _parsear_texto(texto, ano)
            resultado.update(parcial)
            print(f"{len(parcial)} jogos")
        except Exception as e:
            print(f"erro ({type(e).__name__})")

    if resultado:
        _salvar_cache({k: asdict(v) for k, v in resultado.items()})

    return resultado


def lookup_mercado(data: str, mandante: str, visitante: str,
                   mercado: dict[str, MercadoOdds]) -> Optional[MercadoOdds]:
    """
    Busca as odds do mercado com fuzzy match nos nomes (cobre variações
    de acentuação e abreviação entre Oddschecker e 365scores).
    """
    import difflib

    k = _id_jogo(data, mandante, visitante)
    if k in mercado:
        return mercado[k]

    alvo_m = _norm(mandante)
    alvo_v = _norm(visitante)
    candidatos = [c for c in mercado if c.startswith(data + "|")]

    for c in candidatos:
        _, nm, nv = c.split("|", 2)
        sim_m = difflib.SequenceMatcher(None, alvo_m, nm).ratio()
        sim_v = difflib.SequenceMatcher(None, alvo_v, nv).ratio()
        if sim_m >= 0.75 and sim_v >= 0.75:
            return mercado[c]

    return None


def delta_mercado(p_modelo: float, p_mercado: float) -> float:
    """
    Diferença entre probabilidade do modelo e do mercado.
    Positivo = modelo vê mais chance que o mercado (valor potencial).
    """
    return round(p_modelo - p_mercado, 4)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Oddschecker — odds do mercado ===\n")
    m = buscar_mercado(usar_cache=False)
    for k, v in sorted(m.items()):
        data, mand, vis = k.split("|", 2)
        print(f"  {data}  {mand} vs {vis}")
        print(f"    odds: {v.odd_m} / {v.odd_e} / {v.odd_v}  "
              f"(margem {v.margem:.1%})")
        print(f"    impl: M {v.pm:.1%}  E {v.pe:.1%}  V {v.pv:.1%}")
    print(f"\n{len(m)} jogos encontrados.")
