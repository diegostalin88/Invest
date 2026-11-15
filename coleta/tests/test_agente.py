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
