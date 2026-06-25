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

from config import LIGAS, PASTA_SITE, parametros_da_liga
from dados.scores365 import (COMPETICOES_365, coletar_estatisticas,
                             coletar_jogos_futuros)
from dados.fonte import salvar_times_csv, carregar_times_csv
from dados.jogos import salvar_jogos_csv, carregar_jogos_csv
from motor.forca import (EstatisticasTime,
                         gols_esperados, escanteios_esperados, cartoes_esperados)
from motor.poisson import calcular_mercados, handicap_asiatico
from site_gerador import card_jogo, gerar_site

FUSO_BR = timezone(timedelta(hours=-3))
DIAS_HISTORICO = 45   # quantos dias pra tras pra montar a forma dos times
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


def obter_dados(liga_key: str, offline: bool, hoje):
    """
    Devolve (times, jogos, online_ok). 'hoje' e um date em BRT (mesma referencia
    do filtro de exibicao). online_ok=True so se a coleta no 365scores funcionou.
    """
    comp = COMPETICOES_365.get(liga_key)
    if not offline and comp:
        d1 = (hoje - timedelta(days=DIAS_HISTORICO)).strftime("%d/%m/%Y")
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
            return times, jogos, True
        except Exception as e:
            print(f"  [365scores falhou: {type(e).__name__}] usando CSV salvo")

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

    # junta TODOS os jogos de todas as ligas, com sua data/hora, p/ separar por data
    por_data: dict[str, list[tuple[str, str]]] = {}  # data -> [(hora, card_html)]
    alguma_online = False

    for liga_key in LIGAS:
        print(f"[{LIGAS[liga_key]['nome']}]")
        liga_params = parametros_da_liga(liga_key)
        times, jogos, online_ok = obter_dados(liga_key, offline, hoje)
        alguma_online = alguma_online or online_ok

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

            margem = arredondar_meio(lam_m - lam_v)
            linha_ha = -margem if margem != 0 else -0.5
            ha = handicap_asiatico(lam_m, lam_v, linha=linha_ha)

            card = card_jogo(j, mercados, ha, linha_ha, LIGAS[liga_key])
            por_data.setdefault(j.data, []).append((j.hora, card))
            calc += 1
        print(f"  -> {calc} jogos calculados\n")

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

    destino = gerar_site(grupos, ultima_coleta, dados_backup=dados_backup)
    print(f"=== Pronto! {total} jogos no site, separados em {len(grupos)} data(s) ===")
    print(f"Abra: {destino}")

    if total == 0:
        print("!! NENHUM jogo calculado - coleta falhou ou sem jogos. (exit 2)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(offline="--offline" in sys.argv))
