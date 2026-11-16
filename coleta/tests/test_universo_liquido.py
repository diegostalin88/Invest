import json

import universo_liquido as ul


def _dados(pasta, vols):
    ativos = {t: {'i0': 0, 'open': [10] * 70, 'high': [10] * 70, 'low': [10] * 70, 'close': [10] * 70, 'volume': [v] * 70}
              for t, v in vols.items()}
    (pasta / 'precos_000.json').write_text(json.dumps({'formato': 'colunar-v1', 'datas': [], 'ativos': ativos}))


class Resp:
    def __init__(self, obj, erro=False):
        self.obj, self.erro = obj, erro

    def raise_for_status(self):
        if self.erro:
            raise RuntimeError('503')

    def json(self):
        return self.obj


class Sessao:
    def __init__(self, resp):
        self.resp = resp

    def get(self, *a, **k):
        return self.resp


def test_cria_lista_dos_dados_e_reordena(tmp_path):
    d = tmp_path / 'd'; d.mkdir()
    _dados(d, {'A': 100, 'B': 300, 'C': 200, 'D': 50})
    lista, hoje = str(tmp_path / 'lista.txt'), str(tmp_path / 'hoje.txt')
    assert ul.montar(lista, hoje, dados=str(d), n=2) == 0
    assert ul.ler_lista(lista) == ['B', 'C']
    assert ul.ler_lista(hoje) == ['B', 'C']
    d2 = tmp_path / 'd2'; d2.mkdir()
    _dados(d2, {'B': 10, 'C': 200, 'E': 900})
    assert ul.reordenar(lista, str(d2), n=2) == 0
    assert ul.ler_lista(lista) == ['E', 'C']


def test_reordenar_nao_mexe_com_poucos_dados(tmp_path):
    d = tmp_path / 'd'; d.mkdir()
    _dados(d, {'A': 1})
    lista = tmp_path / 'lista.txt'; lista.write_text('X\nY\nZ\n')
    assert ul.reordenar(str(lista), str(d), n=10) == 1
    assert ul.ler_lista(str(lista)) == ['X', 'Y', 'Z']


def test_renovar_soma_candidatos_e_tolera_falha(tmp_path):
    lista, hoje = tmp_path / 'lista.txt', str(tmp_path / 'hoje.txt')
    lista.write_text('AAPL\nMSFT\n')
    rows = [{'symbol': 'NVDA', 'lastsale': '$100.00', 'volume': '1,000'}, {'symbol': 'BRK/B', 'lastsale': '$400', 'volume': '10'},
            {'symbol': 'AAPL', 'lastsale': '$1', 'volume': '1'}, {'symbol': 'ABC^D', 'lastsale': '$9', 'volume': '9'}]
    assert ul.montar(str(lista), hoje, n=3, renovar=True, sessao=Sessao(Resp({'data': {'rows': rows}}))) == 0
    assert ul.ler_lista(hoje) == ['AAPL', 'MSFT', 'NVDA', 'BRK-B']
    assert ul.montar(str(lista), hoje, n=3, renovar=True, sessao=Sessao(Resp({}, erro=True))) == 0
    assert ul.ler_lista(hoje) == ['AAPL', 'MSFT']


def test_sem_lista_e_sem_dados(tmp_path):
    assert ul.montar(str(tmp_path / 'l.txt'), str(tmp_path / 'h.txt')) == 1
