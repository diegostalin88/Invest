"""Índices de referência (SPY/BOVA11), sem rede."""
import json

import indices


def _serie(n=30):
    return [f'2026-01-{i + 1:02d}' for i in range(n)], [100.0 + i for i in range(n)]


def test_grava_indices_e_manifesto(tmp_path):
    (tmp_path / 'br').mkdir()
    for p in (tmp_path, tmp_path / 'br'):
        (p / 'manifest.json').write_text(json.dumps({'ultimoPregao': '2026-01-30'}))
    pedidos = []

    def falso(t):
        pedidos.append(t)
        return None if t == '^BVSP' else _serie()
    assert indices.main(['x', str(tmp_path)], baixar=falso) == 0
    us = json.loads((tmp_path / 'indice.json').read_text())
    assert us['principal'] == 'SPY' and set(us['series']) == {'SPY', '^GSPC'}
    assert us['series']['SPY']['close'][0] == 100.0
    br = json.loads((tmp_path / 'br' / 'indice.json').read_text())
    assert br['principal'] == 'BOVA11.SA' and set(br['series']) == {'BOVA11.SA'}   # o que falhou fica de fora
    for p in (tmp_path, tmp_path / 'br'):
        m = json.loads((p / 'manifest.json').read_text())
        assert m['arquivoIndice'] == 'indice.json' and m['ultimoPregao'] == '2026-01-30'
    assert set(pedidos) == {'SPY', '^GSPC', 'BOVA11.SA', '^BVSP'}


def test_falha_total_nao_mexe_no_manifesto(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}')

    def explode(t):
        raise RuntimeError('429')
    assert indices.main(['x', str(tmp_path)], baixar=explode) == 1
    assert json.loads((tmp_path / 'manifest.json').read_text()) == {}
    assert not (tmp_path / 'indice.json').exists()


def test_principal_cai_para_o_que_veio(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}')
    assert indices.main(['x', str(tmp_path)], baixar=lambda t: _serie() if t == '^GSPC' else None) == 0
    assert json.loads((tmp_path / 'indice.json').read_text())['principal'] == '^GSPC'
