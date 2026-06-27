"""Testa cross-validação Flash vs 365scores usando CSV local."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from dados.flashscore import coletar_estatisticas, comparar_com_365
from dados.fonte import carregar_times_csv

for liga in ('brasileirao_a', 'brasileirao_b'):
    print(f'\n=== {liga} ===')
    flash = coletar_estatisticas(liga)
    s365 = carregar_times_csv(liga)
    if not s365:
        print('  sem CSV do 365scores para comparar')
        continue
    divs = comparar_com_365(flash, s365, limiar_delta=0.2)
    if divs:
        print(f'  {len(divs)} divergências:')
        for d in divs:
            print(f'    {d["time_flash"]:25s} GF: Flash={d["flash_gf"]} / 365={d["s365_gf"]}  '
                  f'GS: Flash={d["flash_gs"]} / 365={d["s365_gs"]}  Δ={d["delta_gf"]+d["delta_gs"]:.2f}')
    else:
        print(f'  OK — {len(flash)} times convergentes com 365scores')
