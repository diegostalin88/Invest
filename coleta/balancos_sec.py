"""Balanços trimestrais históricos dos EUA (XBRL da SEC), com a data em que cada número ficou público.

Para cada papel: trimestres de 3 meses (lucro líquido, receita, lucro bruto, lucro por ação), fotos de balanço
(ativo, patrimônio, passivo, ações em circulação) e as datas de divulgação de resultado (8-K item 2.02).
Cada número guarda o 'filed' do PRIMEIRO formulário que o trouxe: é o que se sabia naquele dia (sem
reapresentações posteriores). O 4º trimestre é o ano (10-K) menos os três primeiros, publicado na data do 10-K.

Só leitura; base das hipóteses C e D (docs/hipotese-fundamentos.md) e, depois, do histórico de balanços no app.
Uso: python coleta/balancos_sec.py site/data saida.json [--limite 1000]   (precisa de SEC_USER_AGENT)
"""
import argparse
import json
import os
import sys
from datetime import date

import fetch_all as fa
from datas_balanco import datas_de_balanco

FORMS = {'10-Q', '10-K', '10-Q/A', '10-K/A', '10-KT', '10-QT'}
FLUXOS = {  # campo: etiquetas em ordem de preferência (unidade USD, exceto eps)
    'ni': ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic'],
    'rev': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet',
            'RevenueFromContractWithCustomerIncludingAssessedTax'],
    'gp': ['GrossProfit'],
    'cor': ['CostOfRevenue', 'CostOfGoodsAndServicesSold', 'CostOfGoodsSold'],
    'eps': ['EarningsPerShareDiluted', 'EarningsPerShareBasic'],
}
FOTOS = {
    'ativo': ['Assets'],
    'pl': ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
    'passivo': ['Liabilities'],
}


def _dias(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def registros(facts, etiquetas, unidade='USD', ns='us-gaap'):
    """Registros da 1ª etiqueta que existir: {(start|None, end): (val, filed)} com o filed mais antigo."""
    base = facts.get('facts', {}).get(ns, {})
    for tag in etiquetas:
        unidades = (base.get(tag) or {}).get('units', {})
        lista = unidades.get(unidade)
        if not lista:
            continue
        out = {}
        for u in lista:
            if u.get('form') not in FORMS or u.get('val') is None or not u.get('end') or not u.get('filed'):
                continue
            k = (u.get('start'), u['end'])
            if k not in out or u['filed'] < out[k][1]:
                out[k] = (u['val'], u['filed'])
        if out:
            return out
    return {}


def trimestres(regs):
    """{end: {'v', 'filed', 'start'}} com trimestres de 3 meses; 4º trimestre = ano − 3 trimestres."""
    q = {}
    for (s, e), (v, f) in regs.items():
        if s and 80 <= _dias(s, e) <= 100:
            if e not in q or f < q[e]['filed']:
                q[e] = {'v': v, 'filed': f, 'start': s}
    for (s, e), (v, f) in regs.items():
        if not s or not (350 <= _dias(s, e) <= 380) or e in q:
            continue
        dentro = sorted([x for x in q.items() if x[1]['start'] >= s and x[0] < e], key=lambda x: x[0])
        if len(dentro) != 3:
            continue
        ultimo_fim = dentro[-1][0]
        if not (80 <= _dias(ultimo_fim, e) <= 100):
            continue
        q[e] = {'v': v - sum(x[1]['v'] for x in dentro), 'filed': max([f] + [x[1]['filed'] for x in dentro]),
                'start': ultimo_fim, 'derivado': True}
    return q


def fotos(regs):
    out = {}
    for (s, e), (v, f) in regs.items():
        if s is None and (e not in out or f < out[e]['filed']):
            out[e] = {'v': v, 'filed': f}
    return out


def extrair(facts):
    """Transforma o companyfacts numa estrutura compacta e sem olhar o futuro."""
    tri = {k: trimestres(registros(facts, tags, 'USD/shares' if k == 'eps' else 'USD')) for k, tags in FLUXOS.items()}
    # lucro bruto: etiqueta própria ou receita − custo do mesmo trimestre (dois números publicados, nada estimado)
    for e, r in tri['rev'].items():
        if e not in tri['gp'] and e in tri['cor']:
            tri['gp'][e] = {'v': r['v'] - tri['cor'][e]['v'], 'filed': max(r['filed'], tri['cor'][e]['filed'])}
    fins = sorted(set(tri['ni']) | set(tri['rev']))
    trim = []
    for e in fins:
        linha = {'end': e}
        filed = []
        for k in ('ni', 'rev', 'gp', 'eps'):
            if e in tri[k]:
                linha[k] = tri[k][e]['v']
                filed.append(tri[k][e]['filed'])
        linha['filed'] = min(filed)  # o resultado do trimestre sai junto; o mais antigo é o 1º formulário
        trim.append(linha)
    fot = {k: fotos(registros(facts, tags)) for k, tags in FOTOS.items()}
    acoes = fotos(registros(facts, ['EntityCommonStockSharesOutstanding'], 'shares', 'dei')) or \
        fotos(registros(facts, ['CommonStockSharesOutstanding'], 'shares'))
    bal = []
    for e in sorted(set(fot['ativo']) | set(fot['pl'])):
        linha = {'end': e, 'filed': min(fot[k][e]['filed'] for k in fot if e in fot[k])}
        for k in fot:
            if e in fot[k]:
                linha[k] = fot[k][e]['v']
        bal.append(linha)
    return {'trim': trim, 'bal': bal, 'acoes': [{'end': e, 'filed': x['filed'], 'v': x['v']} for e, x in sorted(acoes.items())]}


def candidatos(pasta, limite):
    """Os `limite` papéis mais negociados hoje (volume financeiro de 60 pregões) nos dados publicados."""
    man = json.load(open(os.path.join(pasta, 'manifest.json')))
    liq = {}
    for nome in man['arquivosPrecos']:
        o = json.load(open(os.path.join(pasta, nome)))
        ativos = o['ativos'] if o.get('formato') == 'colunar-v1' else o
        for t, a in ativos.items():
            c, v = a['close'][-60:], (a.get('volume') or [])[-60:]
            if len(c) == 60 and len(v) == 60:
                liq[t] = sum(x * y for x, y in zip(c, v)) / 60
    return sorted(liq, key=liq.get, reverse=True)[:limite]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('pasta')
    ap.add_argument('saida')
    ap.add_argument('--limite', type=int, default=1000)
    a = ap.parse_args(argv)
    if not fa.SEC_USER_AGENT:
        print('SEC_USER_AGENT vazio: nada a fazer.')
        return 1
    mapa = fa.load_sec_ticker_map()
    res, sem = {}, []
    tickers = candidatos(a.pasta, a.limite)
    for n, t in enumerate(tickers, 1):
        cik = mapa.get(t.upper().replace('.', '-')) or mapa.get(t.upper())
        r = fa.sec_get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json') if cik else None
        if r is None or r.status_code != 200:
            sem.append(t)
            continue
        try:
            d = extrair(r.json())
        except Exception as e:  # noqa: BLE001 - um papel ruim não derruba a coleta
            print(f'  {t}: falhou ({e})')
            sem.append(t)
            continue
        d['cik'] = cik
        d['anuncios'] = datas_de_balanco(cik) or []
        res[t] = d
        if n % 100 == 0:
            print(f'  {n}/{len(tickers)}', flush=True)
    json.dump(res, open(a.saida, 'w'), separators=(',', ':'))
    print(f'Balanços SEC: {len(res)} de {len(tickers)} papéis; sem dado: {len(sem)} ({", ".join(sem[:30])}...)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
