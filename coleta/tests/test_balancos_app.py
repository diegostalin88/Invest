"""Histórico de balanços para o app (sem rede)."""
import json

import balancos_app as ba


def _b():
    trim = [{'end': f'2025-{m:02d}-30', 'filed': f'2025-{m + 1:02d}-10', 'ni': 100.0 * m, 'rev': 1000.0 * m, 'eps': 1.234 * m, 'gp': 400.0 * m} for m in (3, 6, 9)]
    return {'trim': trim, 'bal': [{'end': '2025-09-30', 'filed': '2025-10-10', 'ativo': 5000.0, 'pl': 2000.0, 'passivo': 3000.0}],
            'anuncios': ['2025-04-01', '2025-09-25', '2025-10-08']}


def test_data_de_divulgacao_usa_o_8k_ate_60_dias():
    assert ba.data_divulgacao('2025-10-10', ['2025-04-01', '2025-10-08']) == '2025-10-08'
    assert ba.data_divulgacao('2025-07-10', ['2025-04-01']) == '2025-07-10'   # 8-K velho demais: vale o 10-Q


def test_compactar_e_gravar(tmp_path):
    c = ba.compactar(_b(), n=12)
    assert c['t'][0] == ['2025-03-30', '2025-04-01', 3000, 300, 3.7, 1200] and c['b'] == [['2025-09-30', 5000, 2000, 3000]]
    (tmp_path / 'bal.json').write_text(json.dumps({'AAA': _b(), 'VAZIO': {'trim': [], 'bal': []}}))
    (tmp_path / 'manifest.json').write_text('{"ultimoPregao": "2025-11-01"}')
    assert ba.main([str(tmp_path / 'bal.json'), str(tmp_path)]) == 0
    out = json.loads((tmp_path / 'balancos.json').read_text())
    assert set(out['ativos']) == {'AAA'} and out['campos']['t'][1] == 'divulgado'
    assert json.loads((tmp_path / 'manifest.json').read_text())['arquivoBalancos'] == 'balancos.json'
