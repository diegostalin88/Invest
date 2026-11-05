"""Preços longos (desde 2009) do Yahoo para os estudos de fundamentos (só leitura).

Grava {ticker: {dates, adj, close, vol, splits: [[data, razão], ...]}}:
  adj   = fechamento ajustado por proventos e desdobramentos (retorno total);
  close = fechamento ajustado só por desdobramentos (com as datas de desdobramento, dá o valor de mercado);
  vol   = volume ajustado por desdobramentos (close × vol = volume financeiro real).
Uso: python coleta/precos_longos.py balancos_us.json saida.json [--extra SPY]
"""
import argparse
import json
import sys

import yfinance as yf


def baixar(tickers, inicio='2009-01-01'):
    out = {}
    for k in range(0, len(tickers), 100):
        lote = tickers[k:k + 100]
        df = yf.download([t.replace('.', '-') for t in lote], start=inicio, auto_adjust=False, actions=True,
                         group_by='ticker', threads=True, progress=False)
        for t in lote:
            y = t.replace('.', '-')
            try:
                d = df[y] if len(lote) > 1 else df
                d = d.dropna(subset=['Close', 'Adj Close'])
            except (KeyError, TypeError):
                continue
            if len(d) < 250:
                continue
            sp = d['Stock Splits'] if 'Stock Splits' in d else None
            out[t] = {
                'dates': [x.strftime('%Y-%m-%d') for x in d.index],
                'adj': [round(float(x), 4) for x in d['Adj Close']],
                'close': [round(float(x), 4) for x in d['Close']],
                'vol': [int(x) if x == x else 0 for x in d['Volume']],
                'splits': [[i.strftime('%Y-%m-%d'), float(r)] for i, r in sp.items() if r and r > 0] if sp is not None else [],
            }
        print(f'  preços: {min(k + 100, len(tickers))}/{len(tickers)} ({len(out)} com dados)', flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('balancos')
    ap.add_argument('saida')
    ap.add_argument('--extra', default='SPY')
    a = ap.parse_args(argv)
    tickers = sorted(json.load(open(a.balancos)))
    out = baixar(tickers + [x for x in a.extra.split(',') if x])
    json.dump(out, open(a.saida, 'w'), separators=(',', ':'))
    print(f'Preços longos: {len(out)} de {len(tickers) + 1}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
