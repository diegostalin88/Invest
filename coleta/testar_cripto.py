#!/usr/bin/env python3
"""Hipótese K: estratégias em cripto (ver docs/hipotese-cripto.md).

Baixa candles diários públicos da Binance (inclusive moedas delistadas),
PTAX e CDI do BCB, BOVA11/IVVB11 do Yahoo, e roda as regras registradas.

Uso:  python testar_cripto.py --saida resultado_cripto
      python testar_cripto.py --sintetico   (só confere o código, dados falsos)
"""
import argparse, io, json, os, re, sys, time, zipfile, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DADOS = "https://data.binance.vision"
INICIO = pd.Timestamp("2018-01-01")
MEIO = pd.Timestamp("2022-01-01")
CUSTO = 0.0015
ESTAVEIS = {"USDC", "BUSD", "TUSD", "FDUSD", "DAI", "PAX", "USDP", "USDS", "USDSB",
            "SUSD", "UST", "USTC", "EUR", "GBP", "AUD", "TRY", "BRL", "RUB", "UAH",
            "NGN", "BIDR", "IDRT", "BKRW", "BVND", "ZAR", "AEUR", "EURI", "PAXG",
            "XUSD", "USD1", "RLUSD", "USDE", "BFUSD", "WBTC", "WBETH", "BETH"}
ALAV = re.compile(r"(UP|DOWN|BULL|BEAR)$")
N_UNIV, N_TOP, JAN_MOM = 30, 5, 84


def http(url, tent=4):
    import urllib.request, urllib.parse; url = urllib.parse.quote(url, safe=":/?&=%+,")
    for i in range(tent):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            if getattr(e, "code", None) == 404:
                return None
            if i == tent - 1:
                raise
            time.sleep(2 ** (i + 1))


def listar_s3(prefixo):
    itens, marcador = [], ""
    while True:
        url = f"{S3}?prefix={prefixo}&delimiter=/" + (f"&marker={marcador}" if marcador else "")
        xml = http(url).decode()
        pref = re.findall(r"<Prefix>([^<]+)</Prefix>", xml)[1:]
        chaves = re.findall(r"<Key>([^<]+)</Key>", xml)
        itens += pref + chaves
        if "<IsTruncated>true</IsTruncated>" not in xml:
            return itens
        marcador = re.findall(r"<NextMarker>([^<]+)</NextMarker>", xml) or [(pref + chaves)[-1]]
        marcador = marcador[0]


def baixar_simbolo(sym, cache):
    arq = os.path.join(cache, f"{sym}.csv")
    if os.path.exists(arq):
        return sym, pd.read_csv(arq, index_col=0, parse_dates=True)
    chaves = [k for k in listar_s3(f"data/spot/monthly/klines/{sym}/1d/") if k.endswith(".zip")]
    partes = []
    for k in chaves:
        b = http(f"{DADOS}/{k}")
        if not b:
            continue
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            txt = z.read(z.namelist()[0]).decode()
        df = pd.read_csv(io.StringIO(txt), header=None)
        if not str(df.iloc[0, 0]).isdigit():
            df = df.iloc[1:]
        partes.append(df.iloc[:, [0, 4, 7]].astype(float))
    if not partes:
        return sym, None
    df = pd.concat(partes)
    ts = df[0].where(df[0] < 1e14, df[0] / 1000)  # 2025+: microssegundos
    out = pd.DataFrame({"close": df[4].values, "qvol": df[7].values},
                       index=pd.to_datetime(ts.values, unit="ms").normalize())
    out = out[~out.index.duplicated()].sort_index()
    out.to_csv(arq)
    return sym, out


def carregar_cripto(cache):
    os.makedirs(cache, exist_ok=True)
    pref = listar_s3("data/spot/monthly/klines/")
    syms = sorted({p.rstrip("/").split("/")[-1] for p in pref})
    syms = [s for s in syms if s.endswith("USDT")]
    syms = [s for s in syms if s[:-4] not in ESTAVEIS and not ALAV.search(s[:-4])]
    print(f"{len(syms)} pares USDT", flush=True)
    with ThreadPoolExecutor(16) as ex:
        res = dict(ex.map(lambda s: baixar_simbolo(s, cache), syms))
    res = {s: d for s, d in res.items() if d is not None and len(d) > 30}
    close = pd.DataFrame({s: d["close"] for s, d in res.items()})
    qvol = pd.DataFrame({s: d["qvol"] for s, d in res.items()})
    return close, qvol


def bcb(serie, ini="01/01/2017"):
    fim = dt.date.today().strftime("%d/%m/%Y")
    partes = []
    # API do BCB limita a 10 anos por pedido
    for a in range(2017, dt.date.today().year + 1, 5):
        i, f = f"01/01/{a}", f"31/12/{min(a + 4, dt.date.today().year)}"
        b = http(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json&dataInicial={i}&dataFinal={f}")
        partes += json.loads(b)
    s = pd.Series({pd.to_datetime(x["data"], dayfirst=True): float(x["valor"]) for x in partes})
    return s.sort_index()


def yahoo(tk):
    """Fechamento ajustado pelo yfinance (mesma biblioteca e mesmo ajuste da coleta diária, coleta/indices.py)."""
    import yfinance as yf
    h = yf.Ticker(tk).history(start="2017-01-01", auto_adjust=True)
    s = h["Close"].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated()].dropna()


def sintetico():
    rng = np.random.default_rng(1)
    dias = pd.date_range("2017-08-17", "2026-10-31")
    n = 60
    ret = rng.normal(0.0005, 0.04, (len(dias), n))
    close = pd.DataFrame(100 * np.exp(np.cumsum(ret, 0)), index=dias, columns=[f"C{i}USDT" for i in range(n)])
    close = close.rename(columns={"C0USDT": "BTCUSDT", "C1USDT": "ETHUSDT"})
    for i, c in enumerate(close.columns[2:]):
        a = rng.integers(0, len(dias) - 400)
        close.iloc[:a, i + 2] = np.nan
        if i % 5 == 0:
            close.iloc[a + 300:, i + 2] = np.nan
    qvol = close * rng.lognormal(10, 1, close.shape)
    dias_u = pd.bdate_range("2017-01-01", "2026-10-31")
    cdi = pd.Series(0.04, index=dias_u)
    ptax = pd.Series(np.exp(np.cumsum(rng.normal(0.0001, 0.008, len(dias_u)))) * 3.3, index=dias_u)
    bova = pd.Series(np.exp(np.cumsum(rng.normal(0.0003, 0.015, len(dias_u)))) * 60, index=dias_u)
    ivvb = pd.Series(np.exp(np.cumsum(rng.normal(0.0004, 0.012, len(dias_u)))) * 90, index=dias_u)
    return close, qvol, cdi, ptax, bova, ivvb


# ---------- motor ----------

def metr(r, rf):
    """r e rf: retornos diários (calendário) em reais."""
    r, rf = r.dropna(), rf.reindex(r.index).fillna(0)
    if len(r) < 30:
        return {}
    ex = r - rf
    eq = (1 + r).cumprod()
    anos = len(r) / 365.25
    return {"retorno_total": eq.iloc[-1] - 1,
            "ao_ano": eq.iloc[-1] ** (1 / anos) - 1,
            "sharpe": ex.mean() / ex.std() * np.sqrt(365) if ex.std() > 0 else 0.0,
            "queda_max": (eq / eq.cummax() - 1).min(),
            "cdi_total": (1 + rf).prod() - 1}


def timing(pos, r_ativo, rf, custo):
    """pos: 0/1 decidido no fechamento de t, vale para o retorno de t+1."""
    p = pos.shift(1).fillna(0)
    giro = p.diff().abs().fillna(p.abs())
    return p * r_ativo + (1 - p) * rf - giro * custo, p


def rotacao(pesos, r_brl, rf, custo, semanas=None):
    """pesos: alvo decidido no fechamento de t (vale a partir de t+1).
    Pesos derivam com o preço entre rebalanceamentos; custo sobre o giro."""
    alvo = pesos.shift(1).fillna(0).values
    r = r_brl.reindex(columns=pesos.columns).fillna(0).values
    rfv = rf.reindex(pesos.index).fillna(0).values
    reb = np.zeros(len(alvo), bool)
    reb[1:] = np.abs(np.diff(alvo, axis=0)).sum(1) > 1e-12
    if semanas is not None:
        idx = pesos.index
        reb |= np.array([(d - pd.Timedelta(days=1)) in semanas for d in idx])
    w = np.zeros(alvo.shape[1]); out = np.zeros(len(alvo))
    for t in range(len(alvo)):
        c = 0.0
        if reb[t] or t == 0:
            c = np.abs(alvo[t] - w).sum() * custo
            w = alvo[t].copy()
        caixa = 1 - w.sum()
        novo = w * (1 + r[t])
        tot = novo.sum() + caixa * (1 + rfv[t])
        out[t] = tot - 1 - c
        w = novo / tot
    return pd.Series(out, index=pesos.index)


class Universo:
    def __init__(self, close_usd, qvol, dias, semanas):
        cols = close_usd.columns
        hist = close_usd.notna().cumsum()
        vol30 = qvol.rolling(30, min_periods=20).mean()
        self.mom = (close_usd / close_usd.ffill().shift(JAN_MOM) - 1).loc[dias].values
        self.vivo = close_usd.loc[dias].notna().values
        self.dias, self.cols = dias, cols
        self.sem = np.array([d in semanas for d in dias])
        self.elig = {}
        for t in np.where(self.sem)[0]:
            d = dias[t]
            v = vol30.loc[d][(hist.loc[d] >= 90) & close_usd.loc[d].notna()].nlargest(N_UNIV)
            self.elig[t] = np.array([cols.get_loc(c) for c in v.index], int)


def pesos_momento(U, filtro=None, acaso_rng=None, qtd=None):
    W = np.zeros((len(U.dias), len(U.cols)))
    atual = np.zeros(len(U.cols)); n_sem, sumicos = {}, 0
    prev_sem, mantidas = None, []
    f = filtro.reindex(U.dias).fillna(False).values if filtro is not None else None
    for t in range(len(U.dias)):
        if U.sem[t]:
            prev = list(np.where(atual > 0)[0])
            atual = np.zeros(len(U.cols)); el = U.elig[t]
            if f is None or f[t]:
                if acaso_rng is not None:
                    # acaso com o mesmo giro: mantém cada moeda anterior com a
                    # mesma taxa de permanência da regra, completa ao acaso
                    k, manter = qtd.get(t, 0), qtd["permanencia"]
                    ant = [c for c in prev if c in set(el) and acaso_rng.random() < manter][:k]
                    resto = np.setdiff1d(el, ant)
                    novos = acaso_rng.choice(resto, max(0, min(k - len(ant), len(resto))), replace=False)
                    atual[np.r_[np.array(ant, int), novos].astype(int)] = 1 / N_TOP if k else 0
                else:
                    m = U.mom[t, el]
                    ok = ~np.isnan(m) & (m > 0)
                    cand = el[ok][np.argsort(-m[ok])][:N_TOP]
                    atual[cand] = 1 / N_TOP
            n_sem[t] = int((atual > 0).sum())
            if prev_sem:
                mantidas.append(len(set(prev_sem) & set(np.where(atual > 0)[0])) / len(prev_sem))
            prev_sem = list(np.where(atual > 0)[0]) if n_sem[t] else None
        sumiu = (atual > 0) & ~U.vivo[t]
        if sumiu.any():
            sumicos += int(sumiu.sum()); atual[sumiu] = 0
        W[t] = atual
    n_sem["permanencia"] = float(np.mean(mantidas)) if mantidas else 0.0
    return pd.DataFrame(W, index=U.dias, columns=U.cols), n_sem, sumicos


def cesta(U):
    W = np.zeros((len(U.dias), len(U.cols))); atual = np.zeros(len(U.cols))
    for t in range(len(U.dias)):
        if U.sem[t]:
            atual = np.zeros(len(U.cols)); atual[U.elig[t]] = 1 / len(U.elig[t])
        atual[(atual > 0) & ~U.vivo[t]] = 0
        W[t] = atual
    return pd.DataFrame(W, index=U.dias, columns=U.cols)


def holding(rb, ri, rf, rbtc, pos_btc, custo, cripto=0.0):
    """1/3 BOVA, 1/3 IVVB, 1/3 CDI (x 1-cripto) + cripto em BTC; rebalanceio trimestral."""
    alvo = np.array([(1 - cripto) / 3] * 3 + [cripto])
    r = pd.concat([rb, ri, rf, rbtc], axis=1).fillna(0).values
    p = pos_btc.shift(1).fillna(0).values if pos_btc is not None else np.ones(len(r))
    w = alvo.copy()
    out = np.zeros(len(r))
    trimestre = None
    idx = rb.index
    for t in range(len(r)):
        rr = r[t].copy()
        rr[3] = p[t] * r[t, 3] + (1 - p[t]) * r[t, 2]
        if pos_btc is not None and t > 0 and p[t] != p[t - 1]:
            rr[3] -= custo
        novo = w * (1 + rr)
        out[t] = novo.sum() - 1
        w = novo / novo.sum()
        q = (idx[t].year, (idx[t].month - 1) // 3)
        if q != trimestre:
            if trimestre is not None:
                out[t] -= np.abs(w - alvo)[[0, 1, 3]].sum() * custo
                w = alvo.copy()
            trimestre = q
    return pd.Series(out, index=idx)


def rodar(close_usd, qvol, cdi, ptax, bova, ivvb, saida, n_acaso_t=1000, n_acaso_m=500):
    fim = close_usd.index.max()
    dias_all = pd.date_range(close_usd.index.min(), fim)
    close_usd = close_usd.reindex(dias_all)
    qvol = qvol.reindex(dias_all).fillna(0)
    # CDI: % ao dia nos dias úteis, 0 nos demais
    rf = (cdi.reindex(dias_all).fillna(0) / 100)
    ptax_d = ptax.reindex(dias_all).ffill()
    usd_brl_r = ptax_d.pct_change().fillna(0)
    # retorno em reais; dia sem preço = 0 (posição parada)
    r_usd = close_usd.ffill().pct_change(fill_method=None).fillna(0)
    r_usd = r_usd.where(close_usd.notna() | close_usd.shift(1).notna(), 0)
    r_brl = (1 + r_usd).mul(1 + usd_brl_r, axis=0) - 1
    rb = bova.reindex(dias_all).ffill().pct_change().fillna(0)
    ri = ivvb.reindex(dias_all).ffill().pct_change().fillna(0)

    dias = dias_all[dias_all >= INICIO]
    semanas = set(dias[dias.weekday == 0])
    btc, eth = close_usd["BTCUSDT"].ffill(), close_usd["ETHUSDT"].ffill()
    sinais = {
        "T1": (btc > btc.rolling(200).mean()).astype(float),
        "T2": (eth > eth.rolling(200, min_periods=200).mean()).astype(float),
        "T3": (btc / btc.shift(90) - 1 > 0).astype(float),
    }
    ativo_de = {"T1": "BTCUSDT", "T2": "ETHUSDT", "T3": "BTCUSDT"}
    ref_de = {"T1": "R1", "T2": "R2", "T3": "R1", "M1": "R3", "M2": "R3"}

    def corta(s):
        return s.loc[dias]

    U = Universo(close_usd, qvol, dias, semanas)
    w_cesta = cesta(U)
    w1, n1, sum1 = pesos_momento(U)
    filtro = sinais["T1"].astype(bool)
    w2, n2, sum2 = pesos_momento(U, filtro=filtro)
    series = {}
    for custo_nome, c in (("normal", CUSTO), ("dobrado", 2 * CUSTO)):
        S = {}
        S["R1"] = corta(r_brl["BTCUSDT"]).copy(); S["R1"].iloc[0] -= c
        S["R2"] = corta(r_brl["ETHUSDT"]).copy(); S["R2"].iloc[0] -= c
        S["R3"] = rotacao(w_cesta, corta(r_brl), corta(rf), c, semanas)
        for k, sig in sinais.items():
            S[k], _ = timing(corta(sig), corta(r_brl[ativo_de[k]]), corta(rf), c)
        S["M1"] = rotacao(w1, corta(r_brl), corta(rf), c, semanas)
        S["M2"] = rotacao(w2, corta(r_brl), corta(rf), c, semanas)
        S["P0"] = holding(corta(rb), corta(ri), corta(rf), corta(r_brl["BTCUSDT"]), None, c, 0)
        S["P1"] = holding(corta(rb), corta(ri), corta(rf), corta(r_brl["BTCUSDT"]), None, c, 0.05)
        S["P2"] = holding(corta(rb), corta(ri), corta(rf), corta(r_brl["BTCUSDT"]), corta(sinais["T1"]), c, 0.05)
        series[custo_nome] = S
    rfd = corta(rf)

    def tab(S):
        out = {}
        for k, s in S.items():
            out[k] = {"inteiro": metr(s, rfd), "metade1": metr(s[s.index < MEIO], rfd),
                      "metade2": metr(s[s.index >= MEIO], rfd)}
        return out

    T = {n: tab(S) for n, S in series.items()}

    # ---- acaso (custo dobrado) ----
    rng = np.random.default_rng(42)
    acaso = {}
    c2 = 2 * CUSTO
    for k, sig in sinais.items():
        p = corta(sig).values
        n = len(p)
        desl = rng.choice(np.arange(30, n - 30), size=min(n_acaso_t, n - 60), replace=False)
        sh = []
        for d in desl:
            ps = pd.Series(np.roll(p, d), index=dias)
            r, _ = timing(ps, corta(r_brl[ativo_de[k]]), rfd, c2)
            sh.append(metr(r, rfd)["sharpe"])
        acaso[k] = sh
    for k, (nq, filt) in {"M1": (n1, None), "M2": (n2, filtro)}.items():
        sh = []
        for i in range(n_acaso_m):
            w, _, _ = pesos_momento(U, acaso_rng=rng, qtd=nq)
            sh.append(metr(rotacao(w, corta(r_brl), rfd, c2, semanas), rfd)["sharpe"])
            if i % 50 == 0:
                print(f"acaso {k} {i}/{n_acaso_m}", flush=True)
        acaso[k] = sh

    # ---- veredito ----
    ver = {}
    for k in ["T1", "T2", "T3", "M1", "M2"]:
        refs = [ref_de[k]] + (["R1"] if k.startswith("M") else [])
        a = T["normal"][k]
        c1 = all(a[p]["sharpe"] > T["normal"][r][p]["sharpe"] for r in refs for p in ("inteiro", "metade1", "metade2"))
        c2_ = all(a["inteiro"]["queda_max"] >= T["normal"][r]["inteiro"]["queda_max"] for r in refs)
        p95 = float(np.percentile(acaso[k], 95))
        sd = T["dobrado"][k]["inteiro"]["sharpe"]
        pct = float((np.array(acaso[k]) < sd).mean() * 100)
        c3 = sd > p95
        c4 = a["inteiro"]["retorno_total"] > a["inteiro"]["cdi_total"]
        ver[k] = {"c1_sharpe_todas_metades": c1, "c2_queda": c2_, "c3_acaso": c3,
                  "percentil_acaso": pct, "p95_acaso": p95, "c4_cdi": c4,
                  "aprovada": bool(c1 and c2_ and c3 and c4)}
    for k in ["P1", "P2"]:
        a, b = T["normal"][k], T["normal"]["P0"]
        c1 = all(a[p]["sharpe"] > b[p]["sharpe"] for p in ("inteiro", "metade1", "metade2"))
        c2_ = a["inteiro"]["queda_max"] >= b["inteiro"]["queda_max"] - 0.02
        ver[k] = {"c1_sharpe_todas_metades": c1, "c2_queda_ate_2pp": c2_, "aprovada": bool(c1 and c2_)}

    res = {"gerado": dt.datetime.now(dt.timezone.utc).isoformat(), "periodo": [str(dias[0].date()), str(dias[-1].date())],
           "n_moedas_base": int(close_usd.shape[1]),
           "n_moedas_delistadas": int((close_usd.apply(lambda s: s.last_valid_index()) < fim - pd.Timedelta(days=10)).sum()),
           "saidas_por_sumico_M1": sum1, "saidas_por_sumico_M2": sum2,
           "custo_lado": CUSTO, "metricas": T, "veredito": ver,
           "exposicao": {k: float(corta(s).mean()) for k, s in sinais.items()}}
    os.makedirs(saida, exist_ok=True)
    with open(os.path.join(saida, "resultado.json"), "w") as f:
        json.dump(res, f, indent=1, default=float)
    linhas = ["| Estratégia | a.a. | Sharpe | Sharpe 18–21 | Sharpe 22–fim | Queda máx | Aprovada |", "|---|---|---|---|---|---|---|"]
    for k, m in T["normal"].items():
        i = m["inteiro"]
        ap = ver.get(k, {}).get("aprovada", "ref")
        linhas.append(f"| {k} | {i['ao_ano']:.1%} | {i['sharpe']:.2f} | {m['metade1'].get('sharpe', 0):.2f} | {m['metade2'].get('sharpe', 0):.2f} | {i['queda_max']:.0%} | {ap} |")
    cdi_aa = (1 + rfd).prod() ** (365.25 / len(rfd)) - 1
    linhas.append(f"\nCDI no período: {cdi_aa:.1%} a.a.  Moedas na base: {res['n_moedas_base']} (delistadas: {res['n_moedas_delistadas']})")
    for k, v in ver.items():
        linhas.append(f"- {k}: " + ", ".join(f"{a}={b if not isinstance(b, float) else round(b, 2)}" for a, b in v.items()))
    md = "\n".join(linhas)
    with open(os.path.join(saida, "resumo.md"), "w") as f:
        f.write(md + "\n")
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## Hipótese K: cripto\n\n" + md + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="resultado_cripto")
    ap.add_argument("--cache", default="cache_cripto")
    ap.add_argument("--sintetico", action="store_true")
    a = ap.parse_args()
    if a.sintetico:
        close, qvol, cdi, ptax, bova, ivvb = sintetico()
        rodar(close, qvol, cdi, ptax, bova, ivvb, a.saida, n_acaso_t=20, n_acaso_m=3)
        return
    close, qvol = carregar_cripto(a.cache)
    ultimo_mes = pd.Timestamp(dt.date.today().replace(day=1)) - pd.Timedelta(days=1)
    close, qvol = close.loc[:ultimo_mes], qvol.loc[:ultimo_mes]
    cdi, ptax = bcb(12), bcb(1)
    bova, ivvb = yahoo("BOVA11.SA"), yahoo("IVVB11.SA")
    rodar(close, qvol, cdi, ptax, bova, ivvb, a.saida)


if __name__ == "__main__":
    main()
