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
    assert 'compra' in o['aviso'] or 'recomendação' in o['aviso']


def test_dados_velhos_e_mercado_ausente(tmp_path):
    site = tmp_path / 's'
    (site / 'antigo' / 'data').mkdir(parents=True)
    (site / 'antigo' / 'data' / 'manifest.json').write_text(json.dumps({'ultimoPregao': '2026-11-02', 'moeda': 'USD'}))
    o = agente.montar(str(site), hoje=date(2026, 11, 12))
    assert o['saude']['diasUteisDesdeUltimoPregao'] == 8 and o['saude']['dadosVelhos']
    assert o['saude']['mercadosAusentes'] == ['br']
    assert agente.montar(str(tmp_path / 'vazio'), hoje=date(2026, 11, 12))['saude']['dadosVelhos']
