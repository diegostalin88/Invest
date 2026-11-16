import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import focus  # noqa: E402


def linha(ind, data, ano, med):
    return {'Indicador': ind, 'Data': data, 'DataReferencia': ano, 'Mediana': med, 'numeroRespondentes': 100}


LINHAS = [
    linha('Selic', '2026-11-06', '2026', 15.0), linha('Selic', '2026-11-06', '2027', 12.25),
    linha('IPCA', '2026-11-06', '2026', 4.55), linha('IPCA', '2026-11-06', '2027', 4.2),
    linha('Câmbio', '2026-11-06', '2026', 5.4), linha('PIB Total', '2026-11-06', '2026', 2.1),
    linha('IPCA', '2026-10-09', '2026', 4.7), linha('Selic', '2026-10-09', '2027', 12.5),
    linha('IPCA', '2026-10-30', '2026', 4.6),
    linha('IPCA', '2026-11-06', '2030', 3.0),          # ano fora da janela: ignorado
    linha('IGP-M', '2026-11-06', '2026', 9.9),          # indicador fora da lista: ignorado
]


def test_resumir_pega_ultima_e_quatro_semanas_antes():
    r = focus.resumir(LINHAS, date(2026, 11, 15))
    assert r['data'] == '2026-11-06'
    assert r['selic'] == {'2026': 15.0, '2027': 12.25}
    assert r['ipca'] == {'2026': 4.55, '2027': 4.2}
    assert r['cambio'] == {'2026': 5.4} and r['pib'] == {'2026': 2.1}
    assert r['antes']['data'] == '2026-10-09'          # a mais recente com 4 semanas ou mais
    assert r['antes']['ipca'] == {'2026': 4.7}
    assert '2030' not in r['ipca'] and 'igp' not in json.dumps(r).lower()


def test_resumir_vazio():
    assert focus.resumir([], date(2026, 11, 15)) is None


def test_consulta_filtra_base_zero_e_data():
    u = focus.consulta('2026-09-16')
    assert 'baseCalculo%20eq%200' in u and "2026-09-16" in u.replace('%27', "'").replace('%2D', '-')


def test_main_grava_e_tolera_rede_fora(tmp_path):
    ok = focus.main(['x', str(tmp_path)], pedir=lambda url: {'value': LINHAS}, hoje=date(2026, 11, 15))
    assert ok == 0
    d = json.load(open(tmp_path / 'focus.json', encoding='utf-8'))
    assert d['selic']['2026'] == 15.0 and 'Focus' in d['fonte']

    def falha(url):
        raise OSError('sem rede')
    assert focus.main(['x', str(tmp_path / 'b')], pedir=falha, hoje=date(2026, 11, 15)) == 2
    assert not (tmp_path / 'b' / 'focus.json').exists()
