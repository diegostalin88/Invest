"""Testes da coleta de vendidos (FINRA e B3), sem rede."""
import json
import os
from datetime import date

import vendidos as v


class Resp:
    def __init__(self, payload=None, texto=None, status=200, conteudo=None):
        self._payload, self.status_code = payload, status
        self.content = conteudo if conteudo is not None else (texto or '').encode('utf-8')
        self.text = texto if texto is not None else (json.dumps(payload) if payload is not None else '')

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class SessaoFalsa:
    def __init__(self, finra_linhas=None, b3_csv=None, b3_falha_dias=()):
        self.finra_linhas, self.b3_csv, self.b3_falha_dias, self.pedidos = finra_linhas or [], b3_csv, set(b3_falha_dias), []

    def post(self, url, json=None, **k):
        self.pedidos.append(('post', json))
        if json.get('sortFields'):
            return Resp(payload=[{'settlementDate': '2026-10-15'}])
        ini = json.get('offset', 0)
        return Resp(payload=self.finra_linhas[ini:ini + json['limit']])

    def get(self, url, params=None, **k):
        self.pedidos.append(('get', params))
        if url == v.B3_PEDIDO_URL:
            if params['date'] in self.b3_falha_dias:
                return Resp(status=404)
            return Resp(payload={'token': 'tok-' + params['date']})
        return Resp(conteudo=self.b3_csv.encode('latin-1'))


CSV_B3 = ("Status do Arquivo: Final\n"
          "RptDt;TckrSymb;ISIN;Asst;BalQty;TradAvrgPric;PricFctr;BalVal\n"
          "2026-10-30;MOVI3;BRMOVIACNOR0;MOVI;12.345.678;9,50;1;117.283.941,00\n"
          "2026-10-30;MOVI3;BRMOVIACNOR0;MOVI;1.000;9,50;1;9.500,00\n"
          "2026-10-30;PETR4;BRPETRACNPR6;PETR;5000000;30,10;1;150500000,00\n"
          "2026-10-30;XXXX3;BRXXXXACNOR0;XXXX;10;1,00;1;10,00\n")


def test_numero():
    assert v._numero('12.345.678') == 12345678
    assert v._numero('1234,5') == 1234.5
    assert v._numero('117.283.941,00') == 117283941
    assert v._numero('') == 0 and v._numero(7) == 7


def test_b3_soma_linhas_filtra_universo_e_pula_fim_de_semana():
    s = SessaoFalsa(b3_csv=CSV_B3, b3_falha_dias={'2026-11-03'})
    dados = v.baixar_b3({'MOVI3', 'PETR4'}, date(2026, 11, 3), s)   # terça; falha e volta para segunda
    assert dados['data'] == '2026-11-02'
    assert dados['ativos']['MOVI3']['qtd'] == 12346678
    assert dados['ativos']['PETR4'] == {'qtd': 5000000, 'valor': 150500000.0}
    assert 'XXXX3' not in dados['ativos']


def test_finra_pagina_e_filtra():
    linhas = [{'symbolCode': f'T{k}', 'currentShortPositionQuantity': 100 + k, 'previousShortPositionQuantity': 50,
               'daysToCoverQuantity': 2.5, 'changePercent': 10.0} for k in range(7000)]
    linhas.append({'symbolCode': 'gme', 'currentShortPositionQuantity': 0})
    s = SessaoFalsa(finra_linhas=linhas)
    dados = v.baixar_finra({'T1', 'T6500', 'GME'}, s)
    assert dados['data'] == '2026-10-15'
    assert set(dados['ativos']) == {'T1', 'T6500'}           # GME com posição zero não entra
    assert dados['ativos']['T6500']['qtd'] == 6600
    assert sum(1 for p in s.pedidos if p[0] == 'post') == 3  # data + 2 páginas


def test_main_grava_e_nao_quebra_quando_fonte_falha(tmp_path, monkeypatch):
    def preparar(pasta, tickers):
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, 'manifest.json'), 'w') as f:
            json.dump({'arquivosPrecos': ['precos_001.json']}, f)
        with open(os.path.join(pasta, 'precos_001.json'), 'w') as f:
            json.dump({'formato': 'colunar-v1', 'ativos': {t: {} for t in tickers}}, f)
    preparar(str(tmp_path), ['AAPL'])
    preparar(str(tmp_path / 'br'), ['MOVI3'])
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)

    class SoB3(SessaoFalsa):
        def post(self, *a, **k):
            raise RuntimeError('FINRA fora do ar')
    assert v.main(['--saida', str(tmp_path)], hoje=date(2026, 11, 3), sessao=SoB3(b3_csv=CSV_B3)) == 0
    assert not (tmp_path / 'vendidos.json').exists()            # EUA falhou: sem arquivo, sem erro
    br = json.loads((tmp_path / 'br' / 'vendidos.json').read_text())
    assert br['ativos']['MOVI3']['qtd'] == 12346678 and br['geradoEm'].endswith('Z')
    assert json.loads((tmp_path / 'br' / 'manifest.json').read_text())['arquivoVendidos'] == 'vendidos.json'
    assert 'arquivoVendidos' not in json.loads((tmp_path / 'manifest.json').read_text())
