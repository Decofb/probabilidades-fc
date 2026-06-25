"""
Gera o site (index.html) com os cards de cada jogo e as probabilidades.
Site estatico: abre direto no navegador e pode ser publicado de graca.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import PASTA_SITE, LIGAS  # noqa: E402
from dados.jogos import Jogo  # noqa: E402
from motor.poisson import ResultadoMercados  # noqa: E402


def _barra(label: str, pct: int, cor: str = "#22c55e") -> str:
    return f"""
      <div class="linha">
        <span class="lbl">{label}</span>
        <div class="bar"><div class="fill" style="width:{pct}%;background:{cor}"></div></div>
        <span class="val">{pct}%</span>
      </div>"""


def _cor_por_pct(pct: int) -> str:
    if pct >= 70:
        return "#22c55e"   # verde forte
    if pct >= 55:
        return "#84cc16"   # verde claro
    if pct >= 45:
        return "#eab308"   # amarelo
    if pct >= 30:
        return "#f97316"   # laranja
    return "#ef4444"       # vermelho


def _melhor_aposta(j: Jogo, m: ResultadoMercados) -> tuple[str, int]:
    """Escolhe o mercado de maior confianca (maior %) entre os principais."""
    candidatos = [
        (f"Vitória {j.mandante}", m.pct(m.vitoria_mandante)),
        (f"Vitória {j.visitante}", m.pct(m.vitoria_visitante)),
        ("Over 2.5 gols", m.pct(m.over_25)),
        ("Under 2.5 gols", 100 - m.pct(m.over_25)),
        ("Over 1.5 gols", m.pct(m.over_15)),
        ("Ambas marcam", m.pct(m.ambas_marcam)),
        ("Ambas NÃO marcam", 100 - m.pct(m.ambas_marcam)),
    ]
    return max(candidatos, key=lambda c: c[1])


def card_jogo(j: Jogo, m: ResultadoMercados, ha: dict | None, linha_ha: float) -> str:
    aposta, conf = _melhor_aposta(j, m)
    cor_conf = _cor_por_pct(conf)

    # 1X2
    pm, pe, pv = m.pct(m.vitoria_mandante), m.pct(m.empate), m.pct(m.vitoria_visitante)

    html_esc = ""
    if m.escanteios:
        linhas = ""
        for chave, val in m.escanteios.items():
            linha = chave.replace("over_", "").replace("_", ".")
            linhas += _barra(f"+{linha} escanteios", round(val * 100), "#06b6d4")
        html_esc = f"""
        <div class="grupo">
          <div class="grupo-tit">⛳ Escanteios <span class="esp">~{m.escanteios_esperados:.1f} no jogo</span></div>
          {linhas}
        </div>"""

    html_ha = ""
    if ha:
        sinal = "+" if linha_ha >= 0 else ""
        html_ha = f"""
        <div class="grupo">
          <div class="grupo-tit">⚖️ Handicap Asiático</div>
          {_barra(f"{j.mandante} ({sinal}{linha_ha})", round(ha['mandante']*100), _cor_por_pct(round(ha['mandante']*100)))}
          {_barra(f"{j.visitante} ({'-' if linha_ha>=0 else '+'}{abs(linha_ha)})", round(ha['visitante']*100), _cor_por_pct(round(ha['visitante']*100)))}
        </div>"""

    rodada = f'<span class="rodada">{j.rodada}</span>' if j.rodada else ""

    return f"""
    <div class="card">
      <div class="topo">
        <div class="confronto">
          <span class="time">{j.mandante}</span>
          <span class="x">×</span>
          <span class="time">{j.visitante}</span>
        </div>
        <div class="meta">{j.data} · {j.hora} {rodada}</div>
      </div>

      <div class="destaque" style="border-color:{cor_conf}">
        <span class="destaque-lbl">Maior probabilidade</span>
        <span class="destaque-val">{aposta}</span>
        <span class="destaque-pct" style="color:{cor_conf}">{conf}%</span>
      </div>

      <div class="grupo">
        <div class="grupo-tit">🏆 Resultado (1X2)</div>
        {_barra(j.mandante, pm, _cor_por_pct(pm))}
        {_barra("Empate", pe, _cor_por_pct(pe))}
        {_barra(j.visitante, pv, _cor_por_pct(pv))}
      </div>

      <div class="grupo">
        <div class="grupo-tit">⚽ Gols</div>
        {_barra("Over 1.5", m.pct(m.over_15), _cor_por_pct(m.pct(m.over_15)))}
        {_barra("Over 2.5", m.pct(m.over_25), _cor_por_pct(m.pct(m.over_25)))}
        {_barra("Ambas marcam", m.pct(m.ambas_marcam), _cor_por_pct(m.pct(m.ambas_marcam)))}
        <div class="placar">Placar mais provável: <b>{m.placar_provavel[0]}–{m.placar_provavel[1]}</b> ({m.pct(m.prob_placar_provavel)}%) · gols esperados {m.gols_esperados_mandante:.1f}–{m.gols_esperados_visitante:.1f}</div>
      </div>

      {html_ha}
      {html_esc}
    </div>"""


def gerar_site(blocos: dict[str, list[str]], data_geracao: str) -> Path:
    """blocos = {liga_key: [html_card, ...]}"""
    secoes = ""
    for liga_key, cards in blocos.items():
        if not cards:
            continue
        cfg = LIGAS[liga_key]
        secoes += f"""
      <section>
        <h2>{cfg['emoji']} {cfg['nome']}</h2>
        <div class="grade">{''.join(cards)}</div>
      </section>"""

    if not secoes:
        secoes = '<p class="vazio">Nenhum jogo carregado. Rode <code>python atualizar.py</code> com a tabela de jogos preenchida.</p>'

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>⚽ Probabilidades FC</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0b0f17; color:#e5e7eb;
         font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  header {{ padding:22px 16px 14px; text-align:center;
            background:linear-gradient(180deg,#111827,#0b0f17); border-bottom:1px solid #1f2937; }}
  header h1 {{ margin:0; font-size:24px; letter-spacing:.5px; }}
  header .sub {{ color:#9ca3af; font-size:13px; margin-top:4px; }}
  .aviso {{ max-width:920px; margin:14px auto 0; padding:10px 14px; font-size:12px;
            color:#fbbf24; background:#1f2937; border-radius:10px; line-height:1.5; }}
  main {{ max-width:920px; margin:0 auto; padding:18px 14px 60px; }}
  section h2 {{ font-size:16px; margin:24px 0 12px; color:#d1d5db;
                border-left:3px solid #22c55e; padding-left:10px; }}
  .grade {{ display:grid; grid-template-columns:1fr; gap:14px; }}
  @media(min-width:760px) {{ .grade {{ grid-template-columns:1fr 1fr; }} }}
  .card {{ background:#111827; border:1px solid #1f2937; border-radius:14px; padding:14px; }}
  .topo {{ margin-bottom:10px; }}
  .confronto {{ font-size:17px; font-weight:600; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  .confronto .x {{ color:#6b7280; font-weight:400; }}
  .meta {{ color:#9ca3af; font-size:12px; margin-top:3px; }}
  .rodada {{ background:#374151; padding:1px 7px; border-radius:6px; margin-left:6px; }}
  .destaque {{ display:flex; align-items:center; gap:8px; margin:10px 0;
               padding:9px 12px; background:#0b0f17; border:1px solid; border-radius:10px; }}
  .destaque-lbl {{ font-size:10px; text-transform:uppercase; color:#9ca3af; letter-spacing:.5px; }}
  .destaque-val {{ font-weight:600; font-size:14px; }}
  .destaque-pct {{ margin-left:auto; font-size:20px; font-weight:700; }}
  .grupo {{ margin-top:12px; }}
  .grupo-tit {{ font-size:13px; color:#cbd5e1; margin-bottom:7px; font-weight:600; }}
  .grupo-tit .esp {{ color:#6b7280; font-weight:400; font-size:11px; }}
  .linha {{ display:flex; align-items:center; gap:8px; margin:5px 0; }}
  .lbl {{ width:34%; font-size:12px; color:#d1d5db; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .bar {{ flex:1; height:9px; background:#1f2937; border-radius:6px; overflow:hidden; }}
  .fill {{ height:100%; border-radius:6px; }}
  .val {{ width:38px; text-align:right; font-size:12px; font-variant-numeric:tabular-nums; }}
  .placar {{ font-size:11px; color:#9ca3af; margin-top:8px; }}
  .vazio {{ text-align:center; color:#9ca3af; margin-top:40px; }}
  footer {{ text-align:center; color:#6b7280; font-size:11px; padding:20px; }}
</style>
</head>
<body>
  <header>
    <h1>⚽ Probabilidades FC</h1>
    <div class="sub">Probabilidades por estatística · sem odds · {data_geracao}</div>
    <div class="aviso">⚠️ As porcentagens são <b>estimativas estatísticas</b> baseadas no histórico recente
      (gols, xG e escanteios). Não são garantia de resultado — futebol tem zebra. Use como apoio, com responsabilidade.</div>
  </header>
  <main>{secoes}</main>
  <footer>Gerado por Probabilidades FC · modelo Poisson · dados FBref + tabela FIFA/ge.globo</footer>
</body>
</html>"""

    destino = PASTA_SITE / "index.html"
    destino.write_text(html, encoding="utf-8")
    return destino
