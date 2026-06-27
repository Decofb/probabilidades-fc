"""
ATUALIZAR.PY  -> o comando que voce roda todo dia.

  python atualizar.py            (busca tudo do 365scores e gera o site)
  python atualizar.py --offline  (usa so os CSVs salvos, nao acessa a internet)

Fluxo:
  1. Para cada liga, busca no 365scores:
       - estatisticas dos times (gols, xG, escanteios) dos ultimos ~45 dias
       - proximos jogos (proximos ~6 dias)
  2. Salva tudo em CSV (cache + backup).
  3. Calcula as probabilidades de cada jogo.
  4. Gera o site em site/index.html.

Se a internet/365scores falhar, usa automaticamente os CSVs ja salvos.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from unidecode import unidecode

from dataclasses import replace as _dc_replace

from config import LIGAS, PASTA_SITE, parametros_da_liga, janela_liga
from dados.scores365 import (COMPETICOES_365, coletar_estatisticas,
                             coletar_jogos_futuros, medias_liga)
from dados.desfalques import coletar_desfalques, desfalques_do_jogo
from dados.fifa_elo import aplicar_elo_copa
from dados.fonte import salvar_times_csv, carregar_times_csv
from dados.jogos import salvar_jogos_csv, carregar_jogos_csv
from dados.registro import registrar, id_jogo
from motor.forca import (EstatisticasTime,
                         gols_esperados, escanteios_esperados, cartoes_esperados)
from motor.poisson import calcular_mercados, handicap_asiatico
from site_gerador import (card_jogo, gerar_site, gerar_tendencias, card_dica,
                          gerar_dicas_html, card_historico, gerar_historico_html)

FUSO_BR = timezone(timedelta(hours=-3))
DIAS_FRENTE = 3       # foco em hoje e amanha (+1 de folga)


def normalizar(nome: str) -> str:
    return unidecode(nome).lower().strip()


def achar_time(nome: str, times: dict[str, EstatisticasTime]) -> EstatisticasTime | None:
    """
    Casa o nome do jogo com o nome do time nas estatisticas. Prioriza match
    EXATO normalizado. Para aproximacao, exige UNICIDADE: se mais de um time
    casa, devolve None e avisa (melhor pular do que usar o time errado, ex.:
    'America' casando America-MG vs America-RN, ou 'Atletico' MG/GO/PR).
    """
    import difflib

    alvo = normalizar(nome)
    por_norm = {normalizar(t.nome): t for t in times.values()}

    # 1) match exato normalizado
    if alvo in por_norm:
        return por_norm[alvo]

    # 2) match aproximado, mas SO se for unico (cutoff alto)
    candidatos = difflib.get_close_matches(alvo, list(por_norm), n=3, cutoff=0.82)
    if len(candidatos) == 1:
        return por_norm[candidatos[0]]
    if len(candidatos) > 1:
        print(f"  ! nome ambiguo '{nome}' casa {candidatos} — pulado por seguranca")
        return None
    return None


def arredondar_meio(x: float) -> float:
    return round(x * 2) / 2


def _cross_validar_flash(liga_key: str, times_365: dict) -> None:
    """Compara médias de gols 365scores vs Flashscore; loga divergências > 0.3 gols/jogo."""
    try:
        from dados.flashscore import coletar_estatisticas as flash_stats, comparar_com_365
        flash = flash_stats(liga_key)
        if not flash:
            return
        divs = comparar_com_365(flash, times_365, limiar_delta=0.3)
        if divs:
            print(f"  [Flash⚡365] {len(divs)} divergências de gols/jogo:")
            for d in divs[:4]:
                print(f"    {d['time_flash']}: GF {d['flash_gf']} vs {d['s365_gf']}  "
                      f"GS {d['flash_gs']} vs {d['s365_gs']}  "
                      f"(Δ {d['delta_gf']+d['delta_gs']:.2f})")
        else:
            print(f"  [Flash⚡365] gols convergentes nos {len(flash)} times")
    except Exception as e:
        print(f"  [Flash⚡365 falhou: {type(e).__name__}]")


def obter_dados(liga_key: str, offline: bool, hoje):
    """
    Devolve (times, jogos, online_ok). 'hoje' e um date em BRT (mesma referencia
    do filtro de exibicao). online_ok=True so se a coleta no 365scores funcionou.
    """
    comp = COMPETICOES_365.get(liga_key)
    if not offline and comp:
        # Janela cobre a temporada inteira a partir do INICIO_TEMPORADA
        d1, _ = janela_liga(liga_key, hoje_date=hoje)
        d2 = hoje.strftime("%d/%m/%Y")
        d_frente = (hoje + timedelta(days=DIAS_FRENTE)).strftime("%d/%m/%Y")
        try:
            times = coletar_estatisticas(comp, d1, d2)
            jogos = coletar_jogos_futuros(comp, liga_key, d2, d_frente)
            if times:
                salvar_times_csv(liga_key, times)
            if jogos:
                salvar_jogos_csv(liga_key, jogos)
            print(f"  [365scores OK] {len(times)} times · {len(jogos)} jogos futuros")
            _cross_validar_flash(liga_key, times)
            return times, jogos, True
        except Exception as e:
            print(f"  [365scores falhou: {type(e).__name__}] tentando Flashscore...")
            # Fallback: Flashscore fornece gols (sem xG/escanteios)
            try:
                from dados.flashscore import (coletar_estatisticas as flash_stats,
                                              coletar_jogos_futuros as flash_jogos)
                times = flash_stats(liga_key)
                jogos = flash_jogos(liga_key, liga_key)
                if times:
                    print(f"  [Flashscore fallback] {len(times)} times · {len(jogos)} jogos")
                    return times, jogos, False
            except Exception as e2:
                print(f"  [Flashscore fallback falhou: {type(e2).__name__}] usando CSV")

    times = carregar_times_csv(liga_key)
    jogos = carregar_jogos_csv(liga_key)
    print(f"  [CSV] {len(times)} times · {len(jogos)} jogos")
    return times, jogos, False


DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def rotulo_data(data_str: str, hoje):
    """Devolve (rotulo, subtitulo) p/ uma data AAAA-MM-DD. Ex: ('HOJE','quinta, 25/06')."""
    d = datetime.strptime(data_str, "%Y-%m-%d").date()
    delta = (d - hoje).days
    sub = f"{DIAS_SEMANA[d.weekday()]}, {d.strftime('%d/%m')}"
    if delta == 0:
        return "HOJE", sub
    if delta == 1:
        return "AMANHÃ", sub
    return sub.split(",")[0].capitalize(), d.strftime("%d/%m")


def rotulo_passado(data_str: str, hoje):
    """Rótulo para datas no passado: HOJE / ONTEM / dia da semana."""
    d = datetime.strptime(data_str, "%Y-%m-%d").date()
    delta = (hoje - d).days
    sub = f"{DIAS_SEMANA[d.weekday()]}, {d.strftime('%d/%m')}"
    if delta == 0:
        return "HOJE", sub
    if delta == 1:
        return "ONTEM", sub
    return sub.split(",")[0].capitalize(), d.strftime("%d/%m")


# tempo de jogo: depois disso consideramos a partida encerrada e tiramos do site
DURACAO_JOGO_H = 2.5


def jogo_relevante(j, agora_dt) -> bool:
    """True se o jogo ainda nao acabou (mostra hoje/amanha; some quando termina)."""
    if not j.data:
        return False
    try:
        quando = datetime.strptime(f"{j.data} {j.hora}", "%Y-%m-%d %H:%M")
        quando = quando.replace(tzinfo=agora_dt.tzinfo)
    except ValueError:
        # sem hora valida: mantem o dia todo (fallback conservador)
        try:
            d = datetime.strptime(j.data, "%Y-%m-%d").date()
        except ValueError:
            return False
        return d >= agora_dt.date()
    return quando >= agora_dt - timedelta(hours=DURACAO_JOGO_H)


ARQ_ULTIMO_SUCESSO = PASTA_SITE / "ultima_coleta.txt"


def main(offline: bool = False) -> int:
    """Devolve um codigo de saida: 0 ok, 2 se nao produziu nenhum jogo."""
    agora_dt = datetime.now(FUSO_BR)
    agora = agora_dt.strftime("%d/%m/%Y %H:%M")
    hoje = agora_dt.date()
    print(f"\n=== Atualizando Probabilidades FC ({agora}) ===\n")

    # Busca odds do mercado (Oddschecker) para comparação Cérebro vs Mercado
    mercado_odds: dict = {}
    if not offline:
        try:
            from dados.oddschecker import buscar_mercado
            print("[Oddschecker]")
            mercado_odds = buscar_mercado()
            print(f"  -> {len(mercado_odds)} jogos com odds do mercado\n")
        except Exception as e:
            print(f"  [Oddschecker falhou: {type(e).__name__}] seguindo sem odds\n")

    # 1) concilia previsoes anteriores com o resultado real (so online)
    if not offline:
        try:
            from conferir import conferir_pendentes
            n_conf = conferir_pendentes(hoje)
            if n_conf:
                print(f"[log: {n_conf} previsoes anteriores conferidas]\n")
        except Exception as e:
            print(f"[log: conferir falhou: {type(e).__name__}]\n")

    # junta TODOS os jogos de todas as ligas, com sua data/hora, p/ separar por data
    por_data: dict[str, list[tuple[str, str]]] = {}  # data -> [(hora, card_html)]
    previsoes_log: list[dict] = []
    dicas_jogos: list = []  # (jogo, mercados, liga_cfg, liga_key) p/ a aba Dicas
    alguma_online = False

    for liga_key in LIGAS:
        print(f"[{LIGAS[liga_key]['nome']}]")
        liga_params = parametros_da_liga(liga_key)
        times, jogos, online_ok = obter_dados(liga_key, offline, hoje)
        alguma_online = alguma_online or online_ok

        # Recalcular médias de gols da liga com dados reais da temporada
        if online_ok and COMPETICOES_365.get(liga_key):
            try:
                d1_liga, _ = janela_liga(liga_key, hoje_date=hoje)
                d2_liga = hoje.strftime("%d/%m/%Y")
                gm, gv = medias_liga(COMPETICOES_365[liga_key], d1_liga, d2_liga)
                if gm and gv:
                    liga_params = _dc_replace(liga_params,
                                              media_gols_mandante=gm,
                                              media_gols_visitante=gv)
                    print(f"  [médias reais] mandante={gm:.2f}  visitante={gv:.2f}  "
                          f"(hardcoded era {parametros_da_liga(liga_key).media_gols_mandante:.2f}"
                          f"/{parametros_da_liga(liga_key).media_gols_visitante:.2f})")
            except Exception as e:
                print(f"  [médias reais falhou: {type(e).__name__}]")

        # Copa do Mundo: ajusta prior bayesiano com ranking FIFA para cada seleção
        if liga_key == "copa_mundo" and times:
            try:
                times = aplicar_elo_copa(times)
                print(f"  [ELO FIFA] prior ajustado para {len(times)} seleções")
            except Exception as e:
                print(f"  [ELO FIFA falhou: {type(e).__name__}]")

        # Coleta desfalques (suspensos/lesionados) — só Brasileirão, falha silenciosamente
        desfal_liga: dict = {}
        if not offline and liga_key in ("brasileirao_a", "brasileirao_b"):
            try:
                desfal_liga = coletar_desfalques(liga_key)
            except Exception as e:
                print(f"  [desfalques falhou: {type(e).__name__}]")

        calc = 0
        for j in jogos:
            if not jogo_relevante(j, agora_dt):  # ignora passados/encerrados
                continue
            tm = achar_time(j.mandante, times)
            tv = achar_time(j.visitante, times)
            if not tm or not tv:
                faltando = j.mandante if not tm else j.visitante
                print(f"  ! sem stats para '{faltando}' (pulado)")
                continue

            lam_m, lam_v = gols_esperados(tm, tv, liga_params)
            esc = escanteios_esperados(tm, tv, liga_params)
            cart = cartoes_esperados(tm, tv, liga_params)
            mercados = calcular_mercados(
                lam_m, lam_v, lam_escanteios=esc, lam_cartoes=cart,
                disp_escanteios=liga_params.disp_escanteios,
                disp_cartoes=liga_params.disp_cartoes)

            # Odds do mercado para este jogo (fuzzy match)
            mkt_jogo = None
            if mercado_odds:
                try:
                    from dados.oddschecker import lookup_mercado
                    mkt_jogo = lookup_mercado(j.data, j.mandante, j.visitante, mercado_odds)
                except Exception:
                    pass

            desfal_jogo = desfalques_do_jogo(j.mandante, j.visitante, desfal_liga) if desfal_liga else None
            card = card_jogo(j, mercados, LIGAS[liga_key], mercado=mkt_jogo, desfalques=desfal_jogo)
            por_data.setdefault(j.data, []).append((j.hora, card))
            dicas_jogos.append((j, mercados, LIGAS[liga_key], liga_key, mkt_jogo))

            def _r4(x):
                return round(x, 4)
            previsoes_log.append({
                "id": id_jogo(j.data, j.mandante, j.visitante),
                "registrado_em": agora, "liga": liga_key, "data": j.data, "hora": j.hora,
                "mandante": j.mandante, "visitante": j.visitante,
                "p1": _r4(mercados.vitoria_mandante), "px": _r4(mercados.empate),
                "p2": _r4(mercados.vitoria_visitante),
                "po05": _r4(mercados.over_05), "po15": _r4(mercados.over_15),
                "po25": _r4(mercados.over_25), "pbtts": _r4(mercados.ambas_marcam),
                "pesc95": _r4(mercados.escanteios.get("over_9_5", 0)) if mercados.escanteios else "",
                "pcart45": _r4(mercados.cartoes.get("over_4_5", 0)) if mercados.cartoes else "",
                "status": "previsto",
            })
            calc += 1
        print(f"  -> {calc} jogos calculados\n")

    # 2) grava as previsoes de hoje no log (so online, p/ nao poluir com reruns offline)
    if not offline and previsoes_log:
        n = registrar(previsoes_log)
        print(f"[log: {n} previsoes de hoje registradas]\n")

    # monta os grupos por data, em ordem cronologica, com rotulo HOJE/AMANHÃ
    grupos = []
    for data_str in sorted(por_data):
        rotulo, sub = rotulo_data(data_str, hoje)
        cards = [c for _, c in sorted(por_data[data_str])]  # ordena por horario
        grupos.append((rotulo, sub, cards))

    total = sum(len(c) for _, _, c in grupos)

    # carimbo honesto: "ultima coleta com SUCESSO" (so atualiza se veio dado online)
    if alguma_online and total > 0:
        ARQ_ULTIMO_SUCESSO.write_text(agora, encoding="utf-8")
    ultima_coleta = (ARQ_ULTIMO_SUCESSO.read_text(encoding="utf-8").strip()
                     if ARQ_ULTIMO_SUCESSO.exists() else agora)
    dados_backup = not (alguma_online and total > 0)

    try:
        from placar import linha_site
        placar = linha_site()
    except Exception:
        placar = ""

    destino = gerar_site(grupos, ultima_coleta, dados_backup=dados_backup, placar=placar)
    print(f"=== Pronto! {total} jogos no site, separados em {len(grupos)} data(s) ===")
    print(f"Abra: {destino}")

    # aba Tendências (scout + padrões dos jogos já disputados) — só online
    perfis_liga: dict = {}  # {liga: {time_norm: taxas reais}} p/ cruzar com o modelo
    if not offline:
        try:
            from backtest import coletar_registros
            from estudo import estudar
            from estudo_times import rankings, sequencias
            from padroes import dna_dados, perfil_map
            trends = []
            for lk in LIGAS:
                d1, d2 = janela_liga(lk, 210, hoje)  # janela da temporada atual
                reg = coletar_registros(COMPETICOES_365[lk], d1, d2)
                minj = 3 if lk == "copa_mundo" else 5
                perfis_liga[lk] = perfil_map(reg, 3 if lk == "copa_mundo" else 4)
                trends.append({
                    "nome": LIGAS[lk]["nome"], "emoji": LIGAS[lk]["emoji"],
                    "ambiente": estudar(reg),
                    "rankings": rankings(reg) if lk != "copa_mundo" else {},
                    "sequencias": sequencias(reg, min_jogos=minj),
                    "dna": dna_dados(reg, 2 if lk == "copa_mundo" else 6),
                })
            gerar_tendencias(trends, ultima_coleta)
            print("[aba Tendências gerada]")
        except Exception as e:
            print(f"[Tendências falhou: {type(e).__name__}: {e}]")

    # aba Dicas (o que explorar) — sempre; reforço pelos padrões quando houver
    try:
        from collections import defaultdict
        from dicas import dicas_do_jogo
        dpd = defaultdict(list)
        for j, m, ligacfg, lk, mkt in dicas_jogos:
            ds = dicas_do_jogo(j, m, perfis_liga.get(lk), mercado_odds=mkt)
            if ds:
                selo = f"{ligacfg.get('emoji', '')} {ligacfg.get('nome', '')}"
                dpd[j.data].append((j.hora, card_dica(j.mandante, j.visitante, j.hora, selo, ds)))
        grupos_dicas = []
        for data_str in sorted(dpd):
            rot, sub = rotulo_data(data_str, hoje)
            grupos_dicas.append((rot, sub, [c for _, c in sorted(dpd[data_str])]))
        gerar_dicas_html(grupos_dicas, ultima_coleta)
        print(f"[aba Dicas gerada: {sum(len(c) for _, _, c in grupos_dicas)} jogos com dica]")
    except Exception as e:
        print(f"[Dicas falhou: {type(e).__name__}: {e}]")

    # aba Histórico (resultado das partidas já mostradas, conciliadas com o real)
    try:
        from collections import defaultdict
        from dados.registro import conferidos
        conf = conferidos()
        # resumo de acerto do modelo
        resumo = None
        if conf:
            res = ov = bt = 0

            def fl(r, c):
                try:
                    return float(r.get(c, "") or 0)
                except ValueError:
                    return 0.0
            for r in conf:
                gm, gv = fl(r, "gm"), fl(r, "gv")
                tot = gm + gv
                pp = [fl(r, "p1"), fl(r, "px"), fl(r, "p2")]
                if pp.index(max(pp)) == (0 if gm > gv else (1 if gm == gv else 2)):
                    res += 1
                if (fl(r, "po25") >= 0.5) == (tot >= 3):
                    ov += 1
                if (fl(r, "pbtts") >= 0.5) == (gm >= 1 and gv >= 1):
                    bt += 1
            n = len(conf)
            resumo = {"n": n, "res": res / n, "over": ov / n, "btts": bt / n}

        ph = defaultdict(list)
        for r in conf:
            ph[r["data"]].append(card_historico(r, LIGAS.get(r["liga"])))
        grupos_h = []
        for data_str in sorted(ph, reverse=True):  # mais recente primeiro
            rot, sub = rotulo_passado(data_str, hoje)
            grupos_h.append((rot, sub, ph[data_str]))
        gerar_historico_html(grupos_h, ultima_coleta, resumo)
        print(f"[aba Histórico gerada: {len(conf)} jogos conferidos]")
    except Exception as e:
        print(f"[Histórico falhou: {type(e).__name__}: {e}]")

    if total == 0:
        print("!! NENHUM jogo calculado - coleta falhou ou sem jogos. (exit 2)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(offline="--offline" in sys.argv))
