"""Hipótese C-BR (docs/hipotese-fundamentos-brasil.md), sem rede."""
import numpy as np

import testar_fundamentos as tf
import testar_fundamentos_br as br


def _precos(n=800):
    cal = [f'{2015 + i // 250}-{1 + (i % 250) // 21:02d}-{1 + (i % 21):02d}' for i in range(n)]
    bruto = {}
    for k, t in enumerate(['AAAA3', 'AAAA4', 'BBBB3', 'BOVA11']):
        close = [10.0 + k + 0.01 * i for i in range(n)]
        # um provento de 5% no meio: o ajustado antes dele fica 5% menor
        adj = [c * (0.95 if i < n // 2 else 1.0) for i, c in enumerate(close)]
        bruto[t] = {'dates': cal, 'adj': adj, 'close': close, 'vol': [1e6] * n, 'splits': []}
    return tf.Precos(bruto, cal), cal


def test_universo_sem_units():
    u = br.universo()
    assert u and not any(t.endswith('11') for t in u) and 'PETR4' in u


def test_dividendos_pela_razao_ajustado():
    P, cal = _precos()
    i = len(cal) // 2 + 10
    assert abs(br.dy_12m(P, 'AAAA3', i) - 0.05) < 1e-9
    assert br.dy_12m(P, 'AAAA3', len(cal) - 1) == 0.0       # provento há mais de um ano
    assert np.isnan(br.dy_12m(P, 'AAAA3', 100))               # sem um ano de história


def test_fundamentos_sem_olhar_o_futuro():
    b = {'trim': [{'end': e, 'filed': f, 'ni': 10.0} for e, f in
                  (('2016-03-31', '2016-05-10'), ('2016-06-30', '2016-08-10'), ('2016-09-30', '2016-11-10'),
                   ('2016-12-31', '2017-03-20'))],
         'bal': [{'end': '2016-12-31', 'filed': '2017-03-20', 'ativo': 100.0, 'pl': 50.0}],
         'acoes': [{'end': '2016-12-31', 'filed': '2017-03-20', 'v': 100.0}]}
    assert br.fundamentos_br(b, '2017-03-20', lambda _: 1.0) is None     # publicado no dia: só vale no seguinte
    f = br.fundamentos_br(b, '2017-03-21', lambda _: 2.0)
    assert f == {'ni': 40.0, 'pl': 50.0, 'acoes': 200.0}
    assert br.fundamentos_br(b, '2017-12-01', lambda _: 1.0) is None     # balanço velho demais


def test_elegiveis_um_codigo_por_empresa_e_pl(monkeypatch):
    monkeypatch.setattr(br, 'MCAP_ESCALA', 0)
    P, cal = _precos()
    i = len(cal) - 1
    b = lambda ni: {'trim': [{'end': e, 'filed': '2000-01-01', 'ni': ni} for e in
                             ('2017-03-31', '2017-06-30', '2017-09-30', '2017-12-31')],
                    'bal': [{'end': '2017-12-31', 'filed': '2000-01-01', 'ativo': 1.0, 'pl': 1.0}],
                    'acoes': [{'end': '2017-12-31', 'filed': '2000-01-01', 'v': 1e6}]}
    B = {'AAAA3': b(1e6), 'AAAA4': b(1e6), 'BBBB3': b(1e8)}   # BBBB3: P/L < 1 → erro de escala
    # datas dos balanços perto do fim do calendário sintético
    fim = cal[-1]
    for v in B.values():
        for x in v['trim']:
            x['end'] = x['end'].replace('2017', str(int(fim[:4]) - 1))
        for k in ('bal', 'acoes'):
            for x in v[k]:
                x['end'] = x['end'].replace('2017', str(int(fim[:4]) - 1))
    empresa = {'AAAA3': 'A', 'AAAA4': 'A', 'BBBB3': 'B'}
    monkeypatch.setattr(br, 'LIQ_MIN', 1.0)
    excl = []
    e = br.elegiveis(P, B, empresa, i, excl)
    assert [x['t'] for x in e] == ['AAAA4'] and excl and excl[0][1] == 'BBBB3'
    # ações informadas em milhares: valor de mercado abaixo de R$ 1 bi é multiplicado por 1.000
    monkeypatch.setattr(br, 'MCAP_ESCALA', 1e9)
    B['BBBB3']['acoes'][0]['v'] = 1e8 / 1000 * 10        # P/L verdadeiro ~1,5 informado em milhares
    excl = []
    e = br.elegiveis(P, B, empresa, i, excl)
    assert 'BBBB3' in [x['t'] for x in e] and any(x[2] == 'ações em milhares' for x in excl)


def test_hipotese_ponta_a_ponta(monkeypatch):
    n = 1300
    cal = [f'{2012 + i // 250}-{1 + (i % 250) // 21:02d}-{1 + (i % 21):02d}' for i in range(n)]
    rng = np.random.default_rng(1)
    bruto, B, emp = {}, {}, {}
    for k in range(8):
        t = f'T{k:03d}3'
        close = list(10 * np.cumprod(1 + rng.normal(0.0005, 0.01, n)))
        bruto[t] = {'dates': cal, 'adj': close, 'close': close, 'vol': [1e7] * n, 'splits': []}
        trim = []
        for a in range(2011, 2018):
            for m, f in (('03-31', '05-10'), ('06-30', '08-10'), ('09-30', '11-10'), ('12-31', '03-20')):
                trim.append({'end': f'{a}-{m}', 'filed': f'{a + (m == "12-31")}-{f}', 'ni': 1e6 * (k + 1)})
        B[t] = {'trim': trim, 'bal': [{**x, 'ativo': 1.0, 'pl': 1.0} for x in trim],
                'acoes': [{**x, 'v': 1e6} for x in trim]}
        emp[t] = t
    bruto['BOVA11'] = {'dates': cal, 'adj': [10 + 0.001 * i for i in range(n)], 'close': [10.0] * n,
                       'vol': [1e7] * n, 'splits': []}
    P = tf.Precos(bruto, cal)
    monkeypatch.setattr(br, 'MIN_ELEG', 4)
    monkeypatch.setattr(br, 'MCAP_ESCALA', 0)
    monkeypatch.setattr(br, 'N_CART', 3)
    monkeypatch.setattr(br, 'SORTEIOS', 5)
    monkeypatch.setattr(br, 'LIQ_MIN', 1.0)
    R = br.hipotese(P, B, emp, {d: 0.0004 for d in cal})
    assert R and R['trimestres'] > 4 and set(R['criterios']) and 'Veredito' in br.markdown(R)
    assert R['cdi']['retorno'] > 0


def test_acoes_do_fre():
    import io as _io
    import zipfile as _zip
    c = '11.111.111/0001-11'
    buf = _io.BytesIO()
    with _zip.ZipFile(buf, 'w') as z:
        z.writestr('fre_cia_aberta_2015.csv', 'CNPJ_CIA;DT_REFER;VERSAO;ID_DOC;DT_RECEB\n'
                   f'{c};2015-01-01;1;9;2015-05-20\n{c};2015-01-01;2;9;2015-08-01\n')
        z.writestr('fre_cia_aberta_capital_social_2015.csv',
                   'CNPJ_Companhia;Data_Referencia;Versao;Tipo_Capital;Quantidade_Total_Acoes\n'
                   f'{c};2015-01-01;1;Capital Emitido;500\n{c};2015-01-01;1;Capital Integralizado;400\n'
                   f'{c};2015-01-01;2;Capital Integralizado;450\n99.999.999/0001-99;2015-01-01;1;Capital Integralizado;7\n')
    out = br.acoes_fre(buf.getvalue(), 2015, {c})
    assert out == {c: [{'end': '2015-01-01', 'filed': '2015-08-01', 'v': 450.0}]}
