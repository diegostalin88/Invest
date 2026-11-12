"""Histórico de balanços do Brasil (dados abertos da CVM) para o app, no mesmo formato do balancos.json dos EUA.

Fontes (https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/):
  - ITR (trimestral) e DFP (anual): DRE, balanço ativo (BPA) e passivo (BPP), consolidado (ou individual, se a
    empresa não publicar consolidado), e o índice com a data de entrega à CVM (DT_RECEB);
  - FCA (valor mobiliário): o código de negociação (PETR4) de cada CNPJ.
Trimestre = linha de 3 meses da DRE do ITR. O 4º trimestre é o ano (DFP) menos os 9 meses do ITR de setembro.
Valores com ESCALA_MOEDA = MIL são multiplicados por 1.000. Os números são os da versão mais recente entregue, e a
data é a da entrega DESSA versão (correção de 07/11/2026: antes era a da primeira entrega, o que fazia um número
retificado parecer conhecido desde a entrega original).
Uso: python coleta/balancos_cvm.py site/data/br [--anos 4]
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from datetime import date, datetime, timezone

BASE = 'https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC'
RE_LUCRO = re.compile(r'^lucro.*preju[ií]zo.*consolidado do per[ií]odo$|^lucro.*preju[ií]zo.*l[ií]quido do per[ií]odo$|^lucro/preju[ií]zo do per[ií]odo$', re.I)
RE_PL = re.compile(r'^patrim[ôo]nio l[íi]quido( consolidado)?$', re.I)
csv.field_size_limit(10_000_000)


def baixar(url, tentativas=4):
    import requests
    for k in range(tentativas):
        try:
            r = requests.get(url, timeout=300)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001 - rede instável: tenta de novo
            if k == tentativas - 1:
                print(f'falhou {url}: {e}', file=sys.stderr)
                return None
            time.sleep(5 * (k + 1))


def linhas(z, nome, cnpjs=None):
    """Linhas do CSV como dicionário; com `cnpjs`, só as dessas empresas (filtro rápido pelo início da linha)."""
    if nome not in z.namelist():
        return
    with z.open(nome) as f:
        texto = io.TextIOWrapper(f, encoding='latin-1')
        cab = next(csv.reader([texto.readline()], delimiter=';'))
        for linha in texto:
            if cnpjs is not None and linha[:18] not in cnpjs:
                continue
            yield dict(zip(cab, next(csv.reader([linha], delimiter=';'))))


def _valor(row):
    try:
        v = float(row['VL_CONTA'])
    except (TypeError, ValueError):
        return None
    return v * 1000 if (row.get('ESCALA_MOEDA') or '').upper() == 'MIL' else v


def _dias(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def mapa_tickers(fca_zip_bytes, tickers):
    """{ticker: cnpj} pelo FCA (valor mobiliário)."""
    z = zipfile.ZipFile(io.BytesIO(fca_zip_bytes))
    nome = next((n for n in z.namelist() if 'valor_mobiliario' in n), None)
    out = {}
    for r in linhas(z, nome) if nome else []:
        t = (r.get('Codigo_Negociacao') or '').strip().upper()
        if t in tickers:
            out[t] = r['CNPJ_Companhia']
    return out


class Acumulador:
    """Junta, por CNPJ, os números de vários ITR/DFP. Fica com a versão mais recente de cada documento e com a data em
    que essa versão foi entregue."""

    def __init__(self, cnpjs):
        self.cnpjs = set(cnpjs)
        self.receb = {}    # (cnpj, dt_refer, tipo) -> data de entrega da versão usada (a mais recente)
        self._versao = {}  # (cnpj, dt_refer, tipo) -> (versão, data de entrega)
        self.dre = {}      # (cnpj, dt_refer, tipo, fonte) -> {(ini, fim, campo): (versao, valor)}
        self.bal = {}      # (cnpj, dt_refer, tipo, fonte) -> {campo: (versao, valor)}

    def ler_zip(self, conteudo, tipo, ano):
        z = zipfile.ZipFile(io.BytesIO(conteudo))
        p = tipo.lower()
        for r in linhas(z, f'{p}_cia_aberta_{ano}.csv', self.cnpjs):
            if r['CNPJ_CIA'] in self.cnpjs:
                k = (r['CNPJ_CIA'], r['DT_REFER'], tipo)
                ver, dt = int(r.get('VERSAO') or 0), r['DT_RECEB']
                atual = self._versao.get(k)
                if atual is None or ver > atual[0] or (ver == atual[0] and dt < atual[1]):
                    self._versao[k] = (ver, dt)
                    self.receb[k] = dt
        com_con = set()
        for fonte in ('con', 'ind'):
            alvo = self.cnpjs if fonte == 'con' else self.cnpjs - com_con   # individual só para quem não tem consolidado
            for r in linhas(z, f'{p}_cia_aberta_DRE_{fonte}_{ano}.csv', alvo):
                if fonte == 'con':
                    com_con.add(r['CNPJ_CIA'])
                if r['CNPJ_CIA'] not in self.cnpjs or r['ORDEM_EXERC'] != 'ÚLTIMO':
                    continue
                cod, ds = r['CD_CONTA'], (r['DS_CONTA'] or '').strip()
                campo = 'rev' if cod == '3.01' else 'gp' if cod == '3.03' else 'ni' if re.fullmatch(r'3\.\d\d', cod) and RE_LUCRO.match(ds) else None
                if not campo:
                    continue
                v = _valor(r)
                if v is None:
                    continue
                d = self.dre.setdefault((r['CNPJ_CIA'], r['DT_REFER'], tipo, fonte), {})
                kk = (r['DT_INI_EXERC'], r['DT_FIM_EXERC'], campo)
                ver = int(r['VERSAO'] or 0)
                if kk not in d or ver >= d[kk][0]:
                    d[kk] = (ver, v)
            for arq, campo_de in ((f'{p}_cia_aberta_BPA_{fonte}_{ano}.csv', lambda c, ds: 'ativo' if c == '1' else None),
                                  (f'{p}_cia_aberta_BPP_{fonte}_{ano}.csv', lambda c, ds: 'passivo' if c == '2' else 'pl' if re.fullmatch(r'2\.\d\d', c) and RE_PL.match(ds) else None)):
                for r in linhas(z, arq, alvo):
                    if r['CNPJ_CIA'] not in self.cnpjs or r['ORDEM_EXERC'] != 'ÚLTIMO':
                        continue
                    campo = campo_de(r['CD_CONTA'], (r['DS_CONTA'] or '').strip())
                    v = _valor(r) if campo else None
                    if v is None:
                        continue
                    d = self.bal.setdefault((r['CNPJ_CIA'], r['DT_REFER'], tipo, fonte), {})
                    ver = int(r['VERSAO'] or 0)
                    if campo not in d or ver >= d[campo][0]:
                        d[campo] = (ver, v)

    def _fonte(self, cnpj, ref, tipo, tabela):
        return tabela.get((cnpj, ref, tipo, 'con')) or tabela.get((cnpj, ref, tipo, 'ind')) or {}

    def empresa(self, cnpj):
        """[[fim, divulgado, receita, lucro, lpa, lucroBruto]] e [[fim, ativo, pl, passivo]] por trimestre."""
        refs = sorted({(k[1], k[2]) for k in self.receb if k[0] == cnpj})
        tri = {}
        for ref, tipo in refs:
            d = self._fonte(cnpj, ref, tipo, self.dre)
            div = self.receb[(cnpj, ref, tipo)]
            if tipo == 'ITR':
                for (ini, fim, campo), (_, v) in d.items():
                    if fim == ref and 80 <= _dias(ini, fim) <= 100:
                        tri.setdefault(fim, {'divulgado': div})[campo] = v
            else:  # DFP: 4º trimestre = ano − 9 meses do ITR de setembro
                ano = {campo: v for (ini, fim, campo), (_, v) in d.items() if fim == ref and 350 <= _dias(ini, fim) <= 380}
                set_ref = f'{ref[:4]}-09-30'
                d9 = self._fonte(cnpj, set_ref, 'ITR', self.dre)
                nove = {campo: v for (ini, fim, campo), (_, v) in d9.items() if fim == set_ref and 260 <= _dias(ini, fim) <= 280}
                q = {campo: ano[campo] - nove[campo] for campo in ano if campo in nove}
                if q:   # o 4º trimestre só é conhecido quando as duas entregas (DFP e ITR de setembro) existem
                    div4 = max(div, self.receb.get((cnpj, set_ref, 'ITR'), div))
                    tri.setdefault(ref, {'divulgado': div4}).update(q)
        t = [[fim, x['divulgado'], _int(x.get('rev')), _int(x.get('ni')), None, _int(x.get('gp'))] for fim, x in sorted(tri.items()) if 'ni' in x or 'rev' in x]
        b = []
        for ref, tipo in refs:
            d = self._fonte(cnpj, ref, tipo, self.bal)
            if d.get('ativo'):
                pl = (d.get('pl') or (0, None))[1]
                total = (d.get('passivo') or (0, None))[1]   # conta 2 da CVM = passivo + patrimônio
                passivo = total - pl if total is not None and pl is not None else None
                b.append([ref, _int(d['ativo'][1]), _int(pl), _int(passivo)])
        b = sorted({x[0]: x for x in b}.values())
        return t, b


def _int(v):
    return None if v is None else int(round(v))


def tickers_publicados(pasta):
    man = json.load(open(os.path.join(pasta, 'manifest.json')))
    ts = set()
    for nome in man['arquivosPrecos']:
        o = json.load(open(os.path.join(pasta, nome)))
        ts |= set(o['ativos'] if o.get('formato') == 'colunar-v1' else o)
    return ts


def main(argv=None, baixar=baixar, hoje=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('pasta')
    ap.add_argument('--anos', type=int, default=4)
    ap.add_argument('--trimestres', type=int, default=12)
    a = ap.parse_args(argv)
    hoje = hoje or date.today()
    tickers = tickers_publicados(a.pasta)
    fca = baixar(f'{BASE}/FCA/DADOS/fca_cia_aberta_{hoje.year}.zip') or baixar(f'{BASE}/FCA/DADOS/fca_cia_aberta_{hoje.year - 1}.zip')
    if not fca:
        print('FCA indisponível: nada a fazer')
        return 1
    mapa = mapa_tickers(fca, tickers)
    acc = Acumulador(set(mapa.values()))
    for ano in range(hoje.year - a.anos, hoje.year + 1):
        for tipo in ('ITR', 'DFP'):
            c = baixar(f'{BASE}/{tipo}/DADOS/{tipo.lower()}_cia_aberta_{ano}.zip')
            if c:
                acc.ler_zip(c, tipo, ano)
                print(f'  {tipo} {ano}: ok', flush=True)
    ativos = {}
    for tk, cnpj in sorted(mapa.items()):
        t, b = acc.empresa(cnpj)
        if t:
            ativos[tk] = {'t': t[-(a.trimestres + 4):], 'b': b[-a.trimestres:]}
    if not ativos:
        print('nenhum balanço montado: mantém o que houver')
        return 1
    saida = {'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
             'fonte': 'CVM (ITR e DFP; data de divulgação = 1ª entrega à CVM)',
             'campos': {'t': ['fim', 'divulgado', 'receita', 'lucro', 'lpa', 'lucroBruto'], 'b': ['fim', 'ativo', 'patrimonio', 'passivo']}, 'ativos': ativos}
    with open(os.path.join(a.pasta, 'balancos.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, separators=(',', ':'))
    caminho = os.path.join(a.pasta, 'manifest.json')
    m = json.load(open(caminho, encoding='utf-8'))
    m['arquivoBalancos'] = 'balancos.json'
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    sem = sorted(tickers - set(ativos))
    print(f'balancos.json (Brasil): {len(ativos)} de {len(tickers)} papéis; sem balanço: {", ".join(sem[:40])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
