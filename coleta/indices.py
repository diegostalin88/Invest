"""Índices de referência para comparar a estratégia congelada (decisão de 04/11/2026).

Grava `indice.json` em cada pasta de mercado (EUA: SPY e ^GSPC; Brasil: BOVA11 e ^BVSP) com o fechamento
ajustado dos últimos anos, e acrescenta `arquivoIndice` ao manifest.json daquela pasta. O app usa isso para
mostrar, na Simulação e no Diário de sinais, quanto o mesmo dinheiro teria rendido no índice nas mesmas datas.

Uso: python coleta/indices.py site/data
"""
import json
import os
import sys
from datetime import datetime, timezone

INDICES = {
    '': [('SPY', 'SPY (ETF do S&P 500)'), ('^GSPC', 'S&P 500')],
    'br': [('BOVA11.SA', 'BOVA11 (ETF do Ibovespa)'), ('^BVSP', 'Ibovespa')],
}
ANOS = '6y'


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
        if r and len(r[0]) == len(r[1]) and len(r[0]) > 20:
            series[ticker] = {'nome': nome, 'dates': list(r[0]), 'close': list(r[1])}
    return series


def main(argv=None, baixar=baixar_yahoo):
    argv = argv if argv is not None else sys.argv
    raiz = argv[1] if len(argv) > 1 else 'site/data'
    gravados = 0
    for sub, lista in INDICES.items():
        pasta = os.path.join(raiz, sub) if sub else raiz
        manifesto = os.path.join(pasta, 'manifest.json')
        if not os.path.exists(manifesto):
            continue
        series = montar(lista, baixar)
        if not series:
            print(f'{pasta}: nenhum índice baixado; mantém o que houver', file=sys.stderr)
            continue
        saida = {'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                 'principal': lista[0][0] if lista[0][0] in series else next(iter(series)), 'series': series}
        with open(os.path.join(pasta, 'indice.json'), 'w', encoding='utf-8') as f:
            json.dump(saida, f, separators=(',', ':'))
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
