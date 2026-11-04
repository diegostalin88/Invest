"""Escolha do diário anterior (Pages × cache), sem rede."""
import json

import diario_anterior as da


def test_escolhe_o_mais_recente_e_ignora_invalido():
    a = {'sinais': [1], 'atualizadoEm': '2026-11-03T23:00:00Z'}
    b = {'sinais': [1, 2], 'atualizadoEm': '2026-11-04T23:00:00Z'}
    assert da.escolher(a, b, None, {'x': 1}) is b
    assert da.escolher(None, {'sinais': 'x'}) is None
    c1, c2 = {'alvo': 3, 'dias': 10, 'calculadoEm': '2026-10-01'}, {'alvo': 2, 'dias': 5, 'calculadoEm': '2026-11-01'}
    assert da.escolher(c1, c2, {'alvo': 3}, nome='calibracao.json') is c2


def test_main_usa_o_cache_quando_o_pages_falha(tmp_path, monkeypatch):
    (tmp_path / 'site' / 'br').mkdir(parents=True)
    for p in ('site', 'site/br'):
        (tmp_path / p / 'manifest.json').write_text('{}')
    (tmp_path / 'cache' / 'br').mkdir(parents=True)
    (tmp_path / 'cache' / 'br' / 'diario.json').write_text(json.dumps({'sinais': [{'id': 'A'}], 'atualizadoEm': 'x'}))
    monkeypatch.setattr(da, 'ler_url', lambda url: None)
    assert da.main(['x', str(tmp_path / 'site'), 'https://exemplo/data', str(tmp_path / 'cache')]) == 0
    assert json.loads((tmp_path / 'site' / 'br' / 'diario.json').read_text())['sinais'] == [{'id': 'A'}]
    assert not (tmp_path / 'site' / 'diario.json').exists()
