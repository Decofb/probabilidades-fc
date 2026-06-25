"""
Gera o site (index.html) com os cards de cada jogo e as probabilidades.
Site estatico: abre direto no navegador e pode ser publicado de graca.
"""

from __future__ import annotations

import html
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
    """
    Destaca o mercado AFIRMATIVO de maior probabilidade. De proposito NAO inclui
    mercados complementares triviais (Under 2.5, Ambas NAO marcam), que ficam
    quase sempre ~100% em jogos de placar baixo e nao representam edge nenhum.
    """
    candidatos = [
        (f"Vitória {j.mandante}", m.pct(m.vitoria_mandante)),
        ("Empate", m.pct(m.empate)),
        (f"Vitória {j.visitante}", m.pct(m.vitoria_visitante)),
        ("Over 2.5 gols", m.pct(m.over_25)),
        ("Ambas marcam", m.pct(m.ambas_marcam)),
    ]
    return max(candidatos, key=lambda c: c[1])


def card_jogo(j: Jogo, m: ResultadoMercados, ha: dict | None, linha_ha: float,
              liga_cfg: dict | None = None) -> str:
    aposta, conf = _melhor_aposta(j, m)
    aposta = html.escape(aposta)
    nome_m = html.escape(j.mandante)
    nome_v = html.escape(j.visitante)
    cor_conf = _cor_por_pct(conf)
    selo = ""
    if liga_cfg:
        emoji = liga_cfg.get("emoji", "")
        nome_liga = html.escape(liga_cfg.get("nome", ""))
        selo = f'<span class="liga">{emoji} {nome_liga}</span>'

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

    html_cart = ""
    if m.cartoes:
        linhas = ""
        for chave, val in m.cartoes.items():
            linha = chave.replace("over_", "").replace("_", ".")
            linhas += _barra(f"+{linha} cartões", round(val * 100), "#f59e0b")
        html_cart = f"""
        <div class="grupo">
          <div class="grupo-tit">🟨 Cartões <span class="esp">~{m.cartoes_esperados:.1f} no jogo</span></div>
          {linhas}
        </div>"""

    html_ha = ""
    if ha:
        sinal = "+" if linha_ha >= 0 else ""
        html_ha = f"""
        <div class="grupo">
          <div class="grupo-tit">⚖️ Handicap Asiático</div>
          {_barra(f"{nome_m} ({sinal}{linha_ha})", round(ha['mandante']*100), _cor_por_pct(round(ha['mandante']*100)))}
          {_barra(f"{nome_v} ({'-' if linha_ha>=0 else '+'}{abs(linha_ha)})", round(ha['visitante']*100), _cor_por_pct(round(ha['visitante']*100)))}
        </div>"""

    rodada = f'<span class="rodada">{html.escape(j.rodada)}</span>' if j.rodada else ""
    hora_safe = html.escape(j.hora or "")

    return f"""
    <div class="card">
      <div class="topo">
        <div class="confronto">
          <span class="time">{nome_m}</span>
          <span class="x">×</span>
          <span class="time">{nome_v}</span>
        </div>
        <div class="meta">{selo} {hora_safe} {rodada}</div>
      </div>

      <div class="destaque" style="border-color:{cor_conf}">
        <span class="destaque-lbl">Maior probabilidade</span>
        <span class="destaque-val">{aposta}</span>
        <span class="destaque-pct" style="color:{cor_conf}">{conf}%</span>
      </div>

      <div class="grupo">
        <div class="grupo-tit">🏆 Resultado (1X2)</div>
        {_barra(nome_m, pm, _cor_por_pct(pm))}
        {_barra("Empate", pe, _cor_por_pct(pe))}
        {_barra(nome_v, pv, _cor_por_pct(pv))}
      </div>

      <div class="grupo">
        <div class="grupo-tit">⚽ Gols</div>
        {_barra("+0.5 gols", m.pct(m.over_05), _cor_por_pct(m.pct(m.over_05)))}
        {_barra("+1.5 gols", m.pct(m.over_15), _cor_por_pct(m.pct(m.over_15)))}
        {_barra("+2.5 gols", m.pct(m.over_25), _cor_por_pct(m.pct(m.over_25)))}
        {_barra("Ambas marcam", m.pct(m.ambas_marcam), _cor_por_pct(m.pct(m.ambas_marcam)))}
        <div class="placar">Placar mais provável: <b>{m.placar_provavel[0]}–{m.placar_provavel[1]}</b> ({m.pct(m.prob_placar_provavel)}%) · gols esperados {m.gols_esperados_mandante:.1f}–{m.gols_esperados_visitante:.1f}</div>
      </div>

      {html_ha}
      {html_esc}
      {html_cart}
    </div>"""


def gerar_site(grupos_data: list[tuple[str, str, list[str]]], data_geracao: str,
               dados_backup: bool = False) -> Path:
    """
    grupos_data = lista ordenada de (rotulo, subtitulo, [html_card, ...]).
    Cada grupo e uma DATA (ex: rotulo='HOJE', subtitulo='quinta, 25/06').
    data_geracao = hora da ULTIMA COLETA COM SUCESSO (nao a hora do processo).
    dados_backup = True quando a coleta de hoje falhou e estamos servindo CSV antigo.
    """
    secoes = ""
    for rotulo, subtitulo, cards in grupos_data:
        if not cards:
            continue
        cls = "dia" if rotulo in ("HOJE", "AMANHÃ") else "dia fut"
        secoes += f"""
      <section>
        <h2><span class="{cls}">{rotulo}</span> <span class="dia-sub">{subtitulo}</span>
            <span class="qtd">{len(cards)} jogo{'s' if len(cards) != 1 else ''}</span></h2>
        <div class="grade">{''.join(cards)}</div>
      </section>"""

    if not secoes:
        secoes = '<p class="vazio">Nenhum jogo para hoje ou amanhã no momento.</p>'

    # marca: usa o logo do Canva se ja foi exportado para docs/logo.png; senao, wordmark
    if (PASTA_SITE / "logo.png").exists():
        marca = '<img class="logo-full" src="logo.png" alt="Probabilidades FC">'
    else:
        marca = '<h1><span class="ball">⚽</span> Probabilidades FC</h1>'

    banner = ""
    if dados_backup:
        banner = ('<div style="max-width:920px;margin:14px auto 0;padding:10px 14px;'
                  'font-size:13px;color:#fff;background:#b91c1c;border-radius:10px;text-align:center">'
                  '⚠️ DADOS DE BACKUP — a coleta de hoje não rodou; mostrando a última atualização bem-sucedida.</div>')

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>⚽ Probabilidades FC</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');
  :root {{
    color-scheme: dark;
    --bg:#070b12; --panel:#0f1828; --panel-2:#0c1422;
    --line:#1d2940; --line-soft:#16223a;
    --txt:#e9eef7; --muted:#90a0b8; --faint:#5d6b82;
    --emerald:#34d399; --emerald-2:#10b981; --gold:#e8c879;
    --radius:16px; --shadow:0 14px 34px -16px rgba(0,0,0,.75);
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:var(--txt);
    font-family:'Inter',-apple-system,Segoe UI,Roboto,sans-serif;
    background:
      radial-gradient(1100px 560px at 50% -220px, #13203a 0%, transparent 60%),
      radial-gradient(760px 460px at 100% 0, #0f241e 0%, transparent 55%),
      var(--bg);
    background-attachment:fixed; -webkit-font-smoothing:antialiased; }}
  ::selection {{ background:var(--emerald-2); color:#04130d; }}

  header {{ position:relative; text-align:center; padding:36px 16px 22px; overflow:hidden;
            border-bottom:1px solid var(--line-soft); }}
  header::after {{ content:""; position:absolute; left:0; right:0; bottom:-1px; height:1px;
            background:linear-gradient(90deg,transparent,var(--emerald),transparent); opacity:.55; }}
  .brand {{ display:flex; align-items:center; justify-content:center; gap:12px; }}
  .brand .logo-full {{ height:74px; width:auto; max-width:88vw; object-fit:contain;
            filter:drop-shadow(0 6px 20px rgba(52,211,153,.22)); }}
  .brand h1 {{ margin:0; font-family:'Sora',sans-serif; font-weight:800; font-size:30px;
            letter-spacing:-.5px; background:linear-gradient(180deg,#ffffff,#b9d7cd);
            -webkit-background-clip:text; background-clip:text; color:transparent; }}
  .brand .ball {{ -webkit-text-fill-color:initial; }}
  header .sub {{ color:var(--muted); font-size:13px; margin-top:10px; letter-spacing:.2px; }}
  header .ts {{ color:var(--faint); font-size:11px; margin-top:4px; font-variant-numeric:tabular-nums; }}
  header .ts b {{ color:var(--emerald); font-weight:600; }}

  .aviso {{ max-width:940px; margin:18px auto 0; padding:11px 16px; font-size:12px;
            color:#f4d58b; background:rgba(232,200,121,.07);
            border:1px solid rgba(232,200,121,.18); border-radius:12px; line-height:1.55; }}

  main {{ max-width:940px; margin:0 auto; padding:12px 16px 72px; }}

  section h2 {{ display:flex; align-items:center; gap:12px; margin:30px 0 14px;
            position:sticky; top:0; z-index:5; padding:12px 2px;
            background:linear-gradient(180deg,var(--bg) 62%,transparent); }}
  .dia {{ font-family:'Sora',sans-serif; font-size:12px; font-weight:700; letter-spacing:1.4px;
            text-transform:uppercase; color:#04130d; background:var(--emerald);
            padding:5px 12px; border-radius:999px; }}
  .dia.fut {{ color:var(--emerald); background:transparent; border:1px solid var(--line); }}
  .dia-sub {{ font-size:13px; color:var(--muted); font-weight:500; }}
  .qtd {{ margin-left:auto; font-size:11px; color:var(--faint); letter-spacing:.3px; }}

  .grade {{ display:grid; grid-template-columns:1fr; gap:16px; }}
  @media(min-width:780px) {{ .grade {{ grid-template-columns:1fr 1fr; }} }}

  .card {{ position:relative; padding:16px 16px 8px;
            background:linear-gradient(180deg,var(--panel),var(--panel-2));
            border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow);
            transition:transform .18s ease, border-color .18s ease; }}
  .card::before {{ content:""; position:absolute; left:0; right:0; top:0; height:1px;
            border-radius:var(--radius) var(--radius) 0 0;
            background:linear-gradient(90deg,transparent,rgba(255,255,255,.10),transparent); }}
  .card:hover {{ transform:translateY(-2px); border-color:#2a3a59; }}
  .topo {{ margin-bottom:4px; }}
  .confronto {{ font-family:'Sora',sans-serif; font-size:17px; font-weight:700; letter-spacing:-.2px;
            display:flex; gap:9px; align-items:center; flex-wrap:wrap; }}
  .confronto .x {{ color:var(--faint); font-weight:400; }}
  .meta {{ color:var(--muted); font-size:12px; margin-top:6px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .liga {{ background:rgba(255,255,255,.05); color:#c6d2e4; padding:2px 9px; border-radius:999px;
            font-weight:600; font-size:11px; border:1px solid var(--line-soft); }}
  .rodada {{ color:var(--faint); }}

  .destaque {{ display:flex; align-items:center; gap:10px; margin:13px 0; padding:11px 13px;
            background:linear-gradient(90deg,rgba(52,211,153,.09),transparent);
            border:1px solid var(--line); border-left-width:3px; border-radius:12px; }}
  .destaque-lbl {{ font-size:9px; text-transform:uppercase; color:var(--muted); letter-spacing:1px; }}
  .destaque-val {{ font-weight:600; font-size:14px; }}
  .destaque-pct {{ margin-left:auto; font-family:'Sora',sans-serif; font-size:22px; font-weight:800;
            font-variant-numeric:tabular-nums; }}

  .grupo {{ margin-top:14px; }}
  .grupo-tit {{ font-size:11px; color:#aab8cd; margin-bottom:9px; font-weight:600;
            text-transform:uppercase; letter-spacing:.7px; }}
  .grupo-tit .esp {{ color:var(--faint); font-weight:400; font-size:11px; text-transform:none; letter-spacing:0; }}
  .linha {{ display:flex; align-items:center; gap:10px; margin:6px 0; }}
  .lbl {{ width:34%; font-size:12.5px; color:#c4d0e2; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .bar {{ flex:1; height:8px; background:var(--line-soft); border-radius:999px; overflow:hidden;
            box-shadow:inset 0 1px 2px rgba(0,0,0,.4); }}
  .fill {{ height:100%; border-radius:999px; position:relative; }}
  .fill::after {{ content:""; position:absolute; inset:0;
            background:linear-gradient(180deg,rgba(255,255,255,.28),transparent 65%); }}
  .val {{ width:40px; text-align:right; font-size:12.5px; font-weight:600;
            font-variant-numeric:tabular-nums; color:#dbe4f1; }}
  .placar {{ font-size:11px; color:var(--muted); margin-top:10px; padding-top:9px;
            border-top:1px solid var(--line-soft); }}
  .placar b {{ color:var(--txt); }}

  .vazio {{ text-align:center; color:var(--muted); margin-top:50px; }}
  footer {{ text-align:center; color:var(--faint); font-size:11px; padding:26px 16px; }}
  footer b {{ color:var(--emerald); font-weight:600; }}
</style>
</head>
<body>
  <header>
    <div class="brand">{marca}</div>
    <div class="sub">Jogos de hoje e amanhã · probabilidades por estatística · sem odds</div>
    <div class="ts">Última coleta OK: <b>{data_geracao}</b></div>
    <div class="aviso">⚠️ As porcentagens são <b>estimativas estatísticas</b> baseadas no histórico recente
      (gols, xG e escanteios). Não são garantia de resultado — futebol tem zebra. Use como apoio, com responsabilidade.</div>
    {banner}
  </header>
  <main>{secoes}</main>
  <footer><b>Probabilidades FC</b> · modelo Poisson + Dixon-Coles · dados do 365scores · atualiza sozinho todo dia</footer>
</body>
</html>"""

    destino = PASTA_SITE / "index.html"
    destino.write_text(html, encoding="utf-8")
    return destino
