"""Extração dos balanços históricos da SEC (sem rede)."""
import balancos_sec as b


def _u(start, end, val, filed, form='10-Q'):
    d = {'end': end, 'val': val, 'filed': filed, 'form': form}
    if start:
        d['start'] = start
    return d


def _facts():
    ni = [
        _u('2024-01-01', '2024-03-31', 10, '2024-05-01'),
        _u('2024-04-01', '2024-06-30', 20, '2024-08-01'),
        _u('2024-07-01', '2024-09-30', 30, '2024-11-01'),
        _u('2024-01-01', '2024-12-31', 100, '2025-02-20', '10-K'),
        _u('2024-01-01', '2024-03-31', 99, '2025-05-01'),        # reapresentado depois: não pode valer
        _u('2024-01-01', '2024-06-30', 30, '2024-08-01'),        # 6 meses: ignorado
        _u('2024-01-01', '2024-03-31', 10, '2024-05-01', '8-K'),  # formulário fora da lista
    ]
    return {'facts': {
        'us-gaap': {'NetIncomeLoss': {'units': {'USD': ni}},
                    'Revenues': {'units': {'USD': [_u('2024-01-01', '2024-03-31', 50, '2024-05-01')]}},
                    'CostOfRevenue': {'units': {'USD': [_u('2024-01-01', '2024-03-31', 30, '2024-05-01')]}},
                    'Assets': {'units': {'USD': [_u(None, '2024-03-31', 1000, '2024-05-01'), _u(None, '2024-03-31', 1100, '2024-08-01')]}},
                    'StockholdersEquity': {'units': {'USD': [_u(None, '2024-03-31', 400, '2024-05-01')]}}},
        'dei': {'EntityCommonStockSharesOutstanding': {'units': {'shares': [_u(None, '2024-04-25', 5000, '2024-05-01')]}}},
    }}


def test_trimestres_quarto_derivado_e_sem_reapresentacao():
    d = b.extrair(_facts())
    t = {x['end']: x for x in d['trim']}
    assert t['2024-03-31']['ni'] == 10 and t['2024-03-31']['filed'] == '2024-05-01'
    assert t['2024-12-31']['ni'] == 40 and t['2024-12-31']['filed'] == '2025-02-20'  # 100 − (10+20+30)
    assert t['2024-03-31']['gp'] == 20  # receita − custo do mesmo trimestre
    assert d['bal'][0] == {'end': '2024-03-31', 'filed': '2024-05-01', 'ativo': 1000, 'pl': 400}
    assert d['acoes'] == [{'end': '2024-04-25', 'filed': '2024-05-01', 'v': 5000}]


def test_quarto_trimestre_exige_os_tres_anteriores():
    f = _facts()
    f['facts']['us-gaap']['NetIncomeLoss']['units']['USD'] = [x for x in f['facts']['us-gaap']['NetIncomeLoss']['units']['USD'] if x['end'] != '2024-06-30']
    t = {x['end'] for x in b.extrair(f)['trim']}
    assert '2024-12-31' not in t
