"""Testes da coleta, sem rede: requests.get e yfinance são mockados."""
import json
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import fetch_all as fa

HOJE = date(2026, 11, 3)


# ----------------------------------------------------------------------------- utilitários
def serie(n=300, preco=50.0, volume=100_000, fim=HOJE, pular=None):
    """Série sintética de n pregões úteis terminando em `fim`."""
    datas = pd.bdate_range(end=pd.Timestamp(fim), periods=n)
    if pular:
        datas = datas.delete(pular)
    m = len(datas)
    close = [preco * (1 + 0.001 * i) for i in range(m)]
    return {
        'dates': [d.strftime('%Y-%m-%d') for d in datas],
        'open': [c * 0.995 for c in close], 'high': [c * 1.01 for c in close],
        'low': [c * 0.99 for c in close], 'close': close, 'volume': [volume] * m,
    }


class Resp:
    def __init__(self, status=200, payload=None, text=''):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError('sem json')
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


def submissions(lista):
    """lista = [(form, data, items)]"""
    return {'filings': {'recent': {
        'form': [x[0] for x in lista], 'filingDate': [x[1] for x in lista],
        'items': [x[2] for x in lista], 'accessionNumber': [f'0000-00-{i:06d}' for i in range(len(lista))],
        'primaryDocument': ['doc.htm'] * len(lista)}}}


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(fa.time, 'sleep', lambda s: None)
    monkeypatch.setattr(fa, 'SEC_USER_AGENT', 'TesteInvest teste@exemplo.com')
    monkeypatch.setattr(fa, '_sec_ticker_map_cache', None)


# ----------------------------------------------------------------------------- universo
def test_universo_filtra_etf_status_teste_e_normaliza():
    nasdaq = ("Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
              "AAPL|Apple|Q|N|N|100|N|N\nQQQ|Invesco QQQ|G|N|N|100|Y|N\n"
              "ZZZT|Teste|Q|Y|N|100|N|N\nBADX|Falida|Q|N|D|100|N|N\n"
              "File Creation Time: 1103202618:00|||||||\n")
    other = ("ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
             "BRK.B|Berkshire B|N|BRK.B|N|100|N|BRK=B\nSPY|SPDR|P|SPY|Y|100|N|SPY\n"
             "BAC$B|BofA pref|N|BACpB|N|100|N|BAC-B\n"
             "File Creation Time: 1103202618:00|||||||\n")
    assert fa.parse_nasdaq_listed(nasdaq) == ['AAPL']
    assert fa.parse_other_listed(other) == ['BRK-B']


# ----------------------------------------------------------------------------- pré-filtros
def test_prefiltro_de_liquidez_e_historico():
    todos = {
        'LIQ': serie(300, preco=50, volume=100_000),     # ~US$ 5,7 mi/dia
        'ILIQ': serie(300, preco=5, volume=100_000),     # ~US$ 0,6 mi/dia
        'CURTO': serie(200, preco=50, volume=1_000_000),  # líquido mas < 250 pregões
        'GRANDE': serie(300, preco=100, volume=200_000),  # ~US$ 26 mi/dia
    }
    filtrado = fa.aplicar_prefiltro_precos(todos, min_adtv=2_000_000, min_pregoes=250)
    assert set(filtrado) == {'LIQ', 'GRANDE'}
    assert fa.selecionar_pool_fundamentos(filtrado, min_adtv=10_000_000) == ['GRANDE']


def test_adtv20_igual_ao_screener():
    s = serie(30, preco=10, volume=1000)
    esperado = sum(c * v for c, v in zip(s['close'][-20:], s['volume'][-20:])) / 20
    assert fa.adtv20(s) == pytest.approx(esperado)


def test_remove_series_duplicadas():
    a = serie(260)
    todos = {'AAA': a, 'BBB': dict(a), 'CCC': serie(260, preco=70)}
    removidos = fa.remover_duplicatas(todos)
    assert removidos == ['BBB'] and set(todos) == {'AAA', 'CCC'}


def test_arredondamento():
    assert fa.arredondar_preco(123.456789) == 123.46
    assert fa.arredondar_preco(0.123456) == 0.1235
    r = fa.arredondar_serie({'dates': ['2026-01-02'], 'open': [1.005], 'high': [2.0], 'low': [0.5],
                             'close': [0.99999], 'volume': [12.0]})
    assert r['volume'] == [12] and isinstance(r['volume'][0], int)
    assert r['low'] == [0.5] and r['close'] == [1.0]


# ----------------------------------------------------------------------------- divisão por tamanho
def test_divisao_dos_arquivos_por_tamanho_e_ida_e_volta():
    precos = {f'T{i:03d}': fa.arredondar_serie(serie(300, preco=10 + i)) for i in range(40)}
    precos['GAP'] = fa.arredondar_serie(serie(300, pular=[100, 101]))  # série com buraco
    limite = 60_000
    arquivos = fa.montar_arquivos_precos(precos, max_bytes=limite)
    assert len(arquivos) > 1
    assert [n for n, _ in arquivos] == [f'precos_{i:03d}.json' for i in range(len(arquivos))]
    for _, b in arquivos:
        assert len(b) <= limite
    remontado = {}
    for _, b in arquivos:
        obj = json.loads(b)
        assert obj['formato'] == 'colunar-v1'
        remontado.update(fa.expandir_arquivo_precos(obj))
    assert remontado == precos
    obj_gap = next(json.loads(b) for _, b in arquivos if 'GAP' in json.loads(b)['ativos'])
    assert 'dates' in obj_gap['ativos']['GAP'] and 'i0' not in obj_gap['ativos']['GAP']
    assert 'i0' in obj_gap['ativos'].get('T000', {'i0': 0})


def test_formato_compacto_economiza_espaco():
    precos = {f'T{i}': fa.arredondar_serie(serie(1260, preco=20 + i, volume=1_234_567)) for i in range(20)}
    compacto = sum(len(b) for _, b in fa.montar_arquivos_precos(precos))
    antigo = len(json.dumps(precos, separators=(',', ':')))
    assert compacto < 0.8 * antigo


def test_reduz_para_3_anos_quando_passa_do_limite():
    precos = {f'T{i}': serie(1260, preco=20 + i) for i in range(5)}
    _, anos, avisos = fa.gerar_saida(precos, 5, limite_bytes=10_000_000)
    assert anos == 5 and not avisos
    arquivos, anos, avisos = fa.gerar_saida(precos, 5, limite_bytes=100_000)
    assert anos == 3 and any('reduzido de 5 para 3' in a for a in avisos)
    dados = fa.expandir_arquivo_precos(json.loads(arquivos[0][1]))
    primeira = min(s['dates'][0] for s in dados.values())
    assert primeira > '2023-11-03'


# ----------------------------------------------------------------------------- manifesto
def test_manifesto():
    m = fa.montar_manifesto('2026-11-03T22:40:00Z', '2026-11-03', 5, ['precos_000.json', 'precos_001.json'],
                            {'tickersPrecos': 10, 'tickersFundamentos': 3, 'fundamentosAtualizadosHoje': 1,
                             'alertasCriticos': 0})
    assert m['versao'] == 2 and m['arquivoFundamentos'] == 'fundamentos.json'
    assert m['arquivosPrecos'] == ['precos_000.json', 'precos_001.json']
    assert m['ultimoPregao'] == '2026-11-03' and m['anosHistorico'] == 5
    assert set(m['stats']) >= {'tickersPrecos', 'tickersFundamentos', 'fundamentosAtualizadosHoje', 'alertasCriticos'}
    json.dumps(m)


# ----------------------------------------------------------------------------- radar 8-K
def _mock_sec(monkeypatch, payload, status=200):
    chamadas = []

    def fake_get(url, headers=None, timeout=None):
        chamadas.append((url, headers))
        return Resp(status, payload)
    monkeypatch.setattr(fa.requests, 'get', fake_get)
    return chamadas


def test_radar_critico(monkeypatch):
    chamadas = _mock_sec(monkeypatch, submissions([('8-K', '2026-10-01', '1.01,9.01'),
                                                   ('8-K', '2026-09-15', '3.01'),
                                                   ('10-Q', '2026-08-01', '')]))
    r = fa.fetch_corporate_events('XYZ', '0000000123', HOJE)
    assert r['ok'] and r['nivel'] == 'critico'
    assert [e['item'] for e in r['eventos']] == ['1.01', '3.01']
    assert r['eventos'][0]['url'] == 'https://www.sec.gov/Archives/edgar/data/123/000000000000/doc.htm'
    assert chamadas[0][1]['User-Agent'] == 'TesteInvest teste@exemplo.com'


def test_radar_atencao(monkeypatch):
    _mock_sec(monkeypatch, submissions([('8-K', '2026-10-01', '2.01')]))
    r = fa.fetch_corporate_events('XYZ', '0000000123', HOJE)
    assert r['nivel'] == 'atencao' and len(r['eventos']) == 1


def test_radar_sem_evento_e_ignora_antigos(monkeypatch):
    _mock_sec(monkeypatch, submissions([('8-K', '2026-10-01', '5.02,9.01'),
                                        ('8-K', '2025-01-10', '1.03')]))  # falência antiga (> 180 dias)
    r = fa.fetch_corporate_events('XYZ', '0000000123', HOJE)
    assert r == {'nivel': None, 'eventos': [], 'ok': True, 'balancos': []}


def test_radar_falha_sinaliza_nao_ok(monkeypatch):
    _mock_sec(monkeypatch, None, status=404)
    assert fa.fetch_corporate_events('XYZ', '0000000123', HOJE)['ok'] is False


# ----------------------------------------------------------------------------- cache incremental
class FakeTicker:
    chamados = []
    falhar = set()

    def __init__(self, t):
        self.t = t
        FakeTicker.chamados.append(t)

    def get_info(self):
        if self.t in FakeTicker.falhar:
            raise RuntimeError('Too Many Requests')
        return {'trailingPE': 15.0, 'priceToBook': 2.0, 'returnOnEquity': 0.2, 'debtToEquity': 50.0,
                'profitMargins': 0.12, 'revenueGrowth': 0.08, 'longName': f'{self.t} Inc', 'currentPrice': 99.0}

    @property
    def calendar(self):
        return {'Earnings Date': [date(2026, 11, 20)]}


@pytest.fixture
def fake_yf(monkeypatch):
    FakeTicker.chamados = []
    FakeTicker.falhar = set()
    monkeypatch.setattr(fa, 'yf', SimpleNamespace(Ticker=FakeTicker))
    monkeypatch.setattr(fa, 'HAS_YFINANCE', True)
    return FakeTicker


def test_cache_incremental(monkeypatch, fake_yf):
    _mock_sec(monkeypatch, submissions([]))
    recente = (HOJE - timedelta(days=2)).isoformat()
    velho = (HOJE - timedelta(days=10)).isoformat()
    cache = {
        'RECENTE': {'pe': 11.0, 'longName': 'Recente', 'atualizadoEm': recente, 'fonte': 'yfinance'},
        'VELHO': {'pe': 30.0, 'longName': 'Velho', 'atualizadoEm': velho, 'fonte': 'yfinance'},
        'FALHA': {'pe': 40.0, 'roe': 0.3, 'longName': 'Falha', 'atualizadoEm': velho, 'fonte': 'yfinance'},
        'FORA': {'pe': 1.0, 'atualizadoEm': recente},  # saiu do pool
    }
    fake_yf.falhar = {'FALHA'}
    pool = ['RECENTE', 'VELHO', 'FALHA', 'NOVO']
    precos = {t: 100.0 for t in pool}
    sec_map = {t: f'{i:010d}' for i, t in enumerate(pool, 1)}
    out, st = fa.atualizar_fundamentos(pool, cache, precos, HOJE, sec_map, dormir=False)

    assert 'RECENTE' not in fake_yf.chamados                     # recente não é re-buscado
    assert set(fake_yf.chamados) == {'VELHO', 'FALHA', 'NOVO'}
    assert fake_yf.chamados[0] == 'NOVO'                          # novos primeiro
    assert out['RECENTE']['pe'] == 11.0 and out['RECENTE']['atualizadoEm'] == recente
    assert out['VELHO']['pe'] == 15.0 and out['VELHO']['atualizadoEm'] == HOJE.isoformat()
    assert out['FALHA']['pe'] == 40.0 and out['FALHA']['atualizadoEm'] == velho  # falha mantém cache
    assert out['NOVO']['nextEarningsDate'] == '2026-11-20'
    assert out['NOVO']['debtToEquity'] == pytest.approx(0.5)
    assert 'FORA' not in out
    assert all(out[t]['price'] == 100.0 for t in pool)            # preço atualizado do dia
    assert st['atualizadosHoje'] == 2 and st['falhasMantidasDoCache'] == 1


def test_radar_falho_mantem_alerta_do_cache(monkeypatch, fake_yf):
    _mock_sec(monkeypatch, None, status=503)
    recente = (HOJE - timedelta(days=1)).isoformat()
    cache = {'MKTX': {'pe': 20.0, 'atualizadoEm': recente, 'alertaEvento': 'critico',
                      'eventosCorporativos': [{'item': '1.03'}]}}
    out, st = fa.atualizar_fundamentos(['MKTX'], cache, {'MKTX': 10.0}, HOJE, {'MKTX': '0000000001'}, dormir=False)
    assert out['MKTX']['alertaEvento'] == 'critico' and st['radarFalhas'] == 1
    assert st['alertasCriticos'] == 1


def test_orcamento_de_tempo(monkeypatch, fake_yf):
    _mock_sec(monkeypatch, submissions([]))
    relogio = iter(range(0, 1000, 10))
    pool = [f'T{i}' for i in range(10)]
    out, st = fa.atualizar_fundamentos(pool, {}, {}, HOJE, {}, orcamento_seg=25, dormir=False,
                                       relogio=lambda: next(relogio))
    assert st['orcamentoEsgotado'] and st['pendentes'] > 0
    assert set(out) == set(pool)                                   # pendentes entram vazios, sem data
    assert sum(1 for r in out.values() if r['atualizadoEm'] is None) == st['pendentes']


def test_yahoo_bloqueado_interrompe(monkeypatch, fake_yf):
    _mock_sec(monkeypatch, submissions([]))
    monkeypatch.setattr(fa, 'MAX_FALHAS_SEGUIDAS_YAHOO', 3)
    pool = [f'T{i}' for i in range(10)]
    fake_yf.falhar = set(pool)
    out, st = fa.atualizar_fundamentos(pool, {}, {}, HOJE, {}, dormir=False)
    assert st['yahooInterrompido'] and len(fake_yf.chamados) == 3


# ----------------------------------------------------------------------------- portão de qualidade
def _manif(n, pregao='2026-11-03'):
    return {'ultimoPregao': pregao, 'stats': {'tickersPrecos': n}}


FUND_OK = {'AAPL': {'pe': 20.0}}


def test_portao_bloqueia_queda_maior_que_30pct():
    erros = fa.portao_qualidade(_manif(690), _manif(1000), FUND_OK, HOJE)
    assert any('queda' in e for e in erros)


def test_portao_aceita_queda_menor_e_primeira_execucao():
    assert fa.portao_qualidade(_manif(750), _manif(1000), FUND_OK, HOJE) == []
    assert fa.portao_qualidade(_manif(100), None, FUND_OK, HOJE) == []


def test_portao_bloqueia_pregao_velho_e_sem_fundamentos():
    erros = fa.portao_qualidade(_manif(1000, '2026-10-28'), None, FUND_OK, HOJE)
    assert any('Último pregão' in e for e in erros)
    assert fa.portao_qualidade(_manif(1000, '2026-10-29'), None, FUND_OK, HOJE) == []
    erros = fa.portao_qualidade(_manif(1000), None, {'X': {'pe': None, 'fonte': 'indisponivel'}}, HOJE)
    assert any('Nenhum fundamento' in e for e in erros)


# ----------------------------------------------------------------------------- ponta a ponta (main)
NASDAQ_TXT = ("Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
              "AAA|A|Q|N|N|100|N|N\nBBB|B|Q|N|N|100|N|N\nCCC|C|Q|N|N|100|N|N\nETFX|E|Q|N|N|100|Y|N\n"
              "File Creation Time: x|||||||\n")
OTHER_TXT = ("ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
             "DDD.B|D|N|DDD.B|N|100|N|DDD=B\nFile Creation Time: x|||||||\n")


def _df_download(tickers, n=300):
    idx = pd.bdate_range(end=pd.Timestamp(date.today()), periods=n)
    frames = {}
    for k, t in enumerate(tickers):
        base = 20 + 10 * k
        close = np.linspace(base, base * 1.2, n)
        vol = {'AAA': 2_000_000, 'BBB': 300_000, 'CCC': 1_000, 'DDD-B': 10_000}.get(t, 100_000)
        frames[t] = pd.DataFrame({'Open': close, 'High': close * 1.01, 'Low': close * 0.99,
                                  'Close': close, 'Volume': vol}, index=idx)
    return pd.concat(frames, axis=1)


def test_main_ponta_a_ponta(monkeypatch, tmp_path, fake_yf):
    hoje = date.today()

    def fake_get(url, headers=None, timeout=None):
        if 'nasdaqlisted' in url:
            return Resp(text=NASDAQ_TXT)
        if 'otherlisted' in url:
            return Resp(text=OTHER_TXT)
        if url.endswith('manifest.json') or url.endswith('fundamentos.json'):
            return Resp(404)
        if 'company_tickers' in url:
            return Resp(payload={'0': {'ticker': 'AAA', 'cik_str': 1}, '1': {'ticker': 'BBB', 'cik_str': 2}})
        if 'submissions/CIK0000000002' in url:
            return Resp(payload=submissions([('8-K', hoje.isoformat(), '1.03')]))
        if 'submissions' in url:
            return Resp(payload=submissions([]))
        return Resp(404)

    monkeypatch.setattr(fa.requests, 'get', fake_get)
    monkeypatch.setattr(fa, 'yf', SimpleNamespace(Ticker=FakeTicker, download=lambda t, **k: _df_download(t)))
    monkeypatch.setenv('TICKER_LIMIT', '10')
    resumo = tmp_path / 'resumo.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(resumo))
    saida = tmp_path / 'data'

    assert fa.main(['--saida', str(saida), '--url-publicado', 'https://exemplo.invalid/data/']) == 0

    m = json.loads((saida / 'manifest.json').read_text())
    assert m['versao'] == 2 and m['ultimoPregao'] == hoje.isoformat() and m['anosHistorico'] == 5
    assert m['arquivosPrecos'] == ['precos_000.json']
    # AAA (~US$ 50 mi/dia) e BBB (~US$ 10 mi/dia) passam; CCC e DDD-B são ilíquidos; ETFX é ETF
    assert m['stats']['tickersPrecos'] == 2
    precos = fa.expandir_arquivo_precos(json.loads((saida / 'precos_000.json').read_text()))
    assert set(precos) == {'AAA', 'BBB'} and len(precos['AAA']['dates']) == 300
    fund = json.loads((saida / 'fundamentos.json').read_text())
    assert set(fund) == {'AAA', 'BBB'}
    assert fund['BBB']['alertaEvento'] == 'critico' and m['stats']['alertasCriticos'] == 1
    assert m['stats']['fundamentosAtualizadosHoje'] == 2
    assert 'Coleta concluída' in resumo.read_text()


def test_main_bloqueia_queda_de_tickers(monkeypatch, tmp_path, fake_yf):
    def fake_get(url, headers=None, timeout=None):
        if 'nasdaqlisted' in url:
            return Resp(text=NASDAQ_TXT)
        if 'otherlisted' in url:
            return Resp(text=OTHER_TXT)
        if url.endswith('manifest.json'):
            return Resp(payload={'ultimoPregao': date.today().isoformat(), 'stats': {'tickersPrecos': 3000}})
        if url.endswith('fundamentos.json'):
            return Resp(payload={})
        if 'company_tickers' in url:
            return Resp(payload={})
        return Resp(404)

    monkeypatch.setattr(fa.requests, 'get', fake_get)
    monkeypatch.setattr(fa, 'yf', SimpleNamespace(Ticker=FakeTicker, download=lambda t, **k: _df_download(t)))
    monkeypatch.delenv('TICKER_LIMIT', raising=False)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    assert fa.main(['--saida', str(tmp_path / 'd')]) == 2


def test_main_exige_user_agent_no_actions(monkeypatch, tmp_path):
    monkeypatch.setattr(fa, 'SEC_USER_AGENT', '')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    assert fa.main(['--saida', str(tmp_path / 'd')]) == 3


def test_extrair_series_aceita_formatos_do_yfinance():
    df = _df_download(['AAA', 'BBB'], n=30)
    a = fa.extrair_series(df, ['AAA', 'BBB', 'ZZZ'])
    assert set(a) == {'AAA', 'BBB'}
    invertido = df.swaplevel(0, 1, axis=1)  # (Price, Ticker), formato de group_by='column'
    assert fa.extrair_series(invertido, ['AAA']) == {'AAA': a['AAA']}
    simples = df['AAA']                      # colunas simples (1 ticker)
    assert fa.extrair_series(simples, ['AAA']) == {'AAA': a['AAA']}
    com_nan = df.copy()
    com_nan.iloc[5, com_nan.columns.get_loc(('AAA', 'Close'))] = np.nan
    assert len(fa.extrair_series(com_nan, ['AAA'])['AAA']['dates']) == 29


def test_radar_guarda_datas_de_balanco(monkeypatch):
    _mock_sec(monkeypatch, submissions([('8-K', '2026-08-06', '2.02,9.01'), ('8-K', '2026-07-01', '5.02'),
                                        ('8-K', '2026-05-07', '2.02')]))
    r = fa.fetch_corporate_events('XYZ', '0000000123', HOJE)
    assert r['balancos'] == ['2026-05-07', '2026-08-06'] and r['nivel'] is None


def test_estimar_proximo_balanco():
    from datetime import date
    hoje = date(2026, 11, 4)
    # mesmo trimestre do ano anterior + 364 dias
    assert fa.estimar_proximo_balanco(['2025-11-06', '2026-02-20', '2026-05-07', '2026-08-06'], hoje) == '2026-11-05'
    # já divulgou este trimestre: pula para o próximo
    assert fa.estimar_proximo_balanco(['2025-11-03', '2026-02-20', '2026-05-07', '2026-08-06', '2026-11-02'], hoje) == '2027-02-19'
    # pouco histórico: último + 91 dias
    assert fa.estimar_proximo_balanco(['2026-09-01'], hoje) == '2026-12-01'
    assert fa.estimar_proximo_balanco([], hoje) is None
