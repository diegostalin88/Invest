"""Histórico longo da B3 (COTAHIST) num banco DuckDB em disco (passo B1, 16/11/2026).

Por que: os preços do Brasil na VM só vão até nov/2021 e só têm os papéis que existem hoje (viés de sobrevivência).
O COTAHIST, arquivo oficial da B3, traz todos os negócios desde os anos 1980, inclusive de empresas que faliram,
fecharam o capital ou mudaram de código.

O que grava (tabela `pregoes`, uma linha por papel e pregão): só o mercado à vista (TPMERC 010), com abertura,
máxima, mínima, média, fechamento, número de negócios, quantidade, volume financeiro, ISIN e o fator de cotação já
aplicado (preço por ação). Começa em 1995 por padrão (antes do Real os preços estão em outras moedas).

O que NÃO faz ainda: ajuste por proventos e desdobramentos. Os preços são os de tela de cada dia. Um teste do
Laboratório precisa ajustar (ou usar só janelas sem evento) antes de medir retorno; isso fica para o próximo passo.

Memória: lê o zip do disco linha a linha, grava cada ano num CSV temporário e o DuckDB importa com limite de
memória (padrão 256 MB, 1 thread). Os zips ficam guardados em <pasta do banco>/cotahist/ para não baixar de novo.
O ano corrente é sempre recarregado; anos completos já carregados são pulados.

Uso (na VM): python coleta/cotahist_db.py /srv/invest/cache/cotahist.duckdb [--de 1995] [--ate 2026] [--memoria 256MB]
"""
import argparse
import csv
import io
import os
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import date, datetime, timezone

URL_ANUAL = 'https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP'
USER_AGENT = 'Mozilla/5.0 (Invest historico B3)'
COLUNAS = ['data', 'codneg', 'codbdi', 'especi', 'nomres', 'isin', 'abertura', 'maxima', 'minima', 'media',
           'fechamento', 'negocios', 'quantidade', 'volume']
ESQUEMA = """CREATE TABLE IF NOT EXISTS pregoes (
    data DATE, codneg VARCHAR, codbdi VARCHAR, especi VARCHAR, nomres VARCHAR, isin VARCHAR,
    abertura DOUBLE, maxima DOUBLE, minima DOUBLE, media DOUBLE, fechamento DOUBLE,
    negocios INTEGER, quantidade BIGINT, volume DOUBLE);
CREATE TABLE IF NOT EXISTS carga (ano INTEGER PRIMARY KEY, linhas BIGINT, completo BOOLEAN, em TIMESTAMP);
CREATE OR REPLACE VIEW liquidez_mensal AS
    SELECT strftime(data, '%Y-%m') AS mes, codneg, any_value(isin) AS isin, count(*) AS pregoes,
           sum(volume) / count(*) AS volume_medio, last(fechamento ORDER BY data) AS fechamento
    FROM pregoes WHERE codbdi IN ('02', '12') GROUP BY 1, 2;"""


def ler_linha(linha):
    """Registro de cotação do mercado à vista como tupla na ordem de COLUNAS, ou None."""
    if linha[0:2] != '01' or linha[24:27] != '010':
        return None
    fator = int(linha[210:217] or 1) or 1
    p = lambda a, b: int(linha[a:b]) / 100.0 / fator
    d = linha[2:10]
    return (f'{d[:4]}-{d[4:6]}-{d[6:8]}', linha[12:24].strip(), linha[10:12], linha[39:49].strip(),
            linha[27:39].strip(), linha[230:242].strip(), p(56, 69), p(69, 82), p(82, 95), p(95, 108), p(108, 121),
            int(linha[147:152]), int(linha[152:170]), int(linha[170:188]) / 100.0)


def baixar(ano, pasta, tentativas=5, forcar=False):
    """Baixa o zip do ano para o disco (streaming) e devolve o caminho."""
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f'COTAHIST_A{ano}.ZIP')
    if not forcar and os.path.exists(destino) and zipfile.is_zipfile(destino):
        return destino
    for i in range(tentativas):
        try:
            req = urllib.request.Request(URL_ANUAL.format(ano=ano), headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as r, open(destino + '.tmp', 'wb') as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
            if zipfile.is_zipfile(destino + '.tmp'):   # a B3 às vezes devolve uma página no lugar do zip
                os.replace(destino + '.tmp', destino)
                return destino
            print(f'  {ano}: resposta não é zip', flush=True)
        except Exception as e:  # noqa: BLE001 - rede: tenta de novo
            print(f'  {ano}: falhou ({e})', flush=True)
        if i < tentativas - 1:
            time.sleep(30 * 2 ** i)
    raise RuntimeError(f'COTAHIST {ano}: não consegui baixar')


def linhas_zip(caminho):
    with zipfile.ZipFile(caminho) as z:
        with z.open(z.namelist()[0]) as f:
            yield from io.TextIOWrapper(f, encoding='latin-1')


def conectar(banco, memoria='256MB'):
    import duckdb
    con = duckdb.connect(banco)
    con.execute(f"SET memory_limit='{memoria}'")
    con.execute('SET threads=1')
    con.execute("SET preserve_insertion_order=false")
    con.execute(ESQUEMA)
    return con


def carregar_ano(con, ano, linhas, completo):
    """Troca os pregões do ano pelos de `linhas`. Devolve quantas linhas entraram."""
    n = 0
    with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='', encoding='utf-8') as tmp:
        w = csv.writer(tmp)
        for linha in linhas:
            r = ler_linha(linha)
            if r:
                w.writerow(r)
                n += 1
    try:
        con.execute('BEGIN')
        con.execute("DELETE FROM pregoes WHERE year(data) = ?", [ano])
        if n:
            tipos = "{'data':'DATE','codneg':'VARCHAR','codbdi':'VARCHAR','especi':'VARCHAR','nomres':'VARCHAR','isin':'VARCHAR'," \
                    "'abertura':'DOUBLE','maxima':'DOUBLE','minima':'DOUBLE','media':'DOUBLE','fechamento':'DOUBLE'," \
                    "'negocios':'INTEGER','quantidade':'BIGINT','volume':'DOUBLE'}"
            con.execute(f"INSERT INTO pregoes SELECT * FROM read_csv(?, header=false, columns={tipos})", [tmp.name])
        con.execute("INSERT OR REPLACE INTO carga VALUES (?, ?, ?, ?)",
                    [ano, n, completo, datetime.now(timezone.utc).replace(tzinfo=None)])
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        raise
    finally:
        os.unlink(tmp.name)
    return n


def main(argv=None, baixar_ano=baixar, hoje=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('banco')
    ap.add_argument('--de', type=int, default=1995)
    ap.add_argument('--ate', type=int)
    ap.add_argument('--memoria', default='256MB')
    ap.add_argument('--refazer', action='store_true', help='recarrega também os anos já completos')
    a = ap.parse_args(argv)
    hoje = hoje or date.today()
    ate = a.ate or hoje.year
    con = conectar(a.banco, a.memoria)
    pasta = os.path.join(os.path.dirname(os.path.abspath(a.banco)), 'cotahist')
    feitos = {r[0] for r in con.execute('SELECT ano FROM carga WHERE completo').fetchall()}
    for ano in range(a.de, ate + 1):
        completo = ano < hoje.year
        if ano in feitos and completo and not a.refazer:
            continue
        t0 = time.time()
        zipado = baixar_ano(ano, pasta, forcar=not completo)
        n = carregar_ano(con, ano, linhas_zip(zipado), completo)
        print(f'{ano}: {n} pregões de papéis à vista ({time.time() - t0:.0f}s)', flush=True)
    tot, papeis, d0, d1 = con.execute('SELECT count(*), count(DISTINCT codneg), min(data), max(data) FROM pregoes').fetchone()
    print(f'Banco {a.banco}: {tot} linhas, {papeis} códigos, de {d0} a {d1}')
    con.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
