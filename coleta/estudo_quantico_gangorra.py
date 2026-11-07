"""Estudo: a "gangorra" (sobe, devolve, sobe) dos papéis quânticos no último mês.

Só leitura. Mede reversão à média no último mês (21 pregões) com barras de 1 h e diárias,
compara com o acaso (os mesmos retornos embaralhados) e pergunta o que importa para operar:
um mês de gangorra é seguido de outro mês de gangorra?
"""
import os
import numpy as np
import pandas as pd
import yfinance as yf

PAPEIS = os.environ.get("PAPEIS", "IONQ RGTI QBTS QUBT").split()
CUSTO = 0.001  # por troca de posição (meia volta ~0,1%)
BLOCO = 21
RNG = np.random.default_rng(7)
saida = []
p = saida.append


def baixar(intervalo, periodo):
    d = yf.download(PAPEIS, interval=intervalo, period=periodo, group_by="ticker", auto_adjust=True, progress=False)
    out = {}
    for t in PAPEIS:
        x = d[t].dropna()
        if x.index.tz is not None:
            x.index = x.index.tz_convert("America/New_York")
        out[t] = x
    return out


h1 = baixar("60m", "730d")
d1 = baixar("1d", "4y")


def vr(r, q):
    """Razão de variância: < 1 = gangorra (reversão), > 1 = tendência, 1 = acaso."""
    r = np.asarray(r)
    if len(r) < 3 * q:
        return np.nan
    rq = np.convolve(r, np.ones(q), "valid")
    return np.var(rq, ddof=1) / (q * np.var(r, ddof=1))


def contrario(close, janela, prazo=1):
    """Aposta contra o movimento dos últimos `janela` períodos (vende depois de subir, compra depois de cair).
    Devolve o retorno somado em %, com custo a cada troca de posição."""
    c = np.asarray(close)
    r = np.diff(np.log(c))
    pos = np.zeros(len(r))
    for i in range(janela, len(r)):
        mov = c[i] / c[i - janela] - 1
        pos[i] = -np.sign(mov)
    res = pos * r
    giro = np.abs(np.diff(np.concatenate([[0], pos])))
    return float(np.sum(res) - CUSTO * np.sum(giro))


def blocos(df, n):
    """Blocos de n pregões terminando no último pregão."""
    datas = sorted(set(df.index.date))
    out = []
    fim = len(datas)
    while fim - n >= 0:
        out.append(datas[fim - n:fim])
        fim -= n
    return out[::-1]


# ------------------------------------------------------------- último mês, 1 h
p("# A gangorra dos papéis quânticos no último mês")
p("")
ult = blocos(h1[PAPEIS[0]], BLOCO)[-1]
p(f"Último mês = {BLOCO} pregões, de {ult[0]} a {ult[-1]}. VR < 1 indica gangorra e VR > 1 indica tendência. "
  "O 'acaso' é o mesmo papel com as horas embaralhadas: mesma volatilidade, sem nenhuma ordem.")
p("")
p("| Papel | Mês | Sobe-e-desce do mês (soma dos movimentos ÷ resultado) | VR 1 dia | VR 3 dias | VR 3 dias no acaso (5%–95%) | Apostar contra o último dia (1 h) |")
p("|---|---|---|---|---|---|---|")
hist_vr = {}
for t in PAPEIS:
    df = h1[t]
    bl = blocos(df, BLOCO)
    vals = []
    for b in bl:
        x = df[np.isin(df.index.date, b)]["Close"]
        r = np.diff(np.log(x.values))
        vals.append(dict(ini=b[0], vr7=vr(r, 7), vr21=vr(r, 21), contra=contrario(x.values, 7),
                         ret=x.values[-1] / x.values[0] - 1))
    hist_vr[t] = pd.DataFrame(vals)
    x = df[np.isin(df.index.date, ult)]["Close"]
    r = np.diff(np.log(x.values))
    sim = [vr(RNG.permutation(r), 21) for _ in range(2000)]
    caminho = np.sum(np.abs(np.diff(df[np.isin(df.index.date, ult)].groupby(
        df[np.isin(df.index.date, ult)].index.date)["Close"].last().values)))
    liq = abs(x.values[-1] - x.values[0])
    v = hist_vr[t].iloc[-1]
    p(f"| {t} | {v.ret*100:+.0f}% | {caminho/max(liq,1e-9):.1f}× | {v.vr7:.2f} | {v.vr21:.2f} | "
      f"{np.percentile(sim,5):.2f}–{np.percentile(sim,95):.2f} | {v.contra*100:+.1f}% |")
p("")

# meses anteriores (1 h, ~2 anos)
p("## Esse mês foi diferente dos outros? (barras de 1 h, cerca de 2 anos)")
p("")
p("| Papel | Meses | VR 3 dias do último mês | Meses anteriores com VR igual ou menor | Mediana do VR 3 dias |")
p("|---|---|---|---|---|")
for t in PAPEIS:
    h = hist_vr[t]
    ultimo = h.vr21.iloc[-1]
    ant = h.vr21.iloc[:-1].dropna()
    p(f"| {t} | {len(h)} | {ultimo:.2f} | {np.mean(ant <= ultimo)*100:.0f}% | {ant.median():.2f} |")
p("")

# ------------------------------------------------------------- persistência, diário 4 anos
p("## A pergunta que importa: um mês de gangorra prevê o mês seguinte? (diário, 4 anos)")
p("")
p("Regra 'gangorra': todo dia, vende se o papel subiu nos últimos 3 pregões e compra se caiu, e troca no dia seguinte. "
  "Resultado do mês com custo. Comparo o mês seguinte a um mês em que a regra ganhou com o mês seguinte a um mês em que ela perdeu.")
p("")
lin = []
for t in PAPEIS:
    df = d1[t]
    bl = blocos(df, BLOCO)
    ant = None
    for b in bl:
        x = df[np.isin(df.index.date, b)]["Close"].values
        r = np.diff(np.log(x))
        g = contrario(x, 3)
        v = vr(r, 3) if len(r) >= 9 else np.nan
        if ant is not None:
            lin.append(dict(t=t, antes=ant[0], depois=g, vr_antes=ant[1], vr_depois=v))
        ant = (g, v)
L = pd.DataFrame(lin)
ganhou = L[L.antes > 0]
perdeu = L[L.antes <= 0]
p(f"- Meses analisados (papel × mês): {len(L)}.")
p(f"- A regra 'gangorra' no mês seguinte a um mês em que ela **ganhou**: média {ganhou.depois.mean()*100:+.1f}%, "
  f"ganhou em {np.mean(ganhou.depois > 0)*100:.0f}% dos casos (n={len(ganhou)}).")
p(f"- No mês seguinte a um mês em que ela **perdeu**: média {perdeu.depois.mean()*100:+.1f}%, "
  f"ganhou em {np.mean(perdeu.depois > 0)*100:.0f}% (n={len(perdeu)}).")
p(f"- Em todos os meses: média {L.depois.mean()*100:+.1f}%, ganhou em {np.mean(L.depois > 0)*100:.0f}%.")
p(f"- Correlação entre o resultado de um mês e o do seguinte: {L.antes.corr(L.depois):+.2f}. "
  f"Correlação do VR de um mês com o do seguinte: {L.vr_antes.corr(L.vr_depois):+.2f}.")
# acaso: embaralhar a ordem dos meses
perm = []
for _ in range(2000):
    s = RNG.permutation(L.depois.values)
    perm.append(np.mean(s[L.antes.values > 0]) - np.mean(s[L.antes.values <= 0]))
obs = ganhou.depois.mean() - perdeu.depois.mean()
p(f"- Diferença 'depois de ganhar' menos 'depois de perder': {obs*100:+.1f} pontos; chance do acaso p="
  f"{(np.sum(np.abs(perm) >= abs(obs)) + 1) / 2001:.2f}.")
p("")
p("Por papel, a regra 'gangorra' mês a mês (últimos 12 meses, do mais antigo ao mais recente):")
p("")
for t in PAPEIS:
    df = d1[t]
    bl = blocos(df, BLOCO)[-12:]
    vals = [contrario(df[np.isin(df.index.date, b)]["Close"].values, 3) for b in bl]
    p(f"- {t}: " + " ".join(f"{v*100:+.0f}%" for v in vals))
p("")

texto = "\n".join(saida)
open(os.environ.get("SAIDA", "estudo_quantico_gangorra.md"), "w").write(texto)
print("RELATORIO_INICIO"); print(texto); print("RELATORIO_FIM")
