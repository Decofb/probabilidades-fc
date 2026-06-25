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

from config import LIGAS
from dados.scores365 import (COMPETICOES_365, coletar_estatisticas,
                             coletar_jogos_futuros)
from dados.fonte import salvar_times_csv, carregar_times_csv
from dados.jogos import salvar_jogos_csv, carregar_jogos_csv
from motor.forca import (EstatisticasTime, ParametrosLiga,
                         gols_esperados, escanteios_esperados)
from motor.poisson import calcular_mercados, handicap_asiatico
from site_gerador import card_jogo, gerar_site

DIAS_HISTORICO = 45   # quantos dias pra tras pra montar a forma dos times
DIAS_FRENTE = 6       # quantos dias pra frente buscar jogos


def normalizar(nome: str) -> str:
    return unidecode(nome).lower().strip()


def achar_time(nome: str, times: dict[str, EstatisticasTime]) -> EstatisticasTime | None:
    alvo = normalizar(nome)
    for t in times.values():
        if normalizar(t.nome) == alvo:
            return t
    for t in times.values():
        n = normalizar(t.nome)
        if alvo in n or n in alvo:
            return t
    palavra = alvo.split()[0] if alvo.split() else alvo
    for t in times.values():
        if palavra and palavra in normalizar(t.nome):
            return t
    return None


def arredondar_meio(x: float) -> float:
    return round(x * 2) / 2


def obter_dados(liga_key: str, offline: bool):
    """Devolve (times, jogos) buscando do 365scores ou caindo no CSV."""
    comp = COMPETICOES_365.get(liga_key)
    if not offline and comp:
        hoje = datetime.now()
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
            return times, jogos
        except Exception as e:
            print(f"  [365scores falhou: {type(e).__name__}] usando CSV salvo")

    times = carregar_times_csv(liga_key)
    jogos = carregar_jogos_csv(liga_key)
    print(f"  [CSV] {len(times)} times · {len(jogos)} jogos")
    return times, jogos


def main(offline: bool = False) -> None:
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M")
    print(f"\n=== Atualizando Probabilidades FC ({agora}) ===\n")

    blocos: dict[str, list[str]] = {}
    liga_params = ParametrosLiga()

    for liga_key in LIGAS:
        print(f"[{LIGAS[liga_key]['nome']}]")
        times, jogos = obter_dados(liga_key, offline)

        cards = []
        for j in jogos:
            tm = achar_time(j.mandante, times)
            tv = achar_time(j.visitante, times)
            if not tm or not tv:
                faltando = j.mandante if not tm else j.visitante
                print(f"  ! sem stats para '{faltando}' (pulado)")
                continue

            lam_m, lam_v = gols_esperados(tm, tv, liga_params)
            esc = escanteios_esperados(tm, tv, liga_params)
            mercados = calcular_mercados(lam_m, lam_v, lam_escanteios=esc)

            margem = arredondar_meio(lam_m - lam_v)
            linha_ha = -margem if margem != 0 else -0.5
            ha = handicap_asiatico(lam_m, lam_v, linha=linha_ha)

            cards.append(card_jogo(j, mercados, ha, linha_ha))

        blocos[liga_key] = cards
        print(f"  -> {len(cards)} jogos calculados\n")

    destino = gerar_site(blocos, agora)
    total = sum(len(c) for c in blocos.values())
    print(f"=== Pronto! {total} jogos no site ===")
    print(f"Abra: {destino}")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
