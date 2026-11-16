import zipfile

import pytest

duckdb = pytest.importorskip('duckdb')
import cotahist_db as cd


def linha(data, codneg, fech, tpmerc='010', codbdi='02', fator=1, vol=1000000, isin='BRPETRACNPR6'):
    l = [' '] * 245
    def put(a, s):
        l[a:a + len(s)] = list(s)
    put(0, '01'); put(2, data); put(10, codbdi); put(12, codneg.ljust(12)); put(24, tpmerc)
    put(27, 'EMPRESA'.ljust(12)); put(39, 'PN'.ljust(10)); put(52, 'R$  ')
    for pos in (56, 69, 82, 95, 108):
        put(pos, f'{int(round(fech * 100)):013d}')
    put(147, '00010'); put(152, f'{1000:018d}'); put(170, f'{vol * 100:018d}'); put(210, f'{fator:07d}')
    put(230, isin.ljust(12))
    return ''.join(l)[:245] + '\n'


def test_ler_linha():
    r = cd.ler_linha(linha('20240102', 'PETR4', 38.5))
    assert r[0] == '2024-01-02' and r[1] == 'PETR4' and r[10] == 38.5 and r[13] == 1000000.0
    assert cd.ler_linha(linha('20240102', 'PETRA38', 1.2, tpmerc='070')) is None    # opção fica de fora
    assert cd.ler_linha('00COTAHIST.2024\n') is None
    assert cd.ler_linha(linha('19970102', 'XXXX4', 1500.0, fator=1000))[10] == 1.5    # cotação por lote de mil


def _zip(tmp_path, ano, linhas):
    p = tmp_path / f'COTAHIST_A{ano}.ZIP'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr(f'COTAHIST_A{ano}.TXT', '00COTAHIST\n' + ''.join(linhas) + '99COTAHIST\n')
    return str(p)


def test_carga_idempotente_e_liquidez(tmp_path):
    from datetime import date
    zips = {2023: _zip(tmp_path, 2023, [linha('20230103', 'OIBR3', 1.0), linha('20231228', 'OIBR3', 0.5)]),
            2024: _zip(tmp_path, 2024, [linha('20240102', 'PETR4', 38.5), linha('20240103', 'PETR4', 39.0)])}
    chamadas = []
    def baixar(ano, pasta, forcar=False):
        chamadas.append((ano, forcar))
        return zips[ano]
    banco = str(tmp_path / 'h.duckdb')
    assert cd.main([banco, '--de', '2023'], baixar_ano=baixar, hoje=date(2024, 6, 1)) == 0
    assert cd.main([banco, '--de', '2023'], baixar_ano=baixar, hoje=date(2024, 6, 1)) == 0
    assert chamadas == [(2023, False), (2024, True), (2024, True)]   # 2023 completo não é baixado de novo
    con = duckdb.connect(banco)
    assert con.execute('SELECT count(*) FROM pregoes').fetchone()[0] == 4   # recarregar 2024 não duplica
    assert con.execute("SELECT codneg FROM liquidez_mensal WHERE mes='2023-12'").fetchall() == [('OIBR3',)]   # papel que sumiu continua no banco
