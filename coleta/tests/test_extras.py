import json
import os

import extras


def test_escolhe_acoes_e_bdrs_fora_do_universo():
    cart = {'ativos': {
        'BOVA11': {}, 'MOVI3': {}, 'PETR4': {}, 'AAPL34': {}, 'HGRU11': {}, 'LREN3': {'apoio': True},
        'QBTS': {'moeda': 'USD', 'tipo': 'EQUITY'}, 'SLV': {'moeda': 'USD', 'tipo': 'ETF'}, 'NVDA': {'moeda': 'USD', 'tipo': 'EQUITY'}}}
    br, us = extras.escolher(cart, {'PETR4'}, {'NVDA'})
    assert br == ['AAPL34', 'MOVI3'] and us == ['QBTS']


def test_coletar_grava_formato_do_universo(tmp_path):
    n = 80
    serie = {'dates': [f'2026-{1 + k // 28:02d}-{1 + k % 28:02d}' for k in range(n)], 'open': [10.0] * n,
             'high': [10.5] * n, 'low': [9.5] * n, 'close': [10.0] * n, 'volume': [1000] * n}
    ok, sem = extras.coletar(['MOVI3', 'NADA3'], '.SA', str(tmp_path / 'extras'), 'br', 'BRL', None,
                             baixar=lambda ts, anos: ({'MOVI3.SA': dict(serie)}, 0),
                             fundamentos=lambda pool, precos: {t: {'pe': 4.0} for t in pool})
    assert ok == ['MOVI3'] and sem == ['NADA3']
    m = json.load(open(tmp_path / 'extras' / 'manifest.json'))
    assert m['extra'] and m['papeis'] == ['MOVI3'] and os.path.exists(tmp_path / 'extras' / m['arquivosPrecos'][0])
    assert extras.tickers(str(tmp_path / 'extras')) == {'MOVI3'}
