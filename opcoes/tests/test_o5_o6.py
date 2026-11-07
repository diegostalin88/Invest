"""O5 (wheel) e O6 (trava de put com VRP e ordem estruturada), sem rede."""
import test_auditoria_o1 as ta
import travas
import vrp
import wheel


def test_executa_casada():
    pernas = [('pV', 'V', -1), ('pC', 'V', +1)]
    lim = {('pV', 'V'): 1.1, ('pC', 'V'): 0.4}               # crédito líquido pedido: 0,70
    ok = [('pV', 'put', 95, 'V', 1.0, 1.2, 1.12, 1.0), ('pC', 'put', 90, 'V', 0.3, 0.5, 0.5, 0.42)]
    assert travas.executa_casada(pernas, lim, ok) == 'todas'     # 1,12 − 0,42 = 0,70
    nao = [('pV', 'put', 95, 'V', 1.0, 1.2, 1.08, 1.0), ok[1]]
    assert travas.executa_casada(pernas, lim, nao) == 'nenhuma'   # 1,08 − 0,42 < 0,70
    sem = [ok[0], ('pC', 'put', 90, 'V', 0.3, 0.5, 0.0, 0.0)]
    assert travas.executa_casada(pernas, lim, sem) == 'nenhuma'


def test_vol_realizada_e_vrp():
    fech = [100 * (1.01 if i % 2 else 0.99) ** 1 for i in range(30)]
    assert travas.vol_realizada(fech) > 0.1
    dados = ta._dados()
    p = {**vrp.VERSOES['6 papéis'][1], 'ativos': ['PETR4']}
    sem = travas.simular(dados, {**p, 'vrp_min': None}, '20220101', '20261231')
    com = travas.simular(dados, {**p, 'vrp_min': 50.0}, '20220101', '20261231')
    assert sem['sinais'] >= com['sinais'] and com['sinais'] == 0
    assert all(o['estrutura'] == 'trava_alta_put' and o['motivo'] == 'vencimento' for o in sem['operacoes'])


def test_proventos_pelo_ajuste_de_strike():
    dias = ['20240102', '20240103', '20240104']
    base = [(f'P{k}', 'put', float(k), '20240216', 1, 1.1, 0, 0) for k in (20, 22, 24, 26)]
    div = [(c[0], c[1], c[2] - 0.5, c[3], 1, 1.1, 0, 0) for c in base]
    spl = [(c[0], c[1], (c[2] - 0.5) / 2, c[3], 1, 1.1, 0, 0) for c in base]
    cad = {(dias[0], 'PETR4'): base, (dias[1], 'PETR4'): div, (dias[2], 'PETR4'): spl}
    prov = wheel.proventos(dias, cad, ['PETR4'])
    assert prov[(dias[1], 'PETR4')][0] == 'div' and abs(prov[(dias[1], 'PETR4')][1] - 0.5) < 1e-9
    assert prov[(dias[2], 'PETR4')] == ('split', 0.5)


def test_wheel_ponta_a_ponta():
    travas.CDI.clear()
    dados = ta._dados()
    p = {**wheel.BASE, 'ativos': ['PETR4']}
    res = wheel.simular(dados, p, '20220101', '20261231', prov={})
    m = wheel.metricas(res)
    assert m['puts'] > 0 and all(o['saida'] >= o['venc'] for o in res['operacoes'])
    assert all(o['strike'] < o['avista_entrada'] for o in res['operacoes'] if o['tipo'] == 'put')
    assert 0 <= m['quedaMax'] < 1 and res['curva']
    assert wheel.simular(dados, p, '20220101', '20261231', prov={})['final'] == res['final']


def test_o6_proposta_com_alvo_casado():
    dados = ta._dados()
    p = {**vrp.VERSOES['6 papéis'][1], 'ativos': ['PETR4'], 'vrp_min': None, 'credito_min': 0}
    res = travas.simular(dados, p, '20220101', '20261231')
    assert res['operacoes'] and {o['motivo'] for o in res['operacoes']} <= {'alvo', 'vencimento'}
    pos = {'pernas': [('pV', 'V', -1), ('pC', 'V', +1)]}
    cad = [('pV', 'put', 95, 'V', 0.2, 0.3, 0.3, 0.15), ('pC', 'put', 90, 'V', 0.0, 0.1, 0.06, 0.02)]
    assert travas.recompra_casada(pos, cad, 0.10) and not travas.recompra_casada(pos, cad, 0.05)


def test_strangle_o7():
    import strangle
    travas.CDI.clear()
    dados = ta._dados()
    p = {**strangle.BASE, 'ativos': ['PETR4'], 'ivr_max': 101}
    res = strangle.simular(dados, p, '20220101', '20261231')
    assert res['operacoes'] and all(o['saida'] >= o['venc'] and o['recebe'] >= 0 for o in res['operacoes'])
    assert len({o['entrada'][:6] for o in res['operacoes']}) == len(res['operacoes'])   # um por mês
    m = strangle.metricas(res)
    assert m['strangles'] == len(res['operacoes']) and m['pagoTotal'] > 0
    assert m['pagoTotal'] < 0.01 * 100000 * 60                                          # só parte dos juros


def test_sinais_o6_lista_do_dia():
    import sinais_o6
    travas.CDI.clear()
    dados = ta._dados()
    p = {**vrp.O6, 'ativos': ['PETR4'], 'credito_min': 0}
    sem = sinais_o6.sinais(dados, {**p, 'vrp_min': -1000})
    assert sem[0]['data'] == dados[0][-1] and sem[0]['sinal'] and sem[0]['trava']
    t = sem[0]['trava']
    assert [x['lado'] for x in t['pernas']] == ['vende', 'compra'] and t['pernas'][0]['strike'] > t['pernas'][1]['strike']
    assert abs(t['alvo_recompra'] - 0.25 * t['credito']) < 1e-12 and t['credito'] > 0
    v, c = t['pernas']
    assert abs(t['venda_limite'] - t['credito'] - c['oferta_venda']) < 1e-9   # crédito líquido igual ao pedido
    assert abs(t['recompra_limite'] - c['oferta_compra'] - t['alvo_recompra']) < 1e-9
    com = sinais_o6.sinais(dados, {**p, 'vrp_min': 1000})
    assert not com[0]['sinal'] and com[0]['vrp'] is not None
    assert 'PETR4' in sinais_o6.markdown(sem)
