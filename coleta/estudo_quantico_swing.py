"""Estudo: swing por risco-retorno (stop e alvo em ATR) nos papéis de computação quântica.

Só leitura. Pergunta: escolher stop e alvo por uma razão risco-retorno, sozinho, dá vantagem?
Compara cada configuração com comprar no mesmo dia e segurar o mesmo número de pregões, separa o
período em duas metades (a segunda serve de fora da amostra) e testa filtros de entrada simples.
Dados diários do Yahoo (yfinance), ~4 anos. Entrada na abertura do pregão seguinte ao sinal.
"""
import os
import numpy as np
import pandas as pd
import yfinance as yf

QUANT = os.environ.get("PAPEIS", "IONQ RGTI QBTS QUBT").split()
CUSTO = 0.002  # 0,20% ida e volta (spread + derrapagem; swing em small caps voláteis)
saida = []
p = saida.append

raw = yf.download(QUANT + ["SPY"], period="4y", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
dados = {t: raw[t].dropna() for t in QUANT + ["SPY"] if t in raw.columns.get_level_values(0) and len(raw[t].dropna()) > 300}
QUANT = [t for t in QUANT if t in dados]


def atr(df, n):
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def ifr(c, n=2):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def preparar(df):
    df = df.copy()
    df["atr"] = atr(df, 14)
    df["atr_curto"] = atr(df, 5) / atr(df, 20)
    df["mme50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["ifr2"] = ifr(df["Close"])
    return df


FILTROS = {
    "todos os dias": lambda d: pd.Series(True, index=d.index),
    "acima da MME50": lambda d: d["Close"] > d["mme50"],
    "recuo (IFR2<10)": lambda d: d["ifr2"] < 10,
    "recuo acima da MME50": lambda d: (d["ifr2"] < 10) & (d["Close"] > d["mme50"]),
    "volatilidade comprimida": lambda d: d["atr_curto"] < 0.75,
}


def simular(df, sinal, k, R, N):
    """Uma linha por entrada: resultado % (com custo), R obtido e o retorno de só segurar N pregões."""
    o, h, l, c, a = (df[x].values for x in ("Open", "High", "Low", "Close", "atr"))
    idx = df.index
    res = []
    s = sinal.values
    for i in range(20, len(df) - N - 1):
        if not s[i] or not np.isfinite(a[i]):
            continue
        e = o[i + 1]
        stop, alvo = e - k * a[i], e + R * k * a[i]
        sai = None
        for j in range(i + 1, i + 1 + N):
            if j > i + 1 and o[j] <= stop:      # gap abaixo do stop
                sai = o[j]; break
            if j > i + 1 and o[j] >= alvo:      # gap acima do alvo
                sai = o[j]; break
            if l[j] <= stop:                     # se tocar os dois no mesmo dia, conta o stop (conservador)
                sai = stop; break
            if h[j] >= alvo:
                sai = alvo; break
        if sai is None:
            sai = c[i + N]
        r = sai / e - 1 - CUSTO
        res.append(dict(d=idx[i], r=r, rR=(sai - e) / (k * a[i]), segurar=c[i + N] / e - 1 - CUSTO))
    return pd.DataFrame(res, columns=["d", "r", "rR", "segurar"])


prep = {t: preparar(dados[t]) for t in QUANT}
meio = sorted(set().union(*[set(d.index) for d in prep.values()]))
meio = meio[len(meio) // 2]


def resumo(df):
    if df.empty:
        return "—"
    return (f"n={len(df)} · acerto {np.mean(df.r > 0)*100:.0f}% · média {df.r.mean()*100:+.2f}% "
            f"({df.rR.mean():+.2f}R) · segurar {df.segurar.mean()*100:+.2f}%")


def rodar(filtro, k, R, N):
    partes = []
    for t in QUANT:
        d = prep[t]
        x = simular(d, FILTROS[filtro](d).fillna(False), k, R, N)
        x["t"] = t
        partes.append(x)
    x = pd.concat(partes)
    return x[x.d < meio], x[x.d >= meio]


spy = dados["SPY"]["Close"]
p(f"# Swing por risco-retorno: {', '.join(QUANT)}")
p("")
p(f"Período: {min(d.index[0] for d in prep.values()).date()} a {max(d.index[-1] for d in prep.values()).date()}. "
  f"1ª metade (treino) até {meio.date()}, 2ª metade (fora da amostra) depois. Custo {CUSTO*100:.1f}% ida e volta.")
for t in QUANT:
    d = prep[t]["Close"]
    a = d[d.index < meio]; b = d[d.index >= meio]
    p(f"- {t}: 1ª metade {(a.iloc[-1]/a.iloc[0]-1)*100:+.0f}%, 2ª metade {(b.iloc[-1]/b.iloc[0]-1)*100:+.0f}%")
p("")
p("No acaso puro (sem tendência), um alvo R vezes o risco acerta cerca de 1/(1+R) e dá ganho esperado zero menos o custo.")
p("")

p("## 1. Só risco-retorno, entrando todo dia (stop k×ATR, alvo R×risco, saída por tempo em N pregões)")
p("")
p("| k (stop em ATR) | R (alvo:risco) | N | Acerto no acaso | 1ª metade | 2ª metade |")
p("|---|---|---|---|---|---|")
for N in (5, 10):
    for k in (1.0, 1.5, 2.0, 3.0):
        for R in (1.0, 2.0, 3.0):
            a, b = rodar("todos os dias", k, R, N)
            p(f"| {k} | {R:g}:1 | {N} | {100/(1+R):.0f}% | {resumo(a)} | {resumo(b)} |")
p("")

p("## 2. Filtro de entrada + risco-retorno (k=1,5 ATR, alvo 2:1, até 10 pregões)")
p("")
p("| Entrada | 1ª metade | 2ª metade |")
p("|---|---|---|")
for f in FILTROS:
    a, b = rodar(f, 1.5, 2.0, 10)
    p(f"| {f} | {resumo(a)} | {resumo(b)} |")
p("")

# por papel, configuração do meio
p("## 3. Por papel (todos os dias, k=1,5, 2:1, 10 pregões)")
p("")
p("| Papel | 1ª metade | 2ª metade |")
p("|---|---|---|")
for t in QUANT:
    d = prep[t]
    x = simular(d, pd.Series(True, index=d.index), 1.5, 2.0, 10)
    p(f"| {t} | {resumo(x[x.d < meio])} | {resumo(x[x.d >= meio])} |")
p("")

# pior sequência e risco da carteira com 1% de risco por operação, operações sem sobreposição
p("## 4. Como seria operando de verdade (1 operação por vez em cada papel, risco de 1% do capital por operação)")
p("")
for f in ("todos os dias", "recuo acima da MME50"):
    for nome_per, sel in (("1ª metade", lambda x: x.d < meio), ("2ª metade", lambda x: x.d >= meio)):
        cap = []
        for t in QUANT:
            d = prep[t]
            x = simular(d, FILTROS[f](d).fillna(False), 1.5, 2.0, 10)
            x = x[sel(x)].reset_index(drop=True)
            # sem sobreposição: pula entradas enquanto a anterior está aberta (aprox. 10 pregões)
            usados, ultimo = [], None
            for _, row in x.iterrows():
                if ultimo is None or (row.d - ultimo).days > 14:
                    usados.append(row); ultimo = row.d
            cap.append(pd.DataFrame(usados))
        y = pd.concat([c for c in cap if not c.empty] or [pd.DataFrame(columns=["d", "rR"])]).sort_values("d")
        if y.empty:
            continue
        curva = (1 + 0.01 * y.rR.values).cumprod()
        queda = (curva / np.maximum.accumulate(curva) - 1).min()
        perdas = (y.rR.values < 0).astype(int)
        seq = max((len(s) for s in "".join(map(str, perdas)).split("0")), default=0)
        p(f"- {f}, {nome_per}: {len(y)} operações, resultado {(curva[-1]-1)*100:+.0f}% do capital, "
          f"pior queda {queda*100:.0f}%, maior sequência de perdas {seq}.")
p("")

texto = "\n".join(saida)
open(os.environ.get("SAIDA", "estudo_quantico_swing.md"), "w").write(texto)
print("RELATORIO_INICIO"); print(texto); print("RELATORIO_FIM")
