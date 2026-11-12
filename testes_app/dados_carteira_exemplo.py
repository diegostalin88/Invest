"""Gera um data/carteira.json sintético (sem rede) para testar o app: python testes_app/dados_carteira_exemplo.py PASTA"""
import json, math, random, sys, os
from datetime import date, timedelta
random.seed(7)
ini, fim = date(2019, 1, 1), date(2026, 11, 6)
def dias(util):
    d = ini
    while d <= fim:
        if not util or d.weekday() < 5: yield d.isoformat()
        d += timedelta(days=1)
def passeio(datas, p0, mu, vol):
    v, out = p0, []
    for _ in datas: v *= math.exp(random.gauss(mu, vol)); out.append(round(v, 4))
    return out
du, dc = list(dias(True)), list(dias(False))
ativos = {'BOVA11': {'nome': 'BOVA11 (ETF do Ibovespa)', 'classe': 'acoes_br', 'datas': du, 'fech': passeio(du, 90, 0.0002, 0.015), 'desdobramentos': []},
          'IVVB11': {'nome': 'IVVB11 (ETF do S&P 500 em reais)', 'classe': 'acoes_eua', 'datas': du, 'fech': passeio(du, 120, 0.0005, 0.012), 'desdobramentos': []},
          'BTC': {'nome': 'Bitcoin (em reais)', 'classe': 'cripto', 'datas': dc, 'fech': passeio(dc, 15000, 0.0012, 0.035), 'desdobramentos': []}}
acum, v = [], 1.0
for d in du: v *= 1.0004; acum.append(round(v, 10))
meses = sorted({d[:7] for d in du})[:-1]
out = {'geradoEm': '2026-11-07T22:40:00Z', 'ativos': ativos, 'falhas': [], 'cdi': {'datas': du, 'acum': acum},
       'ipca': {'meses': meses, 'var': [round(random.uniform(0.1, 0.6), 2) for _ in meses]}, 'ptax': {'data': du[-1], 'valor': 5.4}}
os.makedirs(sys.argv[1], exist_ok=True)
json.dump(out, open(os.path.join(sys.argv[1], 'carteira.json'), 'w'), separators=(',', ':'))
print('ok', len(du), 'pregões')
