"""Estudo exploratório: volatilidade intradiária das ações de computação quântica.

Só leitura, não mexe no app nem na estratégia congelada. Pergunta: os padrões que aparecem nos
últimos 4 pregões se repetem nos pregões anteriores (fora da amostra) e superam o acaso?

Dados (Yahoo via yfinance): 5 min (últimos ~60 dias), 1 h (~2 anos), diário (~4 anos).
Saída: relatório em Markdown no stdout (entre RELATORIO_INICIO/RELATORIO_FIM) e estudo_quantico.md.
"""
import sys
import numpy as np
import pandas as pd
import yfinance as yf

QUANT = ["IONQ", "RGTI", "QBTS", "QUBT"]
CONTROLE = ["SPY", "QQQ"]
TODOS = QUANT + CONTROLE
CUSTO = 0.0010          # ida e volta, 0,10% (spread + derrapagem de small caps voláteis)
N_AMOSTRA = 4           # pregões "recentes" onde o padrão foi visto
RNG = np.random.default_rng(42)
N_PERM = 5000
saida = []


def p(txt=""):
    saida.append(txt)


def baixar(intervalo, periodo):
    d = yf.download(TODOS, interval=intervalo, period=periodo, group_by="ticker",
                    auto_adjust=True, prepost=False, progress=False, threads=True)
    out = {}
    for t in TODOS:
        try:
            df = d[t].dropna(how="all").copy()
        except KeyError:
            continue
        if df.empty:
            continue
        if df.index.tz is not None:
            df.index = df.index.tz_convert("America/New_York")
        out[t] = df
    return out


def sessao(df):
    """Mantém só o pregão regular 9:30–16:00 NY."""
    hm = df.index.hour * 60 + df.index.minute
    return df[(hm >= 570) & (hm < 960)]


def ret(a, b):
    return b / a - 1


def perm_teste(sinal, resultado):
    """Média do retorno 'seguindo o sinal' e p-valor por permutação (sinais embaralhados entre dias)."""
    sinal = np.asarray(sinal, float); resultado = np.asarray(resultado, float)
    ok = (sinal != 0) & np.isfinite(resultado)
    s, r = np.sign(sinal[ok]), resultado[ok]
    if len(s) < 3:
        return dict(n=len(s), acerto=np.nan, media=np.nan, p=np.nan)
    obs = np.mean(s * r)
    perm = np.array([np.mean(RNG.permutation(s) * r) for _ in range(N_PERM)])
    pval = (np.sum(np.abs(perm) >= abs(obs)) + 1) / (N_PERM + 1)
    return dict(n=len(s), acerto=float(np.mean(s * r > 0)), media=float(obs), p=float(pval))


def fmt_pct(x, casas=2):
    return "—" if x is None or not np.isfinite(x) else f"{x*100:+.{casas}f}%"


def linha_teste(nome, r_in, r_out, liquido=True):
    def bloco(r):
        if not r or r["n"] == 0 or not np.isfinite(r["media"]):
            return "n=0"
        liq = r["media"] - CUSTO if liquido else r["media"]
        return f"n={r['n']} · acerto {r['acerto']*100:.0f}% · {fmt_pct(r['media'])} ({fmt_pct(liq)} líq.) · p={r['p']:.2f}"
    p(f"| {nome} | {bloco(r_in)} | {bloco(r_out)} |")


# ---------------------------------------------------------------- dados
m5 = {t: sessao(df) for t, df in baixar("5m", "60d").items()}
h1 = {t: sessao(df) for t, df in baixar("60m", "730d").items()}
d1 = baixar("1d", "4y")

datas5 = sorted(set(m5["IONQ"].index.date))
recentes = datas5[-N_AMOSTRA:]
anteriores = datas5[:-N_AMOSTRA]
p("# Estudo: volatilidade intradiária em computação quântica")
p()
p(f"Pregões recentes (amostra): {', '.join(str(d) for d in recentes)}. "
  f"Fora da amostra em 5 min: {len(anteriores)} pregões ({anteriores[0]} a {anteriores[-1]}). "
  f"1 h: {len(set(h1['IONQ'].index.date))} pregões. Diário: {len(d1['IONQ'])} pregões.")
p(f"Custo considerado: {CUSTO*100:.2f}% ida e volta. p = chance do acaso (permutação, {N_PERM} sorteios).")
p()

# ---------------------------------------------------------------- 1. o que aconteceu nos 4 pregões
p("## 1. O que aconteceu nos últimos 4 pregões")
p()
p("| Papel | Dia | Gap | 1ª meia hora | Resto do dia | Dia todo | Amplitude | Hora da máxima | Hora da mínima |")
p("|---|---|---|---|---|---|---|---|---|")
for t in QUANT + ["SPY"]:
    df = m5[t]
    for d in recentes:
        x = df[df.index.date == d]
        if x.empty:
            continue
        ant = df[df.index.date < d]
        fech_ant = ant["Close"].iloc[-1] if not ant.empty else np.nan
        abre = x["Open"].iloc[0]
        c30 = x[x.index.strftime("%H:%M") < "10:00"]["Close"].iloc[-1]
        fech = x["Close"].iloc[-1]
        p(f"| {t} | {d.strftime('%d/%m')} | {fmt_pct(ret(fech_ant, abre),1)} | {fmt_pct(ret(abre, c30),1)} | "
          f"{fmt_pct(ret(c30, fech),1)} | {fmt_pct(ret(abre, fech),1)} | {(x['High'].max()/x['Low'].min()-1)*100:.1f}% | "
          f"{x['High'].idxmax().strftime('%H:%M')} | {x['Low'].idxmin().strftime('%H:%M')} |")
p()

# correlação entre os papéis nos 5 min (recentes e antes)
r5 = pd.DataFrame({t: m5[t]["Close"].pct_change() for t in QUANT + ["SPY"]})
r5 = r5[r5.index.strftime("%H:%M") != "09:30"]  # tira o salto da abertura
rec_mask = np.isin(r5.index.date, recentes)
p("Correlação média dos retornos de 5 min entre os 4 papéis quânticos: "
  f"recentes {np.nanmean(r5.loc[rec_mask, QUANT].corr().values[np.triu_indices(4,1)]):.2f}, "
  f"antes {np.nanmean(r5.loc[~rec_mask, QUANT].corr().values[np.triu_indices(4,1)]):.2f}. "
  f"Com o SPY: recentes {r5.loc[rec_mask, QUANT].corrwith(r5.loc[rec_mask,'SPY']).mean():.2f}, "
  f"antes {r5.loc[~rec_mask, QUANT].corrwith(r5.loc[~rec_mask,'SPY']).mean():.2f}.")
p()

# ---------------------------------------------------------------- 2. perfil de volatilidade
p("## 2. Perfil de volatilidade ao longo do dia (média do |retorno| de 5 min, papéis quânticos)")
p()
absr = r5[QUANT].abs().mean(axis=1)
faixa = absr.index.floor("30min").strftime("%H:%M")
perf = pd.DataFrame({"faixa": faixa, "rec": np.where(rec_mask, absr, np.nan), "ant": np.where(~rec_mask, absr, np.nan)})
perf = perf.groupby("faixa").mean()
perf_spy = r5["SPY"].abs().groupby(faixa).mean()
p("| Faixa (NY) | Recentes | Antes | SPY (antes) |")
p("|---|---|---|---|")
for f, row in perf.iterrows():
    p(f"| {f} | {row['rec']*100:.2f}% | {row['ant']*100:.2f}% | {perf_spy[f]*100:.3f}% |")
p()
# volatilidade de um dia prevê a do dia seguinte? (agrupamento)
dvol = {}
for t in QUANT:
    dd = d1[t]
    rng = np.log(dd["High"] / dd["Low"])
    dvol[t] = rng.corr(rng.shift(1))
p("Amplitude de ontem vs. de hoje (correlação, diário ~4 anos): " +
  ", ".join(f"{t} {v:.2f}" for t, v in dvol.items()) + ".")
p()

# ---------------------------------------------------------------- 3. testes de direção
p("## 3. Padrões de direção: amostra recente vs. fora da amostra")
p()
p("Cada linha: n = casos (papel×dia), acerto, ganho médio seguindo o sinal (bruto e líquido de custo), p do acaso.")
p()


def dias_5m(tickers, conj):
    """Linhas por (papel, dia) com pontos-chave do dia em 5 min."""
    lin = []
    for t in tickers:
        df = m5[t]
        datas = sorted(set(df.index.date))
        for i, d in enumerate(datas):
            if d not in conj or i == 0:
                continue
            x = df[df.index.date == d]
            hh = x.index.strftime("%H:%M")
            if len(x) < 70:
                continue
            fech_ant = df[df.index.date == datas[i-1]]["Close"].iloc[-1]
            abre = x["Open"].iloc[0]
            c = lambda h: x[hh < h]["Close"].iloc[-1]
            lin.append(dict(t=t, d=d, gap=ret(fech_ant, abre), r30=ret(abre, c("10:00")),
                            resto30=ret(c("10:00"), x["Close"].iloc[-1]),
                            ate15=ret(abre, c("15:00")), ult=ret(c("15:00"), x["Close"].iloc[-1]),
                            dia=ret(abre, x["Close"].iloc[-1])))
    return pd.DataFrame(lin)


def dias_1h(tickers):
    lin = []
    for t in tickers:
        df = h1[t]
        datas = sorted(set(df.index.date))
        for i, d in enumerate(datas):
            x = df[df.index.date == d]
            if len(x) < 7 or i == 0:
                continue
            abre = x["Open"].iloc[0]
            lin.append(dict(t=t, d=d, r1h=ret(abre, x["Close"].iloc[0]),
                            resto1h=ret(x["Close"].iloc[0], x["Close"].iloc[-1]),
                            ate15=ret(abre, x["Close"].iloc[-2]), ult=ret(x["Close"].iloc[-2], x["Close"].iloc[-1])))
    return pd.DataFrame(lin)


rec = dias_5m(QUANT, set(recentes))
ant = dias_5m(QUANT, set(anteriores))
ant_spy = dias_5m(["SPY"], set(anteriores))
h = dias_1h(QUANT)
h_rec = h[h["d"].isin(recentes)]
h_ant = h[~h["d"].isin(recentes)]

p("| Padrão | Últimos 4 pregões | Fora da amostra |")
p("|---|---|---|")
testes = [
    ("Abertura continua (1ª meia hora → resto, 5 min)", "r30", "resto30", 1),
    ("Abertura reverte (1ª meia hora → resto, 5 min)", "r30", "resto30", -1),
    ("Gap continua (gap → abertura até fechamento)", "gap", "dia", 1),
    ("Gap fecha (gap → abertura até fechamento)", "gap", "dia", -1),
    ("Última hora segue o dia (até 15h → última hora)", "ate15", "ult", 1),
    ("Última hora reverte o dia", "ate15", "ult", -1),
]
res_in = {}
for nome, s, r, lado in testes:
    a = perm_teste(lado * rec[s], rec[r]); b = perm_teste(lado * ant[s], ant[r])
    res_in[nome] = (a, b)
    linha_teste(nome, a, b)
# versões longas em 1 h (2 anos)
for nome, s, r, lado in [("Abertura continua (1ª hora → resto, 1 h, 2 anos)", "r1h", "resto1h", 1),
                         ("Abertura reverte (1ª hora → resto, 1 h, 2 anos)", "r1h", "resto1h", -1),
                         ("Última hora segue o dia (1 h, 2 anos)", "ate15", "ult", 1)]:
    linha_teste(nome, perm_teste(lado * h_rec[s], h_rec[r]), perm_teste(lado * h_ant[s], h_ant[r]))
# dia seguinte (diário, anos)
lin = []
for t in QUANT:
    dd = d1[t]
    rr = (dd["Close"] / dd["Open"] - 1)
    gap_next = dd["Open"].shift(-1) / dd["Close"] - 1
    dia_next = dd["Close"].shift(-1) / dd["Close"] - 1
    lin.append(pd.DataFrame({"d": dd.index.date, "dia": rr, "prox": dia_next, "gapn": gap_next}))
dl = pd.concat(lin).dropna()
dl_rec = dl[dl["d"].isin(recentes[:-1])]
dl_ant = dl[~dl["d"].isin(recentes)]
linha_teste("Dia forte continua no dia seguinte (diário, 4 anos)", perm_teste(dl_rec["dia"], dl_rec["prox"]),
            perm_teste(dl_ant["dia"], dl_ant["prox"]))
linha_teste("Dia forte reverte no dia seguinte (diário, 4 anos)", perm_teste(-dl_rec["dia"], dl_rec["prox"]),
            perm_teste(-dl_ant["dia"], dl_ant["prox"]))
p()
p("Controle SPY (fora da amostra, 5 min): " + "; ".join(
    f"{nome.split(' (')[0]} acerto {perm_teste(lado*ant_spy[s], ant_spy[r])['acerto']*100:.0f}%"
    for nome, s, r, lado in testes[::2]) + ".")
p()

# ---------------------------------------------------------------- 4. reversão/continuação de 5 min
p("## 4. Movimento de 5 min prevê os próximos 5 min? (autocorrelação)")
p()
p("| Papel | Recentes | Fora da amostra | Faixa do acaso (±2/√n, fora) |")
p("|---|---|---|---|")
for t in QUANT + ["SPY"]:
    s = r5[t]
    def ac(m):
        x = s[m]; y = s.shift(-1)[m]
        same = pd.Series(x.index.date, index=x.index) == pd.Series(x.index.date, index=x.index).shift(-1)
        ok = same & x.notna() & y.notna()
        return x[ok].corr(y[ok]), ok.sum()
    a, na = ac(rec_mask); b, nb = ac(~rec_mask)
    p(f"| {t} | {a:+.3f} | {b:+.3f} | ±{2/np.sqrt(nb):.3f} |")
p()
# líder: IONQ antecipa os outros?
lead = {}
for t in ["RGTI", "QBTS", "QUBT"]:
    lead[t] = r5["IONQ"][~rec_mask].corr(r5[t].shift(-1)[~rec_mask])
p("IONQ nos 5 min anteriores vs. o papel nos 5 min seguintes (fora da amostra): " +
  ", ".join(f"{t} {v:+.3f}" for t, v in lead.items()) + ".")
p()

# ---------------------------------------------------------------- 5. hora da máxima/mínima vs acaso
p("## 5. Máximas e mínimas concentram no começo/fim do dia: é padrão ou acaso?")
p()


def frac_extremo_cedo(dfmap, datas, embaralhar=False):
    cont = tot = 0
    for t in QUANT:
        df = dfmap[t]
        for d in datas:
            x = df[df.index.date == d]["Close"]
            if len(x) < 70:
                continue
            r = np.diff(np.log(x.values))
            if embaralhar:
                r = RNG.permutation(r)
            caminho = np.concatenate([[0], np.cumsum(r)])
            for idx in (np.argmax(caminho), np.argmin(caminho)):
                cont += idx < 12  # primeira hora
                tot += 1
    return cont / tot if tot else np.nan


real_ant = frac_extremo_cedo(m5, anteriores)
real_rec = frac_extremo_cedo(m5, recentes)
sim = np.mean([frac_extremo_cedo(m5, anteriores, True) for _ in range(30)])
p(f"Máxima ou mínima do dia na 1ª hora: recentes {real_rec*100:.0f}%, fora da amostra {real_ant*100:.0f}%, "
  f"mesmos movimentos embaralhados (acaso puro) {sim*100:.0f}%. "
  "Um caminho aleatório também tende a marcar os extremos perto do começo e do fim (lei do arco-seno).")
p()

texto = "\n".join(saida)
open("estudo_quantico.md", "w").write(texto)
print("RELATORIO_INICIO"); print(texto); print("RELATORIO_FIM")
