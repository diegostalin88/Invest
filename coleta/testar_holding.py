"""Teste registrado em docs/hipotese-holding-dividendos.md (07/11/2026): ETFs de dividendos contra o índice,
comprando e segurando. Só leitura. Não mexe no app nem na estratégia congelada."""
import json
import urllib.request
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf

saida = []
p = saida.append


def baixar(t, inicio="1990-01-01"):
    """Devolve (fechamento ajustado, fechamento sem ajuste, dividendos)."""
    x = yf.download(t, start=inicio, auto_adjust=False, actions=True, progress=False, threads=False)
    if isinstance(x.columns, pd.MultiIndex):
        x.columns = x.columns.get_level_values(0)
    x = x[x["Close"].notna() & (x["Close"] > 0)]
    x.index = pd.to_datetime([i.date() for i in x.index])
    x = x[~x.index.duplicated(keep="last")]
    div = x["Dividends"] if "Dividends" in x else pd.Series(0.0, index=x.index)
    return x["Adj Close"], x["Close"], div.fillna(0)


def cdi():
    partes = []
    for ini in range(2000, date.today().year + 1, 10):
        fim = min(ini + 9, date.today().year)
        url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json"
               f"&dataInicial=01/01/{ini}&dataFinal=31/12/{fim}")
        with urllib.request.urlopen(url, timeout=60) as r:
            partes += json.load(r)
    s = pd.Series({pd.to_datetime(x["data"], dayfirst=True): float(x["valor"]) / 100 for x in partes})
    return s.sort_index()


def metricas(r, caixa):
    r = r.dropna()
    c = caixa.reindex(r.index).ffill().fillna(0)
    curva = (1 + r).cumprod()
    anos = len(r) / 252
    exc = r - c
    m12 = curva.pct_change(252).min()
    return dict(total=curva.iloc[-1] - 1, cagr=curva.iloc[-1] ** (1 / anos) - 1, vol=r.std() * np.sqrt(252),
                sharpe=exc.mean() / r.std() * np.sqrt(252), mdd=(curva / curva.cummax() - 1).min(),
                pior12=m12 if pd.notna(m12) else np.nan)


def renda(fech, div):
    """Dividendos dos últimos 12 meses ÷ preço de hoje, e a média anual (dividendos do ano ÷ preço médio do ano)."""
    ult = fech.index[-1]
    d12 = div[div.index > ult - pd.Timedelta(days=365)].sum()
    atual = d12 / fech.iloc[-1]
    anos = [a for a in sorted(set(fech.index.year)) if (fech.index.year == a).sum() > 200]
    medias = [div[div.index.year == a].sum() / fech[fech.index.year == a].mean() for a in anos]
    return atual, (np.mean(medias) if medias else np.nan)


def ano_a_ano(ra, rb):
    df = pd.DataFrame({"a": ra, "b": rb}).dropna()
    g = df.groupby(df.index.year).apply(lambda x: (1 + x).prod() - 1)
    return g


def f(x, pct=True, sinal=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    if pct:
        return f"{x*100:+.1f}%" if sinal else f"{x*100:.1f}%"
    return f"{x:.2f}"


def comparar(nome, etf, regua, caixa, nome_regua):
    """etf e regua: (adj, close, div). Devolve True se passar nos 3 critérios."""
    ra = etf[0].pct_change()
    rb = regua[0].pct_change()
    ini = max(etf[0].index[0], regua[0].index[0])
    idx = ra.index.intersection(rb.index)
    idx = idx[idx > ini]
    ra, rb = ra.reindex(idx).fillna(0), rb.reindex(idx).fillna(0)
    meio = idx[len(idx) // 2]
    p(f"### {nome} contra {nome_regua}")
    p("")
    p(f"Período: {idx[0].date()} a {idx[-1].date()} ({len(idx)/252:.1f} anos). Metades divididas em {meio.date()}.")
    p("")
    p("| Período | Carteira | Retorno total | Ao ano | Volatilidade | Sharpe | Queda máxima | Pior 12 meses |")
    p("|---|---|---|---|---|---|---|---|")
    res = {}
    for per, m in (("Inteiro", slice(None)), ("1ª metade", idx < meio), ("2ª metade", idx >= meio)):
        for nm, s in ((nome, ra), (nome_regua, rb)):
            mt = metricas(s[m], caixa)
            res[(per, nm)] = mt
            p(f"| {per} | {nm} | {f(mt['total'], sinal=True)} | {f(mt['cagr'], sinal=True)} | {f(mt['vol'])} | "
              f"{f(mt['sharpe'], pct=False)} | {f(mt['mdd'])} | {f(mt['pior12'], sinal=True)} |")
    p("")
    ra_atual, ra_media = renda(etf[1], etf[2])
    rb_atual, rb_media = renda(regua[1], regua[2])
    p(f"Renda (dividendos ÷ preço): {nome} {f(ra_atual)} nos últimos 12 meses, média {f(ra_media)} ao ano; "
      f"{nome_regua} {f(rb_atual)}, média {f(rb_media)}.")
    p("")
    g = ano_a_ano(ra, rb)
    p("Ano a ano (" + nome + " / " + nome_regua + "): " +
      "; ".join(f"{a} {g.loc[a,'a']*100:+.1f} / {g.loc[a,'b']*100:+.1f}" for a in g.index) + ".")
    p("")
    c1 = all(res[(k, nome)]["sharpe"] >= res[(k, nome_regua)]["sharpe"] for k in ("Inteiro", "1ª metade", "2ª metade"))
    c2 = res[("Inteiro", nome)]["mdd"] >= res[("Inteiro", nome_regua)]["mdd"]
    c3 = res[("Inteiro", nome)]["cagr"] >= res[("Inteiro", nome_regua)]["cagr"] - 0.01
    p(f"- Critério 1 (Sharpe ≥ régua no inteiro e nas duas metades): {'PASSA' if c1 else 'FALHA'}")
    p(f"- Critério 2 (queda máxima não pior que a régua): {'PASSA' if c2 else 'FALHA'}")
    p(f"- Critério 3 (ao ano no máximo 1 ponto abaixo da régua): {'PASSA' if c3 else 'FALHA'}")
    p(f"- **{nome}: {'CANDIDATO a núcleo' if c1 and c2 and c3 else 'não substitui o índice'}**")
    p("")
    return c1 and c2 and c3


def mistura(a, b, custo=0.001):
    """50/50 rebalanceado no último pregão de cada ano. a e b: séries de fechamento ajustado."""
    ra, rb = a.pct_change(), b.pct_change()
    idx = ra.dropna().index.intersection(rb.dropna().index)
    ra, rb = ra.reindex(idx), rb.reindex(idx)
    wa, wb = 0.5, 0.5
    out = []
    anos = pd.Series(idx.year, index=idx)
    ultimo = anos != anos.shift(-1)
    for d in idx:
        va, vb = wa * (1 + ra[d]), wb * (1 + rb[d])
        tot = va + vb
        r = tot / (wa + wb) - 1
        wa, wb = va / tot, vb / tot
        if ultimo[d]:
            giro = abs(wa - 0.5) + abs(wb - 0.5)
            r -= custo * giro
            wa, wb = 0.5, 0.5
        out.append(r)
    s = pd.Series(out, index=idx)
    adj = (1 + s).cumprod()
    return adj


p("# Resultado: carteira de holding com dividendos (ETFs contra o índice)")
p("")
p("Regras e critérios em docs/hipotese-holding-dividendos.md, registrados antes de rodar.")
p("")

# ---------- Brasil ----------
p("## Brasil")
p("")
try:
    caixa_br = cdi()
    nota = ""
except Exception as ex:
    caixa_br = pd.Series(dtype=float)
    nota = f"CDI indisponível ({type(ex).__name__}); Sharpe sem desconto do caixa."
if nota:
    p(nota)
    p("")
bova = baixar("BOVA11.SA")
divo = baixar("DIVO11.SA")
p(f"Primeira cota no Yahoo: BOVA11 {bova[0].index[0].date()}, DIVO11 {divo[0].index[0].date()}.")
p("")
ok_br = comparar("DIVO11", divo, bova, caixa_br, "BOVA11")
mix = mistura(divo[0], bova[0])
mt_mix = metricas(mix.pct_change(), caixa_br)
mt_cdi = (1 + caixa_br[caixa_br.index >= mix.index[0]]).prod() - 1 if len(caixa_br) else np.nan
p(f"Só informação: 50% BOVA11 + 50% DIVO11 (rebalanceado no fim do ano): total {f(mt_mix['total'], sinal=True)}, "
  f"ao ano {f(mt_mix['cagr'], sinal=True)}, Sharpe {f(mt_mix['sharpe'], pct=False)}, queda máxima {f(mt_mix['mdd'])}. "
  f"CDI acumulado no mesmo período: {f(mt_cdi, sinal=True)}.")
p("")

# ---------- EUA ----------
p("## EUA")
p("")
irx_adj, _, _ = baixar("^IRX")
caixa_us = irx_adj / 100 / 252
spy = baixar("SPY")
aprovados = []
for t in ("SCHD", "VIG", "DVY", "SDY", "HDV", "NOBL"):
    try:
        e = baixar(t)
        if comparar(t, e, spy, caixa_us, "SPY"):
            aprovados.append(t)
    except Exception as ex:
        p(f"### {t}: falhou ao baixar ({type(ex).__name__}: {ex})")
        p("")

p("## Veredito")
p("")
p(f"- Brasil: DIVO11 {'é CANDIDATO a núcleo' if ok_br else 'não substitui o BOVA11 no núcleo'}.")
p(f"- EUA: {', '.join(aprovados) + ' candidato(s) (precisa confirmar 12 meses para frente; 6 testados)' if aprovados else 'nenhum dos 6 ETFs substitui o SPY no núcleo'}.")
p("")

texto = "\n".join(saida)
print(texto)
open("estudo_holding.md", "w").write(texto)
