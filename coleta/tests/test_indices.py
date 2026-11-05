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
    assert us['principal'] == 'SPY' and set(us['series']) == {'SPY', '^GSPC', '^IRX'} and us['rendaFixa'] == '^IRX'
    assert us['series']['SPY']['close'][0] == 100.0
    br = json.loads((tmp_path / 'br' / 'indice.json').read_text())
    assert br['principal'] == 'BOVA11.SA' and set(br['series']) == {'BOVA11.SA', 'CDI'}   # o que falhou fica de fora
    for p in (tmp_path, tmp_path / 'br'):
        m = json.loads((p / 'manifest.json').read_text())
        assert m['arquivoIndice'] == 'indice.json' and m['ultimoPregao'] == '2026-01-30'
    assert set(pedidos) == {'SPY', '^GSPC', '^IRX', 'BOVA11.SA', '^BVSP', 'CDI'}


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


def test_so_renda_fixa_nao_grava(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}')
    assert indices.main(['x', str(tmp_path)], baixar=lambda t: _serie() if t == '^IRX' else None) == 1
    assert not (tmp_path / 'indice.json').exists()


def test_acumular_cdi():
    d, v = indices.acumular(['2026-01-02', '2026-01-05', '2026-01-06'], [0.001, 0.002, 0.003])
    assert v[0] == 1 and abs(v[1] - 1.001) < 1e-12 and abs(v[2] - 1.001 * 1.002) < 1e-9   # a taxa do último dia ainda não rendeu


def test_cdi_do_banco_central(monkeypatch):
    import requests

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return [{'data': '05/01/2026', 'valor': '0.05'}, {'data': '02/01/2026', 'valor': '0.05'}, {'data': '06/01/2026', 'valor': '0.05'}]
    pedidos = []
    monkeypatch.setattr(requests, 'get', lambda url, params, timeout: pedidos.append((url, params)) or R())
    d, v = indices.baixar_cdi()
    assert d == ['2026-01-02', '2026-01-05', '2026-01-06'] and abs(v[2] - 1.0005 ** 2) < 1e-9
    assert 'sgs.12' in pedidos[0][0] and pedidos[0][1]['dataInicial'] and pedidos[0][1]['dataFinal']


def test_fechamento_nan_fica_de_fora(tmp_path):
    (tmp_path / 'manifest.json').write_text('{}')
    datas = [f'2026-01-{d:02d}' for d in range(1, 31)]
    precos = [100.0 + k for k in range(30)]
    precos[-1] = float('nan')

    def baixar(t):
        return (datas, precos) if t == 'SPY' else None
    indices.main(['x', str(tmp_path)], baixar=baixar)
    texto = (tmp_path / 'indice.json').read_text()
    assert 'NaN' not in texto
    s = json.loads(texto)['series']['SPY']
    assert len(s['close']) == 29 and s['dates'][-1] == '2026-01-29'
