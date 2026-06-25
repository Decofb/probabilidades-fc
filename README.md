# ⚽ Probabilidades FC

Site que calcula **probabilidades em %** (nunca odds) para jogos de futebol, a
partir das estatísticas recentes dos times. Jogos separados por **data (hoje / amanhã)**.

Mercados por jogo:
- 🏆 **Resultado (1X2)** — vitória mandante / empate / visitante
- ⚽ **Gols** — +0,5 / +1,5 / +2,5 + **Ambas Marcam (BTTS)**
- ⚖️ **Handicap Asiático**
- ⛳ **Escanteios** (+7,5 a +11,5)
- 🟨 **Cartões** (+2,5 a +6,5)

🌐 **No ar:** https://decofb.github.io/probabilidades-fc/

---

## Como funciona

1. **Fonte de dados: 365scores** (API JSON pública, sem Cloudflare). Para cada
   partida finalizada coletamos **gols, xG, escanteios e cartões** de cada time
   (`dados/scores365.py`). Disso saem as médias por jogo (a "forma" do time).
2. **Motor estatístico** (`motor/`):
   - **Poisson + Dixon-Coles** para os gols → 1X2, Over/Under, BTTS, handicap.
   - **Vantagem de casa por liga**: Brasileirão tem mando real; **Copa do Mundo é
     campo neutro** (sem vantagem para o "mandante" do feed).
   - **Shrinkage bayesiano**: com poucos jogos (ex.: início de Copa), a força do
     time regride para a média da liga — evita probabilidades superconfiantes (97%/0%).
3. **Site** (`site_gerador.py`) — HTML estático em `docs/`, agrupado por data.
4. **Cache CSV** (`dados/*.csv`) — backup automático quando o 365scores falha.

## Comandos

```
python atualizar.py            # busca do 365scores, gera o site (sai !=0 se nada vier)
python atualizar.py --offline  # usa só o cache CSV (não acessa a internet)
python -m pytest -q            # roda a rede de testes do motor
python backtest.py             # mede o modelo contra resultados reais (calibração)
python otimizar.py             # acha os melhores parâmetros por evidência
```

## Como afiamos as probabilidades (laço de feedback)

O `backtest.py` replica o modelo no passado **sem look-ahead** (só usa dados anteriores
a cada jogo) e mede, por mercado: **Brier**, **log-loss** e **curva de calibração**,
comparando com um baseline (prever sempre a taxa-base). Regra de ouro: só se muda o
modelo se a métrica melhorar.

O `otimizar.py` varre parâmetros (nível de gols, `rho` do Dixon-Coles, dispersão da
Binomial Negativa) e escolhe por evidência.

**Diagnóstico atual (170 jogos do Brasileirão):**
- Mercados de **gols** (1X2, Over/Under, BTTS): superam o baseline e estão bem calibrados.
  A varredura confirmou que os parâmetros atuais já são os melhores — não se mexe.
- **Escanteios e cartões**: ainda **não superam o baseline**. Estão marcados como
  *baixa confiança* no site. A Binomial Negativa corrige a sobredispersão (ganho pequeno),
  mas o sinal em si é fraco — melhoria futura (mais dados, contexto do árbitro).

## Automação (já configurada)

- **Agendador do Windows** → tarefa `ProbabilidadesFC` roda `atualizar.bat` todo dia 08:00.
- O `.bat` **só publica se a coleta deu certo** (checa exit-code do Python e do `git push`).
- Em caso de falha, o site mantém a última versão boa e exibe banner **"DADOS DE BACKUP"**;
  o carimbo "Última coleta OK" mostra quando os dados foram de fato atualizados.
- Log em `logs/cron.log`.

## Estrutura

```
probabilidades-fc/
  motor/
    poisson.py     # Poisson + Dixon-Coles, mercados, handicap
    forca.py       # força do time -> gols esperados (com shrinkage e mando por liga)
  dados/
    scores365.py   # coletor da API do 365scores (gols, xG, escanteios, cartões)
    fonte.py       # cache CSV das estatísticas
    jogos.py       # cache CSV dos jogos
  tests/           # rede de segurança do motor (pytest)
  site_gerador.py  # monta o site HTML
  atualizar.py     # >>> o comando principal <<<
  atualizar.bat    # automação diária (Agendador do Windows)
  docs/index.html  # o site publicado (GitHub Pages)
```

---

⚠️ **As porcentagens são estimativas estatísticas, não garantias.** Futebol tem zebra.
Use como apoio à decisão, com responsabilidade.
