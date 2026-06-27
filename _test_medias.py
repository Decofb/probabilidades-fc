"""Verifica médias reais da liga vs valores hardcoded."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from config import LIGAS, janela_liga, PARAMETROS_LIGA
from dados.scores365 import COMPETICOES_365, medias_liga
from datetime import date

hoje = date.today()
for liga_key in ('brasileirao_a', 'brasileirao_b', 'copa_mundo'):
    d1, d2 = janela_liga(liga_key, hoje_date=hoje)
    comp = COMPETICOES_365[liga_key]
    print(f'\n{LIGAS[liga_key]["nome"]}  ({d1} → {d2})')
    gm, gv = medias_liga(comp, d1, d2)
    cfg = PARAMETROS_LIGA[liga_key]
    if gm and gv:
        print(f'  Hardcoded : mandante={cfg.media_gols_mandante:.2f}  visitante={cfg.media_gols_visitante:.2f}')
        print(f'  Real 2026 : mandante={gm:.2f}  visitante={gv:.2f}')
        dm = gm - cfg.media_gols_mandante
        dv = gv - cfg.media_gols_visitante
        print(f'  Delta     : mandante={dm:+.2f}  visitante={dv:+.2f}')
    else:
        print('  sem dados suficientes')
