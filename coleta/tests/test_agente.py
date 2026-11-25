import json
import os
import subprocess
import sys
from datetime import date

import agente

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _site(tmp_path):
    site = tmp_path / 'site'
    subprocess.run([sys.executable, os.path.join(RAIZ, 'testes_app', 'gerar_site_exemplo.py'), str(site / 'antigo')], check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(RAIZ, 'testes_app', 'dados_carteira_exemplo.py'), str(site / 'data')], check=True, capture_output=True)
    return site


def test_agente_json_completo_e_pequeno(tmp_path):
    site = _site(tmp_path)
    ind = json.load(open(site / 'antigo' / 'data' / 'indice.json'))
    d = ind['series']['SPY']['dates']
    (site / 'antigo' / 'data' / 'diario.json').write_text(json.dumps({'inicio': d[-30], 'regras': {'r1': {'desligada': True}}, 'sinais': [
        {'estado': 'fechado', 'ret': 0.05, 'dataEntrada': d[-20], 'dataSaida': d[-10]},
        {'estado': 'fechado', 'ret': -0.02, 'dataEntrada': d[-9], 'dataSaida': d[-5]},
        {'estado': 'aberto'}]}))
    assert agente.main(['x', str(site)]) == 0
    txt = (site / 'data' / 'agente.json').read_bytes()
    assert len(txt) < agente.LIMITE_BYTES
    o = json.loads(txt)
    us, br = o['mercados']['us'], o['mercados']['br']
    assert us['termometro']['nome'] == 'SPY' and br['termometro']['nome'] == 'BOVA11'
    assert 0 <= us['amplitude']['acimaMM200'] <= 1
    assert len(br['papeis']) == br['saude']['papeis']          # Ibovespa inteiro
    assert set(us['listas']) == {'altas', 'quedas', 'maisNegociados', 'longeDoTopo', 'maisVolateis'}
    p = us['testeParaFrente']
    assert (p['fechados'], p['abertos'], p['regrasDesligadas'], p['acerto']) == (2, 1, ['r1'], 0.5)
    assert 'indiceMesmasDatas' in p
    assert o['referencias']['ref13']['ret12m'] is not None
    assert br['vendidos'] and br['vendidos'][0][1] == 10.0
    assert o['macro']['focus']['selic']['2026'] == 15.0 and o['macro']['focus']['antes']['ipca']['2026'] == 4.7
    assert 'fonte' not in o['macro']['focus']
    assert 'compra' in o['aviso'] or 'recomendação' in o['aviso']


def test_dados_velhos_e_mercado_ausente(tmp_path):
    site = tmp_path / 's'
    (site / 'antigo' / 'data').mkdir(parents=True)
    (site / 'antigo' / 'data' / 'manifest.json').write_text(json.dumps({'ultimoPregao': '2026-11-02', 'moeda': 'USD'}))
    o = agente.montar(str(site), hoje=date(2026, 11, 12))
    assert o['saude']['diasUteisDesdeUltimoPregao'] == 8 and o['saude']['dadosVelhos']
    assert o['saude']['mercadosAusentes'] == ['br']
    assert agente.montar(str(tmp_path / 'vazio'), hoje=date(2026, 11, 12))['saude']['dadosVelhos']


def test_situacoes_parecidas_usa_historico_do_proprio_papel():
    import random
    rng = random.Random(3)
    n = 400
    datas = [f'2025-{1 + k // 28:02d}-{1 + k % 28:02d}' for k in range(n)]
    c = [10.0]
    for k in range(1, n):
        x = c[-1] * (1 + rng.gauss(0, 0.005))
        if k == 100:
            x = c[-1] * 0.6          # episódio antigo: -40% num dia
        if k == 150:
            x = c[-1] * 1.5
        if k == n - 10:
            x = c[-1] * 0.4          # hoje: -60% num dia (salto suspeito)
        c.append(x)
    precos = {'ABCD3': {'dates': datas, 'close': c, 'volume': [1000] * (n - 5) + [5000] * 5},
              'CALM3': {'dates': datas, 'close': [10 + 0.001 * k for k in range(n)], 'volume': [1000] * n}}
    indice = {'principal': 'IBOV', 'series': {'IBOV': {'dates': datas, 'close': [100 + 0.01 * k for k in range(n)]}}}
    s = agente.situacoes(precos, {'ABCD3': {'dias': 7.5}}, indice)
    assert [o['p'] for o in s] == ['ABCD3']
    o = s[0]
    assert o['queda60'] > 0.5 and o['diasVendido'] == 7.5 and o['volumeRel'] == 5.0
    assert o['desde'] == datas[n - 10] and o['saltoSuspeito'][0][0] == datas[n - 10]
    assert o['historico']['casos'] == 1 and o['historico']['ultimos'][0][0] == datas[100]
    caso = o['historico']['ultimos'][0]
    assert caso[1] == round(c[120] / c[100] - 1, 4)                      # retorno em 20 pregões
    ri = indice['series']['IBOV']['close'][120] / indice['series']['IBOV']['close'][100] - 1
    assert abs(caso[2] - (c[120] / c[100] - 1 - ri)) < 1e-4


def test_episodios_respeitam_espaco():
    c = [10] * 60 + [6] * 30 + [10] * 10 + [5] * 100
    eps = agente.episodios_queda(c)
    assert eps[0] == 60 and all(b - a >= agente.ESPACO_EPISODIOS for a, b in zip(eps, eps[1:]))


def test_salto_suspeito_desconta_queda_do_indice():
    n = 120
    datas = [f'2026-{1 + k // 28:02d}-{1 + k % 28:02d}' for k in range(n)]
    c = [10.0] * (n - 5) + [4.3] * 5                     # -57% num dia
    ind_geral = [100.0] * (n - 5) + [85.0] * 5           # índice -15% no mesmo dia (queda geral)
    ind_calmo = [100.0] * n
    p = {'VAMO3': {'dates': datas, 'close': c, 'volume': [1000] * n}}
    geral = agente.situacoes(p, {}, {'principal': 'IBOV', 'series': {'IBOV': {'dates': datas, 'close': ind_geral}}})
    calmo = agente.situacoes(p, {}, {'principal': 'IBOV', 'series': {'IBOV': {'dates': datas, 'close': ind_calmo}}})
    assert 'saltoSuspeito' not in geral[0]               # -57% - (-15%) = -42%: não é suspeito
    assert calmo[0]['saltoSuspeito'][0][0] == datas[n - 5]


# ---------------- indicadores técnicos (24/11/2026) ----------------
def _serie(c, faixa=None):
    s = {'close': c, 'volume': [1000] * len(c)}
    if faixa is not None:
        s['high'] = [x + faixa / 2 for x in c]
        s['low'] = [x - faixa / 2 for x in c]
    return s


def test_ifr_serie_so_subindo_e_so_caindo():
    sobe = agente.tecnico(_serie([10 + 0.1 * k for k in range(120)], 0.2))
    cai = agente.tecnico(_serie([30 - 0.1 * k for k in range(120)], 0.2))
    assert sobe['ifr14'] == 100 and sobe['ifr2'] == 100
    assert cai['ifr14'] == 0 and cai['ifr2'] == 0
    assert sobe['mm21'] > 0 > cai['mm21'] and sobe['macdCruz'] == 0


def test_serie_constante_sem_divisao_por_zero():
    t = agente.tecnico(_serie([10.0] * 100, 0))
    assert t['ifr14'] == 50 and t['bbLarg'] == 0 and 'bbPct' not in t and 'estoc' not in t
    assert t['atr'] == 0 and t['macd'] == 0 and t['sup'] == t['res'] == 10
    assert agente.tecnico(_serie([10.0] * 100)) and 'atr' not in agente.tecnico(_serie([10.0] * 100))


def test_atr_com_amplitude_fixa_e_estocastico():
    c = [10.0] * 100
    t = agente.tecnico(_serie(c, 0.5))
    assert t['atr'] == 0.5 and t['atrPct'] == 0.05 and t['estoc'] == 50
    assert agente.tecnico(_serie(c[:59], 0.5)) is None            # menos de 60 fechamentos


def test_tec_no_agente_json_e_menor_que_200kb(tmp_path):
    site = _site(tmp_path)
    assert agente.main(['x', str(site)]) == 0
    txt = (site / 'data' / 'agente.json').read_bytes()
    assert len(txt) < 200 * 1024
    o = json.loads(txt)
    br = o['mercados']['br']['papeis']
    assert any('tec' in v and 'atr' in v['tec'] and 0 <= v['tec']['ifr14'] <= 100 for v in br.values())
    assert 'tec.ifr14/ifr2' in o['legenda'] and 'não testado' in o['legenda']['tec']


# ---------------- dado suspeito, encerrados e alertas (25/11/2026) ----------------
def _datas(n):
    return [f'2026-{1 + k // 28:02d}-{1 + k % 28:02d}' for k in range(n)]


def test_salto_de_escala_anula_campos_caso_raiz4():
    n = 120
    d = _datas(n)
    c = [0.40] * (n - 10) + [10.8] * 4 + [24.4, 21.4, 20.0, 19.0, 18.0, 13.9]   # 0,30 → 10,83 (×40) → 24,4 (×100)
    o = agente.resumo_papel({'dates': d, 'close': c, 'volume': [1000] * n})
    assert 'm1' not in o and 'vol' not in o and 'topo52' not in o and 'tec' not in o
    assert o['p'] == 13.9 and 'd1' in o
    assert any('salto de escala' in x and d[n - 10] in x for x in o['alertasDado'])
    assert sum('salto de escala' in x for x in o['alertasDado']) == 1          # não repete a cada pregão


def test_queda_real_e_geral_nao_anula_caso_movi3():
    n = 120
    d = _datas(n)
    c = [18.67] * (n - 20) + [7.75] * 20                                      # −58,5% no dia
    ind = {d[k]: 0.0 for k in range(n)}
    ind[d[n - 20]] = -0.139                                                   # Ibovespa −13,9% no mesmo dia
    o = agente.resumo_papel({'dates': d, 'close': c, 'volume': [1000] * n}, ret_idx=ind)
    assert o['m1'] == round(7.75 / 18.67 - 1, 4) and 'topo52' in o and 'tec' in o
    assert 'alertasDado' not in o                                             # −58,5% − (−13,9%) = −44,6%: nem alerta
    so = agente.resumo_papel({'dates': d, 'close': c, 'volume': [1000] * n})  # sem queda do índice: só alerta
    assert so['m1'] == o['m1'] and any('queda de -58%' in x for x in so['alertasDado'])


def test_desdobramento_registrado_nao_e_salto():
    n = 80
    d = _datas(n)
    c = [10.0] * 40 + [100.0] * 40
    assert 'alertasDado' in agente.resumo_papel({'dates': d, 'close': c, 'volume': []})
    o = agente.resumo_papel({'dates': d, 'close': c, 'volume': []}, desd=[d[40]])
    assert 'alertasDado' not in o and 'm1' in o


def test_alertas_de_fundamentos():
    al = agente.alertas_fundamentos({'roe': 1.3, 'pe': 422.7, 'netMargin': 0.671, 'operatingMargins': -3.06})
    assert any('ROE' in x for x in al) and any('P/L' in x for x in al) and any('não operacional' in x for x in al)
    assert agente.alertas_fundamentos({'roe': 0.2, 'pe': 15, 'netMargin': 0.1, 'operatingMargins': 0.15}) == []
    assert any('não operacional' in x for x in agente.alertas_fundamentos({'netMargin': 0.5, 'operatingMargins': 0.2}))


def test_vendido_completo_br_e_eua():
    br = agente.vendido_completo({'qtd': 120, 'valor': 600.0, 'precoMedio': 5.0, 'dias': 12.9, 'mercado': 'br'},
                                 {'sharesOutstanding': 6000, 'floatShares': 400})
    assert br == {'qtd': 120, 'valor': 600.0, 'precoMedio': 5.0, 'dias': 12.9, 'pctAcoes': 0.02, 'pctFloat': 0.3}
    us = agente.vendido_completo({'qtd': 50, 'diasFinra': 2.2, 'dataFinra': '2026-11-13', 'mercado': 'us'},
                                 {'floatShares': 1000, 'shortPercentOfFloat': 0.0517, 'shortRatio': 1.9, 'dateShortInterest': '2026-10-30'})
    assert us['pctFloat'] == 0.05 and us['shortPctFloat'] == 0.0517 and us['dataShortInterest'] == '2026-10-30'


def test_encerrados_separados_das_falhas():
    enc, falhas = agente.separar_encerrados(['BTOW3', 'IPA', 'VVAR3', 'NOVO9'])
    assert falhas == ['IPA', 'NOVO9'] and [e['papel'] for e in enc] == ['BTOW3', 'VVAR3']
    assert enc[0]['sucessor'] == 'AMER3' and enc[1]['sucessor'] == 'BHIA3' and enc[0]['ultimaData'] == '2021-07-16'
    s = agente.saude_carteira({'geradoEm': 'x', 'falhas': ['LAME4', 'IPA']})
    assert s['falhas'] == ['IPA'] and s['encerrados'][0]['papel'] == 'LAME4'


def test_radar_vendidos_ve_o_relatorio_inteiro():
    precos = {'AAPL': {'close': [10.0] * 20, 'volume': [1000] * 20}, 'PETR4': {'close': [30.0] * 20, 'volume': [1_000_000] * 20}}
    us = {'fonte': 'FINRA', 'data': '2026-11-13', 'ativos': {
        'GME': {'qtd': 9_000_000, 'diasFinra': 6.2, 'volMedio': 1_500_000, 'variacaoPct': 40.0, 'nome': 'GameStop', 'mercado': 'NYSE'},
        'AAPL': {'qtd': 1_000_000, 'diasFinra': 1.5, 'volMedio': 50_000_000, 'variacaoPct': 1.0, 'mercado': 'NNM'},
        'AABB': {'qtd': 9_000_000, 'diasFinra': 9.0, 'volMedio': 16_000_000, 'mercado': 'OTC'},       # balcão: fora
        'MINI': {'qtd': 2_000, 'diasFinra': 30.0, 'volMedio': 500_000, 'mercado': 'SC'}}}              # posição minúscula: fora
    r = agente.radar_vendidos(us, precos, 'us')
    assert [x[0] for x in r['itens']] == ['GME', 'AAPL']
    assert r['itens'][0] == ['GME', 6.2, 40.0, 1, 'GameStop'] and r['itens'][1][3] == 0
    assert r['papeisNoRelatorio'] == 4 and r['arquivoCompleto'] == 'vendidos-todos-us.json'
    br = {'fonte': 'B3', 'data': '2026-11-24', 'ativos': {
        'PETR4': {'qtd': 5_000_000, 'valor': 150e6}, 'SMAL3': {'qtd': 3_000_000, 'valor': 30e6},
        'NADA3': {'qtd': 1_000_000, 'valor': 6e6}, 'POUCO3': {'qtd': 10, 'valor': 100.0}}}
    vol = {'SMAL3': (500_000, 4e6), 'NADA3': (1_000, 5_000)}                                        # NADA3 sem liquidez
    r = agente.radar_vendidos(br, precos, 'br', vol)
    assert r['itens'] == [['SMAL3', 6.0, 30.0, 1, None], ['PETR4', 5.0, 150.0, 0, None]]
    assert agente.radar_vendidos(None, precos, 'br') is None


def test_volume_cotahist_sem_banco_e_com_banco(tmp_path):
    assert agente.volume_cotahist(None) == {} and agente.volume_cotahist(str(tmp_path / 'nao.duckdb')) == {}
    duckdb = __import__('pytest').importorskip('duckdb')
    banco = str(tmp_path / 'c.duckdb')
    con = duckdb.connect(banco)
    con.execute('CREATE TABLE pregoes (data DATE, codneg VARCHAR, quantidade BIGINT, volume DOUBLE)')
    for k in range(25):
        con.execute("INSERT INTO pregoes VALUES (DATE '2026-10-01' + ?::INTEGER, 'SMAL3', ?, ?)", [k, 100 if k < 5 else 200, 2000.0])
    con.close()
    q, v = agente.volume_cotahist(banco)['SMAL3']
    assert q == 200 and v == 2000.0                                                                   # só os 20 últimos pregões
