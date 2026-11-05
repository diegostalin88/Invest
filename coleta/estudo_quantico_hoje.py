"""Pregão de hoje dos papéis quânticos contra o estudo: tamanho do movimento, horário e correlação com Nasdaq e Bitcoin.
Só leitura."""
import numpy as np
import pandas as pd
import yfinance as yf

ACOES = ["IONQ", "RGTI", "QBTS", "QUBT", "QQQ", "SPY"]
TODOS = ACOES + ["BTC-USD"]
NY = "America/New_York"
saida = []
p = saida.append

def baixar(intervalo, periodo):
    """Um papel por vez e sem threads (o cache do yfinance travou com downloads em paralelo), com nova tentativa."""
    import time
    partes = {}
    for t in TODOS:
        for tentativa in range(4):
            x = yf.download(t, interval=intervalo, period=periodo, auto_adjust=True, progress=False, threads=False)
            if not x.empty:
                break
            time.sleep(3 * (tentativa + 1))
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.get_level_values(0)
        if intervalo == "1d":  # diário: só a data, sem fuso (o Bitcoin vem em UTC e as ações em NY)
            x.index = pd.to_datetime([i.date() for i in x.index])
        partes[t] = x
    return pd.concat(partes, axis=1)


m5 = baixar("5m", "60d")
d1 = baixar("1d", "1y")


def serie(df, t):
    x = df[t].dropna()
    if x.index.tz is not None:
        x.index = x.index.tz_convert(NY)
    return x


hoje = max(serie(m5, "IONQ").index.date)
agora = serie(m5, "IONQ").index.max()
p(f"# Pregão de {hoje} até {agora.strftime('%H:%M')} (horário de Nova York)")
p("")
p("| Papel | Fechamento anterior → agora | ATR14 diário | Movimento em ATRs | Mínima do dia | Máxima do dia | Dias do último ano com queda maior |")
p("|---|---|---|---|---|---|---|")
for t in TODOS:
    x = serie(m5, t)
    d = serie(d1, t)
    d = d[d.index.date < hoje] if t != "BTC-USD" else d[[i.date() < hoje for i in d.index]]
    fech_ant = d["Close"].iloc[-1]
    if t == "BTC-USD":
        hj = x[x.index >= pd.Timestamp(hoje).tz_localize(NY) + pd.Timedelta(hours=9, minutes=30)]
    else:
        hj = x[x.index.date == hoje]
    if hj.empty:
        continue
    ult = hj["Close"].iloc[-1]
    pc = d["Close"].shift(1)
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - pc).abs(), (d["Low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    mov = ult / fech_ant - 1
    rets = d["Close"].pct_change().dropna()
    pior = np.mean(rets < mov) * 100
    p(f"| {t} | {mov*100:+.1f}% | {atr/fech_ant*100:.1f}% | {(ult-fech_ant)/atr:+.1f} | {(hj['Low'].min()/fech_ant-1)*100:+.1f}% às {hj['Low'].idxmin().strftime('%H:%M')} | "
      f"{(hj['High'].max()/fech_ant-1)*100:+.1f}% às {hj['High'].idxmax().strftime('%H:%M')} | {pior:.0f}% |")
p("")
p("(Bitcoin: desde a abertura de NY.)")
p("")

# correlação de 5 min: hoje vs últimos 60 dias, IONQ contra QQQ e BTC
r = pd.DataFrame({t: serie(m5, t)["Close"] for t in TODOS})
r = r[[True if (i.hour * 60 + i.minute) >= 575 and (i.hour * 60 + i.minute) < 960 else False for i in r.index]]
r = r.dropna(subset=["IONQ"]).ffill().pct_change()
r = r[pd.Series(r.index.date, index=r.index) == pd.Series(r.index.date, index=r.index).shift(1)]
m = r.index.date == hoje
p("Correlação dos movimentos de 5 min:")
p("")
p("| Par | Hoje | Últimos 60 dias |")
p("|---|---|---|")
for a, b in [("IONQ", "QQQ"), ("IONQ", "BTC-USD"), ("QQQ", "BTC-USD"), ("IONQ", "RGTI"), ("IONQ", "QBTS")]:
    p(f"| {a} × {b} | {r.loc[m, a].corr(r.loc[m, b]):.2f} | {r.loc[~m, a].corr(r.loc[~m, b]):.2f} |")
p("")
dd = pd.DataFrame({t: serie(d1, t)["Close"] for t in ["IONQ", "QQQ"]})
btc = serie(d1, "BTC-USD")["Close"]
btc.index = pd.to_datetime([i.date() for i in btc.index])
dd.index = pd.to_datetime([i.date() for i in dd.index])
dd["BTC"] = btc
dr = dd.pct_change().dropna()
beta_q = np.cov(dr.IONQ, dr.QQQ)[0, 1] / dr.QQQ.var()
p(f"Diário, último ano: correlação IONQ × Nasdaq (QQQ) {dr.IONQ.corr(dr.QQQ):.2f}, IONQ × Bitcoin {dr.IONQ.corr(dr.BTC):.2f}. "
  f"Beta da IONQ contra a Nasdaq: {beta_q:.1f} (em média, a IONQ se move {beta_q:.1f} vez o movimento da Nasdaq).")
p("")

# volatilidade por faixa de horário hoje vs estudo
x = serie(m5, "IONQ")
ri = x["Close"].pct_change().abs()
ri = ri[x.index.strftime("%H:%M") != "09:30"]
faixa = ri.index.floor("60min").strftime("%H:%M")
tab = pd.DataFrame({"hoje": ri.where(ri.index.date == hoje), "antes": ri.where(ri.index.date != hoje), "f": faixa}).groupby("f").mean()
p("IONQ, média do |movimento de 5 min| por hora:")
p("")
p("| Hora | Hoje | Últimos 60 dias |")
p("|---|---|---|")
for f, row in tab.iterrows():
    if np.isfinite(row.hoje):
        p(f"| {f} | {row.hoje*100:.2f}% | {row.antes*100:.2f}% |")
p("")
# IONQ desde segunda (02/11)
d = serie(d1, "IONQ")
seg = d[d.index.date == pd.Timestamp("2026-11-02").date()]
if not seg.empty:
    ult = x["Close"].iloc[-1]
    p(f"IONQ: segunda 02/11 abriu a {seg['Open'].iloc[0]:.2f} e fechou a {seg['Close'].iloc[0]:.2f}; "
      f"fechou ontem a {d[d.index.date < hoje]['Close'].iloc[-1]:.2f}; agora {ult:.2f}.")

texto = "\n".join(saida)
open("estudo_quantico_hoje.md", "w").write(texto)
print("RELATORIO_INICIO"); print(texto); print("RELATORIO_FIM")
