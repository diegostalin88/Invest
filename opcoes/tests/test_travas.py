"""Simulação das travas de crédito, sem rede."""
import math
from datetime import date, timedelta

import cotahist as ch
import travas


def test_indicadores_alta_continua():
    i = travas.Indicadores(n_mme=10)
    for k in range(40):
        p = 10 + k
        i.atualizar(p + 0.5, p - 0.5, p)
    assert i.pronto() and i.mme < 49 and i.ifr == 100.0 and i.adx > 50
    assert not i.toca_keltner_inferior()


def _cadeia(s, d, venc, vol=0.4, r=math.log(1.1)):
    t = (ch._dia(venc) - ch._dia(d)).days / 365
    out = []
    for k in [float(x) for x in range(int(s * 0.8), int(s * 1.2) + 1)]:   # grade fixa, como na bolsa
        for tipo in ('call', 'put'):
            v = ch.bs_preco(tipo, s, k, t, r, vol)
            if v > 0.02:
                out.append((f'{tipo[0]}{k}', tipo, k, venc, round(v * 0.98, 2), round(v * 1.02, 2),
                            round(v * 1.01, 2), round(v * 0.99, 2)))   # máxima e mínima negociadas
    return out


def test_montar_trava_de_alta_com_put():
    travas.CDI.clear()
    cad = _cadeia(100.0, '20260105', '20260209')
    m = travas.montar_trava('put', cad, 100.0, '20260105', travas.BASE, 0.4)
    venda, compra = m['pernas']
    assert venda[2] == -1 and compra[2] == +1
    kv = float(venda[0][1:]); kc = float(compra[0][1:])
    assert kc < kv < 100 and abs((kv - kc) - 5) <= 2 and 0 < m['credito'] < m['largura']


def test_custo_recompra_paga_o_spread():
    pos = {'pernas': [('pA', 'V', -1), ('pB', 'V', +1)]}
    cad = [('pA', 'put', 95, 'V', 1.0, 1.2), ('pB', 'put', 90, 'V', 0.3, 0.4)]
    assert abs(travas.custo_recompra(pos, cad, 0.0) - (1.2 - 0.3)) < 1e-12
    assert travas.custo_recompra(pos, cad[:1], 0.0) is None
    assert abs(travas.custo_recompra(pos, cad, 0.0, meio=True) - (1.1 - 0.35)) < 1e-12


def test_spread_largo_nao_dispara_stop_na_entrada():
    """Com oferta larga, desmontar no mesmo dia já custa mais que 2x o crédito; o simulador não pode sair ali."""
    cad = [('pV', 'put', 95.0, '20230215', 1.00, 1.60), ('pC', 'put', 90.0, '20230215', 0.20, 0.45)]
    pos = {'pernas': [('pV', '20230215', -1), ('pC', '20230215', +1)]}
    credito = 1.00 - 0.45
    assert travas.custo_recompra(pos, cad, 0.0) >= 2 * credito       # o cenário do erro encontrado


def test_simulacao_ponta_a_ponta():
    """Ativo em alta com IV subindo no fim: deve abrir travas de alta com put e fechar com P&L coerente."""
    travas.CDI.clear()
    dias, d = [], date(2021, 1, 4)
    while len(dias) < 420:
        if d.weekday() < 5:
            dias.append(d.strftime('%Y%m%d'))
        d += timedelta(days=1)
    spot, ohlc, cadeia, ivs = {}, {}, {}, {}
    for n, dd in enumerate(dias):
        s = 50 + 0.05 * n + 2 * math.sin(n / 7)
        vol = 0.25 + (0.25 if n > 300 else 0.0) + 0.02 * math.sin(n / 11)
        spot[(dd, 'PETR4')] = s
        ohlc[(dd, 'PETR4')] = (s * 1.01, s * 0.99)
        ivs[(dd, 'PETR4')] = vol
        hoje = ch._dia(dd)
        vencs = [f'{y}{m:02d}15' for y, m in ((hoje.year + (hoje.month + j - 1) // 12, (hoje.month + j - 1) % 12 + 1)
                                               for j in (1, 2, 3))]
        cadeia[(dd, 'PETR4')] = [c for v in vencs for c in _cadeia(s, dd, v, vol)]
    dados = (dias, spot, ohlc, cadeia, ivs)
    res = travas.simular(dados, travas.BASE, '20220101', '20261231')
    assert res['operacoes'], 'nenhuma operação'
    assert all(o['estrutura'] in ('trava_alta_put', 'condor', 'trava_baixa_call') for o in res['operacoes'])
    assert all(o['pnl'] >= -o['risco'] - 1e-6 for o in res['operacoes'])   # nunca perde mais que o risco
    assert {o['motivo'] for o in res['operacoes']} & {'alvo', 'prazo', 'stop'}  # saídas antes do vencimento
    assert all(o['saida'] > o['entrada'] for o in res['operacoes'])             # nunca sai no dia da entrada
    m = travas.metricas(res, 0.0)
    assert m['operacoes'] == len(res['operacoes']) and 0 <= m['quedaMax'] < 1
    tec = travas.simular(dados, {**travas.BASE, **travas.TECNICO}, '20220101', '20261231')
    assert isinstance(tec['operacoes'], list)


def test_veredito():
    m = {'retorno': 0.3, 'cdi': 0.2, 'fatorLucro': 1.5, 'operacoes': 80, 'quedaMax': 0.1,
         'retornoSemMelhor': 0.25, 'pnlPorRisco': 0.05}
    _, ok = travas.veredito(m, {**m, 'pnlPorRisco': 0.01})
    assert ok
    crit, ok = travas.veredito(m, {**m, 'pnlPorRisco': 0.09})
    assert not ok and not crit['filtro de IV Rank melhora o resultado por operação']
