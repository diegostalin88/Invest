"""Travas de débito (O2), sem rede."""
import math
from datetime import date, timedelta

import cotahist as ch
import debito
import test_travas as tt
import travas


def test_montar_trava_de_alta_com_call():
    travas.CDI.clear()
    cad = tt._cadeia(100.0, '20260105', '20260209')
    m = debito.montar('alta', cad, 100.0, '20260105', debito.BASE)
    (cc, _, lc), (cv, _, lv) = m['pernas']
    assert lc == +1 and lv == -1 and m['tipo'] == 'call'
    assert m['strikes'][cc] == 100.0 and m['strikes'][cv] == 105.0 and 0 < m['debito'] < m['largura'] == 5.0


def test_valor_e_intrinseco():
    pos = {'pernas': [('c100', 'V', +1), ('c105', 'V', -1)], 'strikes': {'c100': 100.0, 'c105': 105.0}, 'tipo': 'call'}
    cad = [('c100', 'call', 100, 'V', 2.0, 2.2), ('c105', 'call', 105, 'V', 0.5, 0.6)]
    assert abs(debito.valor(pos, cad, 0.0) - (2.0 - 0.6)) < 1e-12
    assert abs(debito.valor(pos, cad, 0.0, meio=True) - (2.1 - 0.55)) < 1e-12
    assert debito.intrinseco(pos, 103.0) == 3.0 and debito.intrinseco(pos, 110.0) == 5.0 and debito.intrinseco(pos, 90) == 0


def test_escolher_tecnica_pede_rompimento_com_volume():
    i = travas.Indicadores(n_mme=5)
    for k in range(25):
        i.atualizar(10.5, 9.5, 10.0, 1000.0)
    i.atualizar(12.0, 10.0, 11.5, 2000.0)          # rompe a máxima de 20 com o dobro do volume
    assert debito.escolher(i, 11.5, {**debito.BASE, **debito.TECNICO}) == 'alta'
    j = travas.Indicadores(n_mme=5)
    for k in range(25):
        j.atualizar(10.5, 9.5, 10.0, 1000.0)
    j.atualizar(12.0, 10.0, 11.5, 1100.0)          # rompe sem volume
    assert debito.escolher(j, 11.5, {**debito.BASE, **debito.TECNICO}) is None


def test_simulacao_ponta_a_ponta():
    travas.CDI.clear()
    dias, d = [], date(2021, 1, 4)
    while len(dias) < 520:
        if d.weekday() < 5:
            dias.append(d.strftime('%Y%m%d'))
        d += timedelta(days=1)
    spot, ohlc, cadeia, ivs = {}, {}, {}, {}
    for n, dd in enumerate(dias):
        s = 50 + 0.06 * n + 2 * math.sin(n / 9)
        vol = 0.25 + 0.15 * math.sin(n / 40)
        spot[(dd, 'PETR4')], ohlc[(dd, 'PETR4')], ivs[(dd, 'PETR4')] = s, (s * 1.015, s * 0.985, 1e6), vol
        hoje = ch._dia(dd)
        vencs = [f'{y}{m:02d}15' for y, m in ((hoje.year + (hoje.month + j - 1) // 12, (hoje.month + j - 1) % 12 + 1)
                                               for j in (1, 2, 3))]
        cadeia[(dd, 'PETR4')] = [c for v in vencs for c in tt._cadeia(s, dd, v, vol)]
    res = debito.simular((dias, spot, ohlc, cadeia, ivs), {**debito.BASE, 'ivr_max': None}, '20220101', '20261231')
    ops = res['operacoes']
    assert ops and all(o['saida'] > o['entrada'] for o in ops)
    assert all(o['pnl'] >= -o['risco'] - 1e-6 for o in ops)                 # nunca perde mais que o débito
    m = travas.metricas(res, 0.0)
    assert m['operacoes'] == len(ops) and set(m['porEstrutura']) <= {'trava_alta_call', 'trava_baixa_put'}
    r2 = debito.simular((dias, spot, ohlc, cadeia, ivs), {**debito.BASE, 'ivr_max': None, 'sorteio': (0.1, 3)},
                        '20220101', '20261231')
    assert r2['elegiveis'] >= r2['sinais']
