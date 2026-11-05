"""Auditoria da O1, sem rede: atraso e placebo rodam e se comportam como esperado."""
import math
from datetime import date, timedelta

import auditoria_o1 as au
import cotahist as ch
import test_travas as tt
import travas


def _dados():
    travas.CDI.clear()
    dias, d = [], date(2021, 1, 4)
    while len(dias) < 520:
        if d.weekday() < 5:
            dias.append(d.strftime('%Y%m%d'))
        d += timedelta(days=1)
    spot, ohlc, cadeia, ivs = {}, {}, {}, {}
    for n, dd in enumerate(dias):
        s = 50 + 0.03 * n + 3 * math.sin(n / 9)
        vol = 0.25 + 0.15 * math.sin(n / 40)
        spot[(dd, 'PETR4')], ohlc[(dd, 'PETR4')], ivs[(dd, 'PETR4')] = s, (s * 1.012, s * 0.988), vol
        hoje = ch._dia(dd)
        vencs = [f'{y}{m:02d}15' for y, m in ((hoje.year + (hoje.month + j - 1) // 12, (hoje.month + j - 1) % 12 + 1)
                                               for j in (1, 2, 3))]
        cadeia[(dd, 'PETR4')] = [c for v in vencs for c in tt._cadeia(s, dd, v, vol)]
    return dias, spot, ohlc, cadeia, ivs


def test_atraso_e_placebo(monkeypatch):
    monkeypatch.setattr(au, 'FORA', ('20220101', '20261231'))
    dados = _dados()
    res, m = au.rodar(dados, travas.BASE)
    assert m['operacoes'] > 0 and res['elegiveis'] >= res['sinais'] > 0
    _, m2 = au.rodar(dados, {**travas.BASE, 'atraso': 2})
    assert m2['operacoes'] > 0
    ent1 = {o['entrada'] for o in res['operacoes']}
    ent2 = {o['entrada'] for o in au.rodar(dados, {**travas.BASE, 'atraso': 2})[0]['operacoes']}
    assert ent1 != ent2
    freq = res['sinais'] / res['elegiveis']
    p1 = au.rodar(dados, {**travas.BASE, 'sorteio': (freq, 1)})[0]
    p2 = au.rodar(dados, {**travas.BASE, 'sorteio': (freq, 1)})[0]
    assert p1['operacoes'] == p2['operacoes']           # mesma semente, mesmo resultado
    assert au.por_ano(res['operacoes']) and au.pior_mes(res)
    assert len(au.conferencia(dados, res['operacoes'], n=2)) == min(2, len(res['operacoes']))
