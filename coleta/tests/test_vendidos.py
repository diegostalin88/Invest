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
    def __init__(self, finra_linhas=None, b3_csv=None, b3_falha_dias=(), sem_ordenacao=False, b3_bdi=None):
        self.finra_linhas, self.b3_csv, self.b3_falha_dias, self.pedidos = finra_linhas or [], b3_csv, set(b3_falha_dias), []
        self.sem_ordenacao, self.b3_bdi = sem_ordenacao, b3_bdi

    def post(self, url, json=None, **k):
        if '/bdi/table/BTBLendingOpenPosition/' in url:
            self.pedidos.append(('bdi', url))
            if self.b3_bdi is None:
                return Resp(status=504)
            pagina = int(url.rstrip('/').split('/')[-2])
            return Resp(payload=self.b3_bdi[pagina - 1])
        self.pedidos.append(('post', json))
        if json.get('sortFields'):
            if self.sem_ordenacao:
                return Resp(texto='{"message":"invalid sort"}', status=400)
            return Resp(payload=[{'settlementDate': '2026-10-15'}])
        filtro = (json.get('compareFilters') or [{}])[0].get('fieldValue')
        if filtro != '2026-10-15':
            return Resp(payload=[])
        ini = json.get('offset', 0)
        return Resp(payload=self.finra_linhas[ini:ini + json['limit']])

    def get(self, url, params=None, **k):
        self.pedidos.append(('get', params))
        if url == v.B3_PEDIDO_URL:
            if self.b3_csv is None:
                return Resp(status=504)
            if params['date'] in self.b3_falha_dias:
                return Resp(status=404)
            return Resp(payload={'token': 'tok-' + params['date']})
        assert url.startswith(v.B3_DOWNLOAD_URL + '?token=tok-')   # token cru no endereço, como a página da B3
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


def test_finra_sem_ordenacao_procura_a_data_dia_a_dia():
    s = SessaoFalsa(finra_linhas=[{'symbolCode': 'AAPL', 'currentShortPositionQuantity': 10}], sem_ordenacao=True)
    dados = v.baixar_finra({'AAPL'}, s, hoje=date(2026, 11, 3))
    assert dados['data'] == '2026-10-15' and dados['ativos']['AAPL']['qtd'] == 10


def _pagina_bdi(linhas, paginas):
    cols = ['RptDt', 'DtRef', 'TckrSymb', 'ISIN', 'Company', 'Type', 'Market', 'StockBalance', 'AvgPric', 'Balance']
    return {'table': {'name': 'BTBLendingOpenPosition', 'pageCount': paginas,
                      'columns': [{'name': c, 'type': 1} for c in cols],
                      'values': [['2026-11-03T00:00:00', '2026-11-03T00:00:00', t, 'BR', 'EMPRESA', '-', m, q, None, val]
                                 for t, m, q, val in linhas]}}


def test_b3_usa_o_boletim_diario_com_linha_total_e_paginas():
    paginas = [_pagina_bdi([('MOVI3', 'Neg. Eletrônica D+1', 1000000, 9500000.0), ('MOVI3', 'Registro', 500000, 4750000.5),
                            ('MOVI3', 'Total', 1500000, 14250000.5)], 2),
               _pagina_bdi([('PETR4', 'Neg. Eletrônica D+0', 300, 9000.0), ('PETR4', 'Registro', 200, 6000.0),   # sem "Total": soma
                            ('VALE3', 'Total', 0, 0), ('XXXX3', 'Total', 10, 10.0)], 2)]
    s = SessaoFalsa(b3_bdi=paginas)
    dados = v.baixar_b3({'MOVI3', 'PETR4', 'VALE3'}, date(2026, 11, 3), s)
    assert dados['data'] == '2026-11-03'
    assert dados['ativos'] == {'MOVI3': {'qtd': 1500000, 'valor': 14250000.5}, 'PETR4': {'qtd': 500, 'valor': 15000.0}}
    urls = [u for tipo, u in s.pedidos if tipo == 'bdi']
    assert urls == [v.B3_BDI_URL.format(d='2026-11-03', p=k, n=v.B3_BDI_POR_PAGINA) for k in (1, 2)]
    assert not any(tipo == 'get' for tipo, _ in s.pedidos)   # nem tentou o arquivo antigo


def test_b3_cai_no_arquivo_antigo_quando_o_boletim_falha():
    dados = v.baixar_b3({'PETR4'}, date(2026, 11, 3), SessaoFalsa(b3_csv=CSV_B3))
    assert dados['ativos'] == {'PETR4': {'qtd': 5000000, 'valor': 150500000.0}}


def test_erro_http_mostra_o_motivo():
    import pytest
    with pytest.raises(RuntimeError, match='invalid sort'):
        v._erro_http(Resp(texto='{"message":"invalid sort"}', status=400), 'FINRA')


def test_coletor_no_brasil_grava_bruto_e_a_coleta_usa_a_copia(tmp_path, monkeypatch):
    """O coletor no Brasil baixa a B3 inteira; a coleta principal (bloqueada pela B3) usa essa cópia recente."""
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    bruto = tmp_path / 'cache' / 'aluguel_b3.json'
    assert v.main(['--somente-b3-bruto', str(bruto)], hoje=date(2026, 11, 3), sessao=SessaoFalsa(b3_csv=CSV_B3)) == 0
    obj = json.loads(bruto.read_text())
    assert {'MOVI3', 'PETR4', 'XXXX3'} <= set(obj['ativos'])          # sem filtro: todos os papéis
    pasta = tmp_path / 'site'
    for p, tk in ((pasta, ['AAPL']), (pasta / 'br', ['MOVI3'])):
        os.makedirs(p, exist_ok=True)
        (p / 'manifest.json').write_text(json.dumps({'arquivosPrecos': ['precos_001.json']}))
        (p / 'precos_001.json').write_text(json.dumps({'formato': 'colunar-v1', 'ativos': {t: {} for t in tk}}))
    bloqueada = SessaoFalsa()   # B3 direta dá 504, FINRA sem dados
    assert v.main(['--saida', str(pasta), '--b3-bruto', str(bruto)], hoje=date(2026, 11, 4), sessao=bloqueada) == 0
    br = json.loads((pasta / 'br' / 'vendidos.json').read_text())
    assert br['ativos'] == {'MOVI3': obj['ativos']['MOVI3']} and 'coletor no Brasil' in br['fonte']
    assert not any(p[0] == 'get' for p in bloqueada.pedidos)          # nem tentou a B3 direta


def test_copia_velha_do_coletor_e_ignorada(tmp_path):
    arq = tmp_path / 'b.json'
    arq.write_text(json.dumps({'data': '2026-10-01', 'ativos': {'MOVI3': {'qtd': 1}}}))
    assert v.ler_b3_bruto(str(arq), {'MOVI3'}, date(2026, 11, 4)) is None
    assert v.ler_b3_bruto(str(tmp_path / 'nao_existe.json'), {'MOVI3'}, date(2026, 11, 4)) is None


def test_token_b3_aceita_formato_novo_redirect():
    assert v._token_b3({'token': 'abc'}) == 'abc'
    assert v._token_b3({'redirectUrl': '~/download?token=R2c+/x=='}) == 'R2c+/x=='
    assert v._token_b3({'redirectUrl': '~/download'}) is None and v._token_b3({}) is None
