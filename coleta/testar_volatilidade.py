"""Teste registrado em docs/hipotese-volatilidade.md (07/11/2026): controle da exposição pela volatilidade.
Só leitura. Não mexe no app nem na estratégia congelada."""
import json
import urllib.request
from datetime import date
import numpy as np
import pandas as pd
import yfinance as yf

CESTA = ("IONQ RGTI QBTS QUBT PLTR SOUN BBAI RKLB ASTS ACHR JOBY SMCI MSTR COIN HOOD UPST AFRM MARA RIOT "
         "LUNR OKLO SMR PLUG FCEL LCID RIVN CHPT BYND SPCE OPEN SOFI U PATH AI").split()
saida = []
p = saida.append


def fech(t, inicio):
    x = yf.download(t, start=inicio, auto_adjust=True, progress=False, threads=False)
    if isinstance(x.columns, pd.MultiIndex):
        x.columns = x.columns.get_level_values(0)
    s = x["Close"].dropna()
    s.index = pd.to_datetime([i.date() for i in s.index])
    return s


def cdi():
    """CDI diário (% ao dia) do BCB, em blocos de 10 anos (limite da API)."""
    partes = []
    for ini in range(1995, date.today().year + 1, 10):
        fim = min(ini + 9, date.today().year)
        url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json"
               f"&dataInicial=01/01/{ini}&dataFinal=31/12/{fim}")
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        partes += d
    s = pd.Series({pd.to_datetime(x["data"], dayfirst=True): float(x["valor"]) / 100 for x in partes})
    return s.sort_index()


def metricas(r, caixa):
    r = r.dropna()
    c = caixa.reindex(r.index).fillna(0)
    curva = (1 + r).cumprod()
    anos = len(r) / 252
    exc = r - c
    return dict(cagr=curva.iloc[-1] ** (1 / anos) - 1, vol=r.std() * np.sqrt(252),
                sharpe=exc.mean() / r.std() * np.sqrt(252), mdd=(curva / curva.cummax() - 1).min())


def simular(preco, caixa, custo):
    r = preco.pct_change()
    vol = r.rolling(21).std() * np.sqrt(252)
    alvo = vol.expanding(min_periods=252).median()
    e = (alvo / vol).clip(0, 1)
    sexta = pd.Series(e.index.dayofweek == 4, index=e.index)
    e = e.where(sexta).ffill().shift(1)
    ok = e.notna()
    r, e = r[ok], e[ok]
    c = caixa.reindex(r.index).ffill().fillna(0)
    giro = e.diff().abs().fillna(e.iloc[0])
    regra = e * r + (1 - e) * c - custo * giro
    return r, regra, e, c


def bloco(nome, preco, caixa, nota=""):
    p(f"## {nome}{nota}")
    p("")
    r, regra, e, c = simular(preco, caixa, 0.001)
    _, regra2, _, _ = simular(preco, caixa, 0.002)
    p(f"Período: {r.index[0].date()} a {r.index[-1].date()}. Exposição média da regra: {e.mean()*100:.0f}% "
      f"(mínima {e.min()*100:.0f}%). Exposição mudou em {int((e.diff().abs() > 0.001).sum())} semanas.")
    p("")
    p("| Período | Carteira | Retorno ao ano | Volatilidade | Sharpe | Queda máxima |")
    p("|---|---|---|---|---|---|")
    meio = r.index[len(r) // 2]
    veredito = {}
    for per, m in (("Inteiro", slice(None)), ("1ª metade", r.index < meio), ("2ª metade", r.index >= meio)):
        rr, rg, ee, cc = r[m], regra[m], e[m], c[m]
        fixa = ee.mean() * rr + (1 - ee.mean()) * cc
        res = {}
        for nm, s in (("Comprar e segurar", rr), ("Regra de volatilidade", rg), (f"Exposição fixa {ee.mean()*100:.0f}%", fixa)):
            mt = metricas(s, cc)
            res[nm.split(" ")[0]] = mt
            p(f"| {per} | {nm} | {mt['cagr']*100:+.1f}% | {mt['vol']*100:.1f}% | {mt['sharpe']:.2f} | {mt['mdd']*100:.0f}% |")
        veredito[per] = res
    mt2 = metricas(regra2, c)
    p(f"| Inteiro | Regra com custo dobrado | {mt2['cagr']*100:+.1f}% | {mt2['vol']*100:.1f}% | {mt2['sharpe']:.2f} | {mt2['mdd']*100:.0f}% |")
    p("")
    c1 = all(veredito[k]["Regra"]["sharpe"] > veredito[k]["Comprar"]["sharpe"] for k in veredito)
    c2 = veredito["Inteiro"]["Regra"]["mdd"] >= 0.8 * veredito["Inteiro"]["Exposição"]["mdd"]
    c3 = mt2["sharpe"] > veredito["Inteiro"]["Comprar"]["sharpe"]
    p(f"- Critério 1 (Sharpe maior que segurar no inteiro e nas duas metades): {'PASSA' if c1 else 'FALHA'}")
    p(f"- Critério 2 (queda máxima ≥20% menor que a exposição fixa de mesma média): {'PASSA' if c2 else 'FALHA'} "
      f"({veredito['Inteiro']['Regra']['mdd']*100:.0f}% contra {veredito['Inteiro']['Exposição']['mdd']*100:.0f}%)")
    p(f"- Critério 3 (critério 1 no inteiro com custo dobrado): {'PASSA' if c3 else 'FALHA'}")
    p("")
    return c1 and c2 and c3


p("# Resultado: controle da exposição pela volatilidade")
p("")
p("Regras e critérios em docs/hipotese-volatilidade.md, registrados antes de rodar.")
p("")
irx = fech("^IRX", "1990-01-01") / 100 / 252
spy = fech("SPY", "1993-01-01")
ok_us = bloco("EUA: SPY", spy, irx)
nota = ""
try:
    caixa_br = cdi()
except Exception as ex:  # registrado: sem CDI, caixa rende zero
    caixa_br = pd.Series(dtype=float)
    nota = f" (CDI indisponível: {type(ex).__name__}; caixa rende zero)"
ibov = fech("^BVSP", "1995-01-01")
ok_br = bloco("Brasil: Ibovespa", ibov, caixa_br, nota)

# cesta (informação)
precos = pd.DataFrame({t: fech(t, "2018-01-01") for t in CESTA})
rc = precos.pct_change().mean(axis=1, skipna=True).dropna()
cesta = (1 + rc).cumprod()
bloco("Só informação: cesta de 34 papéis voláteis (viés de sobrevivência)", cesta, irx)

p(f"**Veredito: {'APROVADA' if ok_us and ok_br else 'REPROVADA'}** (EUA {'passa' if ok_us else 'falha'}, Brasil {'passa' if ok_br else 'falha'}).")
texto = "\n".join(saida)
open("estudo_volatilidade.md", "w").write(texto)
print("RELATORIO_INICIO"); print(texto); print("RELATORIO_FIM")
