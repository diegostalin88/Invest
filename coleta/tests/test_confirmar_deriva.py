"""Confirmação de D: a carteira contínua cobra custo e segue o preço (sem rede)."""
import numpy as np

import confirmar_deriva as cd
from testar_fundamentos import Precos


def _precos(n=80):
    cal = [f'2020-{1 + k // 28:02d}-{1 + k % 28:02d}' for k in range(n)]
    bruto = {'SPY': {'dates': cal, 'adj': [100.0] * n, 'close': [100.0] * n, 'vol': [1] * n},
             'AAA': {'dates': cal, 'adj': [10.0 * 1.01 ** k for k in range(n)], 'close': [10.0] * n, 'vol': [1] * n}}
    return Precos(bruto, cal)


def test_carteira_um_evento():
    P = _precos()
    r, rs = cd.carteira(P, [{'t': 'AAA', 'i': 5}], 'SPY')
    assert r[6] == 0 and abs(r[7] - (0.01 - 0.001)) < 1e-12 and abs(r[30] - 0.01) < 1e-12
    assert abs(r[66] - (0.01 - 0.001)) < 1e-12 and r[67] == 0   # sai no fechamento de i+61
    assert np.all(rs == 0)
    m = cd.metricas(r[7:67])
    assert m['quedaMax'] == 0 and m['retorno'] > 70
