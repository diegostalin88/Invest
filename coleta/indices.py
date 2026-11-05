"""Índices de referência para comparar a estratégia congelada (decisão de 04/11/2026).

Grava `indice.json` em cada pasta de mercado (EUA: SPY e ^GSPC; Brasil: BOVA11 e ^BVSP) com o fechamento
ajustado dos últimos anos, e acrescenta `arquivoIndice` ao manifest.json daquela pasta. O app usa isso para
mostrar quanto o mesmo dinheiro teria rendido no índice nas mesmas datas.

Também grava a renda fixa sem risco como uma série acumulada (começa em 1): o CDI no Brasil (Banco Central,
série SGS 12) e a T-bill de 3 meses nos EUA (^IRX do Yahoo). É o custo de oportunidade: o que o dinheiro
rende parado, sem risco de bolsa.

Uso: python coleta/indices.py site/data
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

INDICES = {
    '': [('SPY', 'SPY (ETF do S&P 500)'), ('^GSPC', 'S&P 500'), ('^IRX', 'T-bill de 3 meses')],
    'br': [('BOVA11.SA', 'BOVA11 (ETF do Ibovespa)'), ('^BVSP', 'Ibovespa'), ('CDI', 'CDI')],
}
RENDA_FIXA = {'^IRX', 'CDI'}
ANOS = '6y'


def acumular(datas, taxas_dia):
    """Série acumulada: valor[0] = 1 e valor[k] = valor[k-1] × (1 + taxa do dia k-1)."""
    v, out = 1.0, []
    for k in range(len(datas)):
        if k:
            v *= 1 + taxas_dia[k - 1]
        out.append(round(v, 8))
    return list(datas), out


def baixar_cdi():
    """CDI diário do Banco Central (% ao dia) → série acumulada. A API aceita no máximo 10 anos por pedido."""
    import requests
    from datetime import date, timedelta
    ini = (date.today() - timedelta(days=6 * 365)).strftime('%d/%m/%Y')
    fim = date.today().strftime('%d/%m/%Y')
    r = requests.get('https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados',
                     params={'formato': 'json', 'dataInicial': ini, 'dataFinal': fim}, timeout=60)
    r.raise_for_status()
    linhas = [(datetime.strptime(x['data'], '%d/%m/%Y').strftime('%Y-%m-%d'), float(x['valor']) / 100) for x in r.json()]
    linhas.sort()
    return acumular([d for d, _ in linhas], [t for _, t in linhas])


def baixar_tbill():
    """^IRX = juro anual (%) da T-bill de 3 meses; rende pelos dias corridos entre um pregão e o seguinte."""
    import yfinance as yf
    from datetime import date
    h = yf.Ticker('^IRX').history(period=ANOS, auto_adjust=False)
    if h is None or not len(h):
        return None
    datas = h.index.strftime('%Y-%m-%d').tolist()
    y = [float(x) / 100 for x in h['Close']]
    taxas = [(1 + y[k]) ** ((date.fromisoformat(datas[k + 1]) - date.fromisoformat(datas[k])).days / 365) - 1
             for k in range(len(datas) - 1)] + [0.0]
    return acumular(datas, taxas)


def baixar_padrao(ticker):
    if ticker == 'CDI':
        return baixar_cdi()
    if ticker == '^IRX':
        return baixar_tbill()
    return baixar_yahoo(ticker)


def baixar_yahoo(ticker):
    """Devolve (datas, fechamentos ajustados) ou None."""
    import yfinance as yf
    h = yf.Ticker(ticker).history(period=ANOS, auto_adjust=True)
    if h is None or not len(h):
        return None
    datas = h.index.strftime('%Y-%m-%d').tolist()
    return datas, [round(float(x), 4) for x in h['Close']]


def montar(lista, baixar):
    series = {}
    for ticker, nome in lista:
        try:
            r = baixar(ticker)
        except Exception as e:  # um índice que falha não derruba o outro
            print(f'falhou {ticker}: {e}', file=sys.stderr)
            r = None
        if r and len(r[0]) == len(r[1]):
            # o Yahoo às vezes devolve o pregão do dia sem fechamento (NaN): NaN no JSON derruba o arquivo inteiro no app
            pares = [(d, c) for d, c in zip(r[0], r[1]) if c is not None and math.isfinite(c) and c > 0]
            if len(pares) > 20:
                series[ticker] = {'nome': nome, 'dates': [d for d, _ in pares], 'close': [c for _, c in pares]}
    return series


def main(argv=None, baixar=baixar_padrao):
    argv = argv if argv is not None else sys.argv
    raiz = argv[1] if len(argv) > 1 else 'site/data'
    gravados = 0
    for sub, lista in INDICES.items():
        pasta = os.path.join(raiz, sub) if sub else raiz
        manifesto = os.path.join(pasta, 'manifest.json')
        if not os.path.exists(manifesto):
            continue
        series = montar(lista, baixar)
        fixa = next((t for t in series if t in RENDA_FIXA), None)
        if not any(t not in RENDA_FIXA for t in series):
            print(f'{pasta}: nenhum índice baixado; mantém o que houver', file=sys.stderr)
            continue
        saida = {'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                 'principal': lista[0][0] if lista[0][0] in series else next(t for t in series if t not in RENDA_FIXA),
                 'rendaFixa': fixa, 'series': series}
        with open(os.path.join(pasta, 'indice.json'), 'w', encoding='utf-8') as f:
            json.dump(saida, f, separators=(',', ':'), allow_nan=False)
        with open(manifesto, encoding='utf-8') as f:
            m = json.load(f)
        m['arquivoIndice'] = 'indice.json'
        with open(manifesto, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        gravados += 1
        print(f'{pasta}: ' + ', '.join(f'{t} ({len(s["dates"])} pregões)' for t, s in series.items()))
    return 0 if gravados else 1


if __name__ == '__main__':
    sys.exit(main())
