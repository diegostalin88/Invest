import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import datas_balanco as db  # noqa: E402


class Resp:
    def __init__(self, dados, status=200):
        self._d, self.status_code = dados, status

    def json(self):
        return self._d


def test_pega_so_8k_com_item_202_inclusive_arquivos_antigos():
    recentes = {'form': ['8-K', '10-Q', '8-K', '8-K/A', '8-K'], 'filingDate': ['2026-10-30', '2026-10-31', '2026-09-01', '2026-08-01', '2026-07-30'],
                'items': ['2.02,9.01', '', '5.02', '2.02', '2.02']}
    antigo = {'form': ['8-K', '8-K'], 'filingDate': ['2019-05-01', '2026-07-30'], 'items': ['2.02', '2.02']}
    urls = []

    def falso(url):
        urls.append(url)
        if url.endswith('CIK0000000001.json'):
            return Resp({'filings': {'recent': recentes, 'files': [{'name': 'CIK0000000001-submissions-001.json'}]}})
        return Resp(antigo)

    assert db.datas_de_balanco('0000000001', falso) == ['2019-05-01', '2026-07-30', '2026-08-01', '2026-10-30']
    assert len(urls) == 2


def test_sec_fora_do_ar_devolve_none():
    assert db.datas_de_balanco('0000000001', lambda url: Resp({}, 503)) is None
    assert db.datas_de_balanco('0000000001', lambda url: None) is None
