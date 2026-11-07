"""Box de 4 pontas (O4), sem rede."""
import box
import test_auditoria_o1 as ta
import test_travas as tt
import travas


def test_custo_box_e_taxa():
    c1 = ('c90', 'call', 90.0, 'V', 11.0, 11.2)
    c2 = ('c100', 'call', 100.0, 'V', 3.0, 3.1)
    p1 = ('p90', 'put', 90.0, 'V', 0.5, 0.6)
    p2 = ('p100', 'put', 100.0, 'V', 2.4, 2.5)
    pago = box.custo_box((c1, c2, p1, p2), False, 0.0)
    assert abs(pago - (11.2 - 3.0 + 2.5 - 0.5)) < 1e-12
    meio = box.custo_box((c1, c2, p1, p2), True, 0.0)
    assert abs(meio - (11.1 - 3.05 + 2.45 - 0.55)) < 1e-12
    tx, recebe = box.taxa(('V', 90.0, 100.0, None), pago, {'custo': 0.0}, 252)
    assert recebe == 10.0 and abs(tx - (10.0 / pago - 1)) < 1e-12


def test_simulacao_box_paridade():
    """Na cadeia sintética (Black-Scholes, juros de 10%), o box no meio rende perto de 10% e pelas ofertas, menos."""
    travas.CDI.clear()
    dados = ta._dados()
    assert box.boxes(tt._cadeia(100.0, '20260105', '20260209'), '20260105', box.BASE)
    r_meio = box.simular(dados, {**box.BASE, 'meio': True, 'custo': 0.0}, '20220101', '20261231')
    r_of = box.simular(dados, box.BASE, '20220101', '20261231')
    assert r_meio['operacoes'] and all(o['saida'] >= o['venc'] for o in r_meio['operacoes'])
    assert all(o['pnl'] >= 0 for o in r_meio['operacoes'])
    m = box.metricas(r_meio)
    assert abs(m['todosBoxes']['mediana']) < 0.02            # taxa no meio ≈ CDI (os dois 10%)
    assert box.metricas(r_of)['todosBoxes']['mediana'] < m['todosBoxes']['mediana']
    assert box.metricas(box.simular(dados, {**box.BASE, 'atraso': 1}, '20220101', '20261231'))['operacoes'] >= 0
    c, ok = box.veredito(m)
    assert isinstance(ok, bool) and len(c) == 4
