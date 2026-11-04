"""Histórico de vendidos e calibração (sem rede)."""
import json

import historico as h


def test_escolhe_o_mais_longo_e_nunca_um_invalido():
    curto = {'vendidos': {'2026-11-01': {}}, 'calibracao': {}}
    longo = {'vendidos': {'2026-11-01': {}, '2026-11-02': {}}, 'calibracao': {'2026-11-01': {}}}
    assert h.escolher(curto, longo, None, {'x': 1}) is longo
    assert h.escolher(None, {'vendidos': []}) == {'vendidos': {}, 'calibracao': {}}


def test_acrescentar_usa_a_data_do_dado_e_nao_duplica():
    hist = {'vendidos': {}, 'calibracao': {}}
    v = {'data': '2026-11-03', 'fonte': 'B3', 'ativos': {'PETR4': {'qtd': 10}}}
    c = {'alvo': 3, 'dias': 10, 'calculadoEm': '2026-11-04T22:00:00Z'}
    h.acrescentar(hist, v, c)
    h.acrescentar(hist, v, c)
    assert list(hist['vendidos']) == ['2026-11-03'] and list(hist['calibracao']) == ['2026-11-04']
    h.acrescentar(hist, {'data': '2026-11-04', 'ativos': {}}, {'alvo': 3})  # vazio/inválido não entra
    assert len(hist['vendidos']) == 1 and len(hist['calibracao']) == 1


def test_main_junta_cache_dia_novo_e_bruto_da_b3(tmp_path, monkeypatch):
    site, cache = tmp_path / 'site', tmp_path / 'cache'
    (site / 'br').mkdir(parents=True); (cache / 'br').mkdir(parents=True)
    for p in (site, site / 'br'):
        (p / 'manifest.json').write_text('{}')
    (site / 'vendidos.json').write_text(json.dumps({'data': '2026-10-31', 'ativos': {'AAPL': {'qtd': 1}}}))
    (site / 'br' / 'vendidos.json').write_text(json.dumps({'data': '2026-11-03', 'ativos': {'PETR4': {'qtd': 1}}}))
    (site / 'br' / 'calibracao.json').write_text(json.dumps({'alvo': 3, 'dias': 10, 'calculadoEm': '2026-11-01'}))
    (cache / 'br' / 'historico.json').write_text(json.dumps({'vendidos': {'2026-11-02': {'ativos': {}}}, 'calibracao': {}}))
    bruto = tmp_path / 'b3.json'
    bruto.write_text(json.dumps({'data': '2026-11-03', 'ativos': {'PETR4': {'qtd': 1}, 'MOVI3': {'qtd': 9}}}))
    monkeypatch.setattr(h, 'ler_url', lambda url: None)
    assert h.main(['x', str(site), 'https://exemplo/data', str(cache), str(bruto)]) == 0
    br = json.loads((site / 'br' / 'historico.json').read_text())
    assert sorted(br['vendidos']) == ['2026-11-02', '2026-11-03']
    assert 'MOVI3' in br['vendidos']['2026-11-03']['ativos']  # todos os papéis da B3
    assert list(br['calibracao']) == ['2026-11-01']
    us = json.loads((site / 'historico.json').read_text())
    assert list(us['vendidos']) == ['2026-10-31'] and us['calibracao'] == {}
