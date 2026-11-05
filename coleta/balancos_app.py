"""Histórico de balanços para o app: os últimos trimestres de cada papel, num arquivo leve.

Lê a saída de coleta/balancos_sec.py (EUA, XBRL da SEC, com a data em que cada número ficou público) e grava
`balancos.json` na pasta do mercado, com `arquivoBalancos` no manifest.json. O app calcula a reação do preço
em volta de cada divulgação com os preços que ele já tem.

Formato: {geradoEm, fonte, campos, ativos: {ticker: {t: [[fim, divulgado, receita, lucro, lpa, lucroBruto], ...],
                                                   b: [[fim, ativo, patrimonio, passivo], ...]}}}
`divulgado` é o 8-K de resultado (item 2.02) até 60 dias antes do 10-Q/10-K; sem ele, a data do próprio 10-Q/10-K.
Uso: python coleta/balancos_app.py balancos_us.json site/data [--trimestres 12]
"""
import argparse
import bisect
import json
import os
import sys
from datetime import date, datetime, timezone

CAMPOS_T = ['fim', 'divulgado', 'receita', 'lucro', 'lpa', 'lucroBruto']
CAMPOS_B = ['fim', 'ativo', 'patrimonio', 'passivo']


def data_divulgacao(filed, anuncios):
    k = bisect.bisect_right(anuncios, filed)
    if k and (date.fromisoformat(filed) - date.fromisoformat(anuncios[k - 1])).days <= 60:
        return anuncios[k - 1]
    return filed


def _num(v, casas=0):
    if v is None:
        return None
    return round(v, casas) if casas else int(round(v))


def compactar(b, n=12):
    anuncios = sorted(b.get('anuncios') or [])
    trim = sorted([x for x in b.get('trim', []) if 'ni' in x or 'rev' in x], key=lambda x: x['end'])[-(n + 4):]   # +4 para a comparação com o ano anterior
    t = [[x['end'], data_divulgacao(x['filed'], anuncios), _num(x.get('rev')), _num(x.get('ni')), _num(x.get('eps'), 2), _num(x.get('gp'))] for x in trim]
    bal = sorted([x for x in b.get('bal', []) if x.get('ativo')], key=lambda x: x['end'])[-n:]
    bb = [[x['end'], _num(x.get('ativo')), _num(x.get('pl')), _num(x.get('passivo'))] for x in bal]
    return {'t': t, 'b': bb} if t else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('balancos')
    ap.add_argument('pasta')
    ap.add_argument('--trimestres', type=int, default=12)
    a = ap.parse_args(argv)
    manifesto = os.path.join(a.pasta, 'manifest.json')
    if not os.path.exists(a.balancos) or not os.path.exists(manifesto):
        print('sem balanços ou sem manifest: nada a fazer')
        return 1
    B = json.load(open(a.balancos))
    ativos = {}
    for tk, b in B.items():
        c = compactar(b, a.trimestres)
        if c:
            ativos[tk] = c
    if not ativos:
        print('nenhum papel com balanço: mantém o que houver')
        return 1
    saida = {'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
             'fonte': 'SEC (XBRL dos 10-Q/10-K; data de divulgação pelo 8-K item 2.02)', 'campos': {'t': CAMPOS_T, 'b': CAMPOS_B}, 'ativos': ativos}
    with open(os.path.join(a.pasta, 'balancos.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, separators=(',', ':'))
    m = json.load(open(manifesto, encoding='utf-8'))
    m['arquivoBalancos'] = 'balancos.json'
    with open(manifesto, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print(f'balancos.json: {len(ativos)} papéis, {os.path.getsize(os.path.join(a.pasta, "balancos.json")) // 1024} KB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
