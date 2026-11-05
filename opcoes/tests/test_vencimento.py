"""Hipótese O3 (ordem limite no meio, até o vencimento), sem rede."""
import auditoria_o1 as au
import debito
import test_auditoria_o1 as ta
import travas
import vencimento


def test_executa_ordem_limite():
    pernas = [('pV', 'V', -1), ('pC', 'V', +1)]
    ref = [('pV', 'put', 95, 'V', 1.0, 1.2, 0, 0), ('pC', 'put', 90, 'V', 0.3, 0.5, 0, 0)]
    lim = travas.limites_meio(pernas, ref)
    assert lim == {('pV', 'V'): 1.1, ('pC', 'V'): 0.4}
    hoje = [('pV', 'put', 95, 'V', 1.0, 1.2, 1.1, 1.0), ('pC', 'put', 90, 'V', 0.3, 0.5, 0.45, 0.4)]
    assert travas.executa(pernas, lim, hoje) == 'todas'
    assert travas.executa(pernas, lim, hoje, estrito=True) == 'nenhuma'
    sem_negocio = [hoje[0], ('pC', 'put', 90, 'V', 0.3, 0.5, 0.0, 0.0)]
    assert travas.executa(pernas, lim, sem_negocio) == 'parte'
    assert travas.executa(pernas, lim, []) == 'nenhuma'


def test_simulacao_o3_so_sai_no_vencimento(monkeypatch):
    dados = ta._dados()
    for nome, (sim, p) in vencimento.VERSOES.items():
        p = {**p, 'ivr_tendencia': None, 'ivr_lateral': None, 'ivr_max': None}
        res = sim(dados, p, '20220101', '20261231')
        ops = res['operacoes']
        assert ops, nome
        assert {o['motivo'] for o in ops} == {'vencimento'}
        assert all(o['saida'] > o['entrada'] and o['pnl'] >= -o['risco'] * 1.02 for o in ops)  # + custo do exercício
        assert res['ordens']['todas'] >= len(ops)
        estrito = sim(dados, {**p, 'estrito': True}, '20220101', '20261231')
        assert estrito['ordens']['todas'] <= res['ordens']['todas']
    monkeypatch.setattr(au, 'FORA', ('20220101', '20261231'))
    _, m = au.rodar(dados, {**debito.BASE, **vencimento.O3, 'ivr_max': None}, debito.simular)
    assert m['operacoes'] > 0
