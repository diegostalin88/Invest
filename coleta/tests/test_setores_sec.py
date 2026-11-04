import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import setores_sec as ss  # noqa: E402


class Resp:
    def __init__(self, dados, status=200):
        self._d, self.status_code = dados, status

    def json(self):
        return self._d


def test_le_sic_e_grupo():
    r = ss.setor_da_empresa('1', lambda url: Resp({'sic': '3674', 'sicDescription': 'Semiconductors & Related Devices'}))
    assert r == {'sic': '3674', 'grupo': '36', 'descricao': 'Semiconductors & Related Devices'}


def test_sem_sic_ou_falha():
    assert ss.setor_da_empresa('1', lambda url: Resp({'sic': ''})) is None
    assert ss.setor_da_empresa('1', lambda url: Resp({}, 404)) is None
