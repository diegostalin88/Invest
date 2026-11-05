"""COTAHIST e IV, sem rede."""
import math

import cotahist


def linha(data, codneg, tpmerc, especi, preult, totneg=10, preexe=0.0, datven='99991231', codbdi='02'):
    """Monta um registro de 245 posições no layout oficial."""
    campos = [
        ('01', 2), (data, 8), (codbdi, 2), (codneg.ljust(12), 12), (tpmerc, 3), ('NOME'.ljust(12), 12),
        (especi.ljust(10), 10), (' ' * 3, 3), (' ' * 4, 4),
        *[(f'{round(preult * 100):013d}', 13)] * 7,                # PREABE..PREOFV (só PREULT importa)
        (f'{totneg:05d}', 5), ('0' * 18, 18), ('0' * 18, 18),
        (f'{round(preexe * 100):013d}', 13), ('0', 1), (datven, 8), ('0000001', 7), ('0' * 13, 13),
        (' ' * 12, 12), ('000', 3)]
    s = ''.join(v for v, n in campos)
    assert len(s) == 245
    return s + '\n'


def test_ler_linha():
    r = cotahist.ler_linha(linha('20260105', 'PETRA350', '070', 'PN      N2', 1.23, totneg=42, preexe=35.0,
                                 datven='20260116'))
    assert r['data'] == '20260105' and r['codneg'] == 'PETRA350' and r['tpmerc'] == '070'
    assert r['preult'] == 1.23 and r['totneg'] == 42 and r['preexe'] == 35.0 and r['datven'] == '20260116'
    assert cotahist.ler_linha('00COTAHIST.2026') is None


def test_filtrar_separa_classe():
    linhas = [
        linha('20260105', 'PETR4', '010', 'PN      N2', 36.0),
        linha('20260105', 'PETR3', '010', 'ON      N2', 38.0),
        linha('20260105', 'PETRA360', '070', 'PN      N2', 1.0, preexe=36.0, datven='20260206'),
        linha('20260105', 'PETRA380', '070', 'ON      N2', 1.0, preexe=38.0, datven='20260206'),   # de PETR3
        linha('20260105', 'XPTOA10', '070', 'ON', 1.0, preexe=10.0),
    ]
    spot, opcoes, ign = cotahist.filtrar(linhas)
    assert spot == {('20260105', 'PETR4'): 36.0}
    assert [o['codneg'] for o in opcoes] == ['PETRA360'] and ign == 1


def test_iv_recupera_a_vol():
    for tipo in ('call', 'put'):
        p = cotahist.bs_preco(tipo, 36.0, 37.0, 30 / 365, math.log(1.11), 0.35)
        assert abs(cotahist.iv(tipo, p, 36.0, 37.0, 30 / 365, math.log(1.11)) - 0.35) < 1e-4
    assert cotahist.iv('call', 0.0001, 36.0, 30.0, 30 / 365, 0.1) is None   # abaixo do valor intrínseco


def test_iv_diaria_escolhe_atm_perto_de_30_dias():
    r, vol, s = math.log(1.11), 0.30, 36.0
    def p(tipo, k, dias):
        return round(cotahist.bs_preco(tipo, s, k, dias / 365, r, vol), 2)
    linhas = [linha('20260105', 'PETR4', '010', 'PN', s)]
    for k in (34.0, 36.0, 38.0):
        linhas.append(linha('20260105', f'PETRB{int(k)}', '070', 'PN', p('call', k, 32), preexe=k, datven='20260206'))
        linhas.append(linha('20260105', f'PETRN{int(k)}', '080', 'PN', p('put', k, 32), preexe=k, datven='20260206'))
    linhas.append(linha('20260105', 'PETRA36', '070', 'PN', 0.5, preexe=36.0, datven='20260116'))    # 11 dias: fora
    linhas.append(linha('20260105', 'PETRB37', '070', 'PN', 2.0, totneg=1, preexe=36.5, datven='20260206'))  # ilíquida
    spot, opcoes, _ = cotahist.filtrar(linhas)
    out = cotahist.iv_diaria(spot, opcoes, {'20260105': 0.11})
    assert len(out) == 1
    x = out[0]
    assert x['dte'] == 32 and x['strike'] == 36.0 and x['pernas'] == 2 and abs(x['iv'] - vol) < 0.01


def test_iv_rank():
    assert cotahist.iv_rank([0.2] * 10) is None
    serie = [0.20 + 0.10 * i / 251 for i in range(252)]
    assert abs(cotahist.iv_rank(serie) - 100) < 1e-9
    assert abs(cotahist.iv_rank(serie[:-1] + [0.25]) - 50) < 0.5


def test_resumo_e_markdown():
    linhas = [{'data': '2026-01-05', 'ativo': 'PETR4', 'iv': 0.3}, {'data': '2026-01-06', 'ativo': 'PETR4', 'iv': 0.32}]
    res = cotahist.resumir(linhas, {'PETR4': {'2026': 4}})
    assert res['PETR4']['anos']['2026'] == {'pregoes': 4, 'comIV': 2, 'cobertura': 0.5, 'ivMediana': 0.31}
    assert res['VALE3']['ultimaIV'] is None
    assert '| PETR4 | 2026 | 4 | 2 | 50% | 31.0% |' in cotahist.markdown(res, ['x'])
