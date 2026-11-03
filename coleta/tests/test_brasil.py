"""Testes da coleta do Brasil (IBOVESPA), sem rede."""
import json
from datetime import date
from types import SimpleNamespace

import pytest

import brasil
import fetch_all as fa
from test_fetch_all import FakeTicker, Resp, _df_download


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(fa.time, 'sleep', lambda *a, **k: None)
    monkeypatch.setattr(fa, 'SEC_USER_AGENT', 'Teste teste@exemplo.invalid', raising=False)
    monkeypatch.setattr(fa, 'CHUNK_SIZE', 500)   # séries sintéticas repetem entre lotes


@pytest.fixture
def ambiente(monkeypatch):
    FakeTicker.chamados, FakeTicker.falhar = [], set()
    pedidos = []
    monkeypatch.setattr(fa, 'yf', SimpleNamespace(Ticker=FakeTicker, download=lambda t, **k: (pedidos.append(list(t)), _df_download(t))[1]))
    monkeypatch.setattr(fa, 'HAS_YFINANCE', True)
    return pedidos


def _b3(cods):
    return Resp(payload={'page': {}, 'results': [{'cod': c, 'asset': c} for c in cods]})


def test_carteira_da_b3(monkeypatch):
    cods = [f'TST{i}3' for i in range(80)]
    monkeypatch.setattr(fa.requests, 'get', lambda url, **k: _b3(cods))
    assert brasil.baixar_carteira_ibovespa() == (cods, 'B3')


def test_carteira_usa_reserva_se_b3_falhar_ou_vier_curta(monkeypatch):
    reserva = brasil.ler_reserva()
    assert 'PETR4' in reserva and 'VALE3' in reserva and len(reserva) > 60
    monkeypatch.setattr(fa.requests, 'get', lambda url, **k: Resp(503))
    assert brasil.baixar_carteira_ibovespa() == (reserva, 'lista de reserva')
    monkeypatch.setattr(fa.requests, 'get', lambda url, **k: _b3(['PETR4', 'VALE3']))
    assert brasil.baixar_carteira_ibovespa()[1] == 'lista de reserva'


def test_coleta_brasil_ponta_a_ponta(monkeypatch, tmp_path, ambiente):
    cods = ['PETR4', 'VALE3', 'ITUB4'] + [f'X{i:02d}3' for i in range(60)]

    def fake_get(url, **k):
        if 'sistemaswebb3' in url:
            return _b3(cods)
        return Resp(404)
    monkeypatch.setattr(fa.requests, 'get', fake_get)
    saida = tmp_path / 'br'
    linhas = brasil.coletar_brasil(str(saida), 'https://exemplo.invalid/data/br/', date.today())
    assert any('Brasil (IBOVESPA): ✅' in l for l in linhas)
    assert all(t.endswith('.SA') for lote in ambiente for t in lote)          # Yahoo recebe .SA
    m = json.loads((saida / 'manifest.json').read_text())
    assert m['mercado'] == 'br' and m['moeda'] == 'BRL' and m['stats']['tickersPrecos'] == len(cods)
    precos = fa.expandir_arquivo_precos(json.loads((saida / m['arquivosPrecos'][0]).read_text()))
    assert 'PETR4' in precos and 'PETR4.SA' not in precos                     # arquivo sem o sufixo
    fund = json.loads((saida / 'fundamentos.json').read_text())
    assert set(fund) == set(cods) and fund['PETR4']['pe'] == 15.0
    assert 'PETR4.SA' in FakeTicker.chamados                                  # fundamentos via .SA


def test_falha_no_brasil_mantem_publicado(monkeypatch, tmp_path, ambiente):
    publicado = {'manifest.json': {'ultimoPregao': '2026-11-02', 'stats': {'tickersPrecos': 80},
                                   'arquivosPrecos': ['precos_000.json'], 'arquivoFundamentos': 'fundamentos.json'},
                 'precos_000.json': {'formato': 'colunar-v1', 'datas': [], 'ativos': {}},
                 'fundamentos.json': {'PETR4': {'pe': 5.0}}}

    def fake_get(url, **k):
        if 'sistemaswebb3' in url:
            return _b3(['PETR4', 'VALE3'] * 1)   # curta -> reserva
        nome = url.rsplit('/', 1)[-1]
        return Resp(payload=publicado[nome]) if nome in publicado else Resp(404)
    monkeypatch.setattr(fa.requests, 'get', fake_get)
    monkeypatch.setattr(fa, 'yf', SimpleNamespace(Ticker=FakeTicker, download=lambda t, **k: _df_download([])))  # Yahoo vazio
    saida = tmp_path / 'br'
    linhas = brasil.coletar_brasil(str(saida), 'https://exemplo.invalid/data/br/', date.today())
    assert any('mantidos os dados publicados' in l for l in linhas)
    assert json.loads((saida / 'fundamentos.json').read_text()) == {'PETR4': {'pe': 5.0}}


def test_erro_no_brasil_nao_derruba_eua(monkeypatch, tmp_path, ambiente):
    from test_fetch_all import NASDAQ_TXT, OTHER_TXT

    def fake_get(url, headers=None, timeout=None, **k):
        if 'nasdaqlisted' in url:
            return Resp(text=NASDAQ_TXT)
        if 'otherlisted' in url:
            return Resp(text=OTHER_TXT)
        if 'company_tickers' in url:
            return Resp(payload={})
        return Resp(404)
    monkeypatch.setattr(fa.requests, 'get', fake_get)
    monkeypatch.setattr(brasil, 'baixar_carteira_ibovespa', lambda: (_ for _ in ()).throw(RuntimeError('B3 caiu')))
    monkeypatch.delenv('TICKER_LIMIT', raising=False)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    saida = tmp_path / 'data'
    assert fa.main(['--saida', str(saida), '--url-publicado', 'https://exemplo.invalid/data/']) == 0
    assert (saida / 'manifest.json').exists() and not (saida / 'br').exists()
