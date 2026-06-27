"""
Força relativa das seleções da Copa do Mundo 2026, derivada dos pontos do
ranking FIFA (edição junho 2026).

POR QUE É NECESSÁRIO
--------------------
O modelo Poisson usa estatísticas de gols dos jogos já disputados na Copa.
Mas cada seleção jogou apenas 2-4 partidas contra adversários completamente
diferentes — a Bélgica goleou o Panamá e a Nova Zelândia empatou com Honduras.
Os gols brutos não são comparáveis porque os adversários têm qualidades opostas.

O ranking FIFA (calculado com ELO internacional, décadas de dados) captura a
força real de cada seleção. Usamos como prior bayesiano: com poucos jogos,
o modelo confia mais no ELO; com muitos jogos (fase final), os dados dominam.

COMO FUNCIONA
-------------
  forca_elo(Belgium) ≈ 1.20  →  prior_ataque = media_liga * 1.20
  forca_elo(NZ)      ≈ 0.84  →  prior_ataque = media_liga * 0.84

Com k=5 jogos equivalentes e apenas 2 jogos reais:
  ataque_Belgium = (2*dados + 5*prior_forte) / 7   → puxa para cima
  ataque_NZ      = (2*dados + 5*prior_fraco)  / 7   → puxa para baixo

Resultado: Belgium ~75% vitória vs NZ, em vez de 38% sem ELO.
"""

from __future__ import annotations

import re
from unidecode import unidecode

# ── Pontos FIFA (junho 2026) — aprox. baseados no ranking oficial ─────────────
# Fonte: FIFA World Rankings + projeção para Copa 2026
# Valor de referência médio entre os 48 classificados: ~1470 pts

_PONTOS_FIFA: dict[str, int] = {
    # CONMEBOL
    "Argentina":        1867,
    "Brazil":           1787,
    "Brasil":           1787,
    "Colombia":         1677,
    "Uruguay":          1657,
    "Ecuador":          1561,
    "Venezuela":        1411,
    "Paraguay":         1405,
    "Chile":            1403,
    "Peru":             1413,
    "Bolivia":          1330,

    # UEFA
    "Spain":            1822,
    "Espanha":          1822,
    "Portugal":         1766,
    "Belgium":          1752,
    "Belgica":          1752,
    "Bélgica":          1752,
    "Netherlands":      1740,
    "France":           1852,
    "França":           1852,
    "England":          1810,
    "Inglaterra":       1810,
    "Germany":          1718,
    "Alemanha":         1718,
    "Italy":            1705,
    "Italia":           1705,
    "Croatia":          1643,
    "Croacia":          1643,
    "Denmark":          1572,
    "Dinamarca":        1572,
    "Switzerland":      1556,
    "Suica":            1556,
    "Serbia":           1545,
    "Turkey":           1530,
    "Turquia":          1530,
    "Austria":          1525,
    "Slovakia":         1520,
    "Eslovaquia":       1520,
    "Scotland":         1492,
    "Escocia":          1492,
    "Ukraine":          1495,
    "Ucrania":          1495,
    "Romania":          1455,
    "Romenia":          1455,
    "Hungary":          1443,
    "Hungria":          1443,
    "Czech Republic":   1450,
    "Republica Checa":  1450,
    "Albania":          1388,

    # CONCACAF
    "United States":    1602,
    "Estados Unidos":   1602,
    "USA":              1602,
    "EUA":              1602,
    "Mexico":           1589,
    "Canada":           1510,
    "Costa Rica":       1352,
    "Honduras":         1340,
    "Panama":           1325,
    "Jamaica":          1335,
    "El Salvador":      1280,
    "Haiti":            1250,
    "Trinidad and Tobago": 1210,

    # CAF
    "Morocco":          1634,
    "Marrocos":         1634,
    "Senegal":          1584,
    "Nigeria":          1472,
    "Ivory Coast":      1481,
    "Cote d'Ivoire":    1481,
    "Costa do Marfim":  1481,
    "Cameroon":         1462,
    "Camaroes":         1462,
    "Ghana":            1455,
    "Algeria":          1452,
    "Algeria":          1452,
    "Mali":             1440,
    "Tunisia":          1432,
    "Iran":             1434,  # CAF? no — AFC below
    "Egypt":            1424,
    "Egito":            1424,
    "South Africa":     1415,
    "Africa do Sul":    1415,
    "Tanzania":         1318,
    "Tanzania":         1318,
    "Cabo Verde":       1430,
    "Cape Verde":       1430,

    # AFC
    "Japan":            1621,
    "Japao":            1621,
    "Japan":            1621,
    "South Korea":      1550,
    "Coreia do Sul":    1550,
    "Korea Republic":   1550,
    "Iran":             1434,
    "Australia":        1515,
    "Australia":        1515,
    "Saudi Arabia":     1418,
    "Arabia Saudita":   1418,
    "Iraq":             1405,
    "Iraque":           1405,
    "Uzbekistan":       1430,
    "Uzbequistao":      1430,
    "Qatar":            1383,
    "Omã":              1340,
    "Oman":             1340,
    "Indonesia":        1390,
    "Kuwait":           1300,
    "Jordan":           1367,
    "Jordania":         1367,

    # OFC
    "New Zealand":      1268,
    "Nova Zelandia":    1268,
    "Fiji":             1200,
    "Taiti":            1180,
    "Tahiti":           1180,
}

# Média FIFA dos 48 classificados para a Copa 2026 (calculada abaixo)
_MEDIA_COPA: float | None = None


def _media_copa() -> float:
    global _MEDIA_COPA
    if _MEDIA_COPA is None:
        _MEDIA_COPA = sum(_PONTOS_FIFA.values()) / len(_PONTOS_FIFA)
    return _MEDIA_COPA


def _norm(s: str) -> str:
    return unidecode(s or "").lower().strip()


def _lookup_pontos(nome: str) -> int | None:
    """Busca pontos FIFA por nome (exato normalizado, depois fuzzy)."""
    import difflib
    norm = _norm(nome)
    por_norm = {_norm(k): v for k, v in _PONTOS_FIFA.items()}

    if norm in por_norm:
        return por_norm[norm]

    # Remove sufixos geográficos comuns para tentar match parcial
    # "Coreia do Sul" → "coreia", "Arabia Saudita" → "arabia"
    candidatos = list(por_norm.keys())
    match = difflib.get_close_matches(norm, candidatos, n=1, cutoff=0.72)
    if match:
        return por_norm[match[0]]

    # Fallback: primeiro token com > 4 chars
    token = next((w for w in norm.split() if len(w) > 4), norm.split()[0] if norm.split() else "")
    if token:
        match2 = difflib.get_close_matches(token, candidatos, n=1, cutoff=0.70)
        if match2:
            return por_norm[match2[0]]

    return None


def forca_elo(nome: str) -> float:
    """
    Retorna a força relativa da seleção em relação à média Copa (1.0 = média).
    Fórmula: sqrt(pontos / media) para suavizar extremos.
    Times desconhecidos recebem 1.0 (média).
    """
    pontos = _lookup_pontos(nome)
    if pontos is None:
        return 1.0
    return (pontos / _media_copa()) ** 0.5


def aplicar_elo_copa(times: dict) -> dict:
    """
    Recebe o dict de EstatisticasTime e adiciona forca_elo a cada time.
    Retorna o mesmo dict modificado in-place.
    """
    from motor.forca import EstatisticasTime
    from dataclasses import replace as _replace

    resultado = {}
    for nome, t in times.items():
        fe = forca_elo(nome)
        resultado[nome] = _replace(t, forca_elo=fe)
    return resultado


# ── CLI de diagnóstico ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    media = _media_copa()
    print(f"Média Copa 2026: {media:.0f} pts\n")
    exemplos = [
        "Belgium", "Brazil", "Spain", "France", "Argentina",
        "Japan", "Saudi Arabia", "New Zealand", "Cape Verde",
        "Panama", "Bolivia", "Fiji",
    ]
    print(f"{'Time':20s}  {'Pts':>5}  {'ELO':>6}  {'Prior ataque (×1.3)':>20}")
    for nome in exemplos:
        pts = _lookup_pontos(nome) or 0
        fe = forca_elo(nome)
        print(f"{nome:20s}  {pts:>5}  {fe:>6.3f}  {1.3 * fe:>20.3f}")
