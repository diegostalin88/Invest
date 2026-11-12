import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import carteira_dados as cd  # noqa: E402


def falso_yahoo(simbolo, inicio=None):
    if simbolo in ('FALHA.SA', 'NAOEXISTE'):
        raise RuntimeError('sem dados')
    datas = [f'2026-10-{d:02d}' for d in range(1, 31)]
    base = 50000.0 if simbolo == 'BTC-USD' else 100.0
    desd = [['2026-10-15', 2.0]] if simbolo == 'BOVA11.SA' else []
    return datas, [base + i for i in range(30)], desd


def falso_bcb(serie, inicio=None):
    if serie == 1:   # PTAX só em dias úteis: dia 3 e 4 sem cotação usam a do dia 2
        return [('2026-10-01', 5.0), ('2026-10-02', 5.5), ('2026-10-05', 6.0)]
    if serie == 12:
        return [(f'2026-10-{d:02d}', 0.05) for d in range(1, 31)]
    return [('2026-08-01', 0.2), ('2026-09-01', 0.4)]


def test_monta_e_grava(tmp_path, monkeypatch):
    monkeypatch.setenv('CARTEIRA_EXTRAS', 'SMAL11, FALHA')
    monkeypatch.setenv('CARTEIRA_EUA', 'VOO NAOEXISTE')
    monkeypatch.setattr(cd, 'PADRAO_EUA', ['IONX', 'IONQ'])
    rc = cd.main(['x', str(tmp_path)], baixar_yahoo=falso_yahoo, baixar_bcb=falso_bcb, nomear=lambda s: (s + ' nome', 'ETF'))
    assert rc == 2   # FALHA não veio, mas o arquivo é gravado
    d = json.load(open(tmp_path / 'carteira.json'))
    assert set(d['ativos']) == {'BOVA11', 'IVVB11', 'BTC', 'SMAL11', 'IONX', 'IONQ', 'VOO', 'QTUM'}   # QTUM: setor dos quânticos
    assert d['ativos']['QTUM']['apoio'] is True
    assert d['falhas'] == ['FALHA', 'NAOEXISTE']
    voo = d['ativos']['VOO']   # dólar sem sufixo .SA, convertido pela PTAX do dia (ou a anterior)
    assert voo['moeda'] == 'USD' and voo['fonte'] == 'VOO' and voo['classe'] == 'exterior' and voo['nome'] == 'VOO nome' and voo['tipo'] == 'ETF'
    assert voo['fechUSD'][3] == 103 and voo['fech'][3] == 103 * 5.5 and voo['fech'][4] == 104 * 6.0
    assert d['ativos']['IONX']['alavancado'] == {'base': 'IONQ', 'fator': 2}
    assert 'alavancado' not in voo
    assert d['ptaxSerie'] == {'datas': ['2026-10-01', '2026-10-02', '2026-10-05'], 'valor': [5.0, 5.5, 6.0]}
    assert d['ativos']['BOVA11']['desdobramentos'] == [['2026-10-15', 2.0]]
    btc = d['ativos']['BTC']
    assert btc['fech'][0] == 50000 * 5.0 and btc['fech'][3] == 50003 * 5.5 and btc['fech'][4] == 50004 * 6.0
    assert abs(d['cdi']['acum'][-1] - 1.0005 ** 30) < 1e-9
    assert d['ipca'] == {'meses': ['2026-08', '2026-09'], 'var': [0.2, 0.4]}


def test_nada_baixado_nao_grava(tmp_path, monkeypatch):
    monkeypatch.delenv('CARTEIRA_EXTRAS', raising=False)
    rc = cd.main(['x', str(tmp_path)], baixar_yahoo=lambda s, i=None: None, baixar_bcb=falso_bcb)
    assert rc == 1 and not (tmp_path / 'carteira.json').exists()


def test_bcb_divide_em_janelas_de_10_anos():
    pedidos = []
    def pedir(url, params):
        pedidos.append(params)
        return [{'data': '02/01/2015', 'valor': '0,05'}]
    r = cd.bcb(12, '2010-01-01', pedir=pedir)
    assert len(pedidos) >= 2 and r == [('2015-01-02', 0.05)]


def test_extras_por_arquivo(tmp_path, monkeypatch):
    arq = tmp_path / 'codigos-br.txt'
    arq.write_text('MGLU3\nsmal11\n')
    monkeypatch.setenv('CARTEIRA_EXTRAS', 'SMAL11')
    monkeypatch.setenv('CARTEIRA_EXTRAS_ARQUIVO', str(arq))
    monkeypatch.delenv('CARTEIRA_EUA', raising=False)
    monkeypatch.setattr(cd, 'PADRAO_EUA', [])
    rc = cd.main(['x', str(tmp_path)], baixar_yahoo=falso_yahoo, baixar_bcb=falso_bcb, nomear=lambda s: (s, ''))
    d = json.load(open(tmp_path / 'carteira.json'))
    assert rc == 0 and set(d['ativos']) == {'BOVA11', 'IVVB11', 'BTC', 'SMAL11', 'MGLU3'}
    assert d['ativos']['MGLU3']['fonte'] == 'MGLU3.SA'


def test_setores(tmp_path, monkeypatch):
    monkeypatch.setenv('CARTEIRA_EXTRAS', 'MGLU3 P2LT34')
    monkeypatch.delenv('CARTEIRA_EXTRAS_ARQUIVO', raising=False)
    monkeypatch.setenv('CARTEIRA_EUA', '')
    monkeypatch.delenv('CARTEIRA_EUA_ARQUIVO', raising=False)
    monkeypatch.setattr(cd, 'PADRAO_EUA', ['PLTR', 'IONX', 'SLV'])
    monkeypatch.setitem(cd.SETORES_BR, 'Consumer Cyclical', ('Varejo', ['LREN3', 'MGLU3', 'FALHA']))
    info = {'MGLU3.SA': ('Magazine Luiza', 'EQUITY', 'Consumer Cyclical'), 'P2LT34.SA': ('Palantir DRN', 'EQUITY', 'Technology'), 'PLTR': ('Palantir', 'EQUITY', 'Technology'),
            'IONX': ('IONX', 'ETF', ''), 'SLV': ('iShares Silver', 'ETF', '')}
    rc = cd.main(['x', str(tmp_path)], baixar_yahoo=falso_yahoo, baixar_bcb=falso_bcb, nomear=lambda s: info.get(s, (s, '', '')),
                 fundamentar=lambda s: {'lpa': 1.0, 'vpa': 10.0, 'dividendosAno': {'2024': 0.5}, 'lucros': [], 'fonte': s})
    d = json.load(open(tmp_path / 'carteira.json'))
    A = d['ativos']
    assert rc == 0   # par de setor que falha não conta como falha da coleta
    assert A['MGLU3']['setor'] == {'nome': 'Varejo', 'pares': ['LREN3']} and A['LREN3']['apoio'] is True
    assert A['PLTR']['setor'] == {'nome': 'Tecnologia', 'ref': 'XLK'} and A['XLK']['apoio'] and A['XLK']['moeda'] == 'USD'
    assert A['IONX']['setor'] == {'nome': 'Computação quântica', 'ref': 'QTUM'} and A['QTUM']['apoio']
    assert 'setor' not in A['SLV'] and 'setor' not in A['BOVA11']
    assert d['falhasApoio'] == ['FALHA'] and d['falhas'] == []
    assert A['MGLU3']['fund']['fonte'] == 'MGLU3.SA' and A['PLTR']['fund']['lpa'] == 1.0
    assert 'fund' not in A['IONX'] and 'fund' not in A['SLV'] and 'fund' not in A['LREN3']   # ETF e apoio não têm ficha
    assert 'setor' not in A['P2LT34'] and 'fund' not in A['P2LT34']   # BDR: sem cesta de setor da B3 nem ficha
