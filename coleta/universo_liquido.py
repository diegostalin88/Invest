"""Lista dos papéis dos EUA mais negociados, usada pela coleta de mercado na VM (desde 12/11/2026).

Decisão do Diego (12/11/2026): não baixar mais o universo completo (~3.400 papéis), para não esbarrar no
limite do Yahoo com o IP da Oracle. A coleta fica com os N papéis de maior volume financeiro.

Como a lista se mantém atual sem baixar tudo:
  1. Depois de cada coleta, a lista é refeita com os N maiores volumes financeiros médios de 60 pregões
     medidos nos próprios dados coletados (`reordenar`).
  2. Uma vez por mês (`montar --renovar`), entram como candidatos os N maiores volumes do dia na tela de
     ações da Nasdaq (uma única consulta). Eles são coletados naquele dia e, se tiverem volume, ficam na
     lista no passo 1. Se a Nasdaq não responder, a lista continua a mesma.
  3. Sem lista ainda (primeira vez), ela nasce dos dados da última coleta completa (`montar --dados`).

Uso:
  python coleta/universo_liquido.py montar LISTA SAIDA_DO_DIA [--dados PASTA] [--n 500] [--renovar]
  python coleta/universo_liquido.py reordenar LISTA PASTA_DADOS_NOVOS [--n 500]
"""
import argparse
import glob
import json
import os
import sys

import requests

N_PADRAO = 500
JANELA = 60
NASDAQ_TELA = 'https://api.nasdaq.com/api/screener/stocks'


def log(msg):
    print(msg, flush=True)


def ler_lista(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return [l.split('#')[0].strip().upper() for l in f if l.split('#')[0].strip()]
    except OSError:
        return []


def gravar_lista(caminho, tickers, cabecalho):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    tmp = caminho + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(f'# {cabecalho}\n')
        f.write('\n'.join(tickers) + '\n')
    os.replace(tmp, caminho)


def volumes_dos_dados(pasta, janela=JANELA):
    """{ticker: volume financeiro médio dos últimos `janela` pregões} a partir dos precos_NNN.json."""
    vol = {}
    for arq in sorted(glob.glob(os.path.join(pasta, 'precos_*.json'))):
        with open(arq, encoding='utf-8') as f:
            obj = json.load(f)
        ativos = obj.get('ativos') if obj.get('formato') == 'colunar-v1' else obj
        for t, a in (ativos or {}).items():
            c, v = a.get('close') or [], a.get('volume') or []
            pares = [(x, y) for x, y in zip(c[-janela:], v[-janela:]) if x and y]
            if pares:
                vol[t] = sum(x * y for x, y in pares) / len(pares)
    return vol


def maiores(vol, n):
    return [t for t, _ in sorted(vol.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def normalizar(simbolo):
    s = (simbolo or '').strip().upper()
    if not s or '^' in s or '$' in s or ' ' in s:
        return None
    return s.replace('/', '-').replace('.', '-')


def candidatos_nasdaq(n, sessao=requests):
    """Os n maiores volumes financeiros do dia na tela de ações da Nasdaq (sem ETFs). [] se falhar."""
    try:
        r = sessao.get(NASDAQ_TELA, params={'tableonly': 'true', 'limit': 10000, 'download': 'true'}, timeout=30)
        r.raise_for_status()
        linhas = ((r.json().get('data') or {}).get('rows')) or []
    except Exception as e:  # noqa: BLE001 - sem candidatos, a lista segue igual
        log(f'Nasdaq indisponível ({e}); a lista continua a mesma.')
        return []

    def num(x):
        try:
            return float(str(x).replace('$', '').replace(',', '').strip())
        except ValueError:
            return 0.0
    vol = {}
    for l in linhas:
        t = normalizar(l.get('symbol'))
        if t:
            vol[t] = num(l.get('lastsale')) * num(l.get('volume'))
    return maiores({t: v for t, v in vol.items() if v > 0}, n)


def montar(lista, saida, dados=None, n=N_PADRAO, renovar=False, sessao=requests):
    atual = ler_lista(lista)
    if not atual and dados:
        atual = maiores(volumes_dos_dados(dados), n)
        if atual:
            gravar_lista(lista, atual, f'{len(atual)} mais negociados (volume financeiro médio de {JANELA} pregões); criada a partir de {dados}')
            log(f'Lista criada com {len(atual)} papéis a partir de {dados}.')
    novos = []
    if renovar:
        novos = [t for t in candidatos_nasdaq(n, sessao) if t not in set(atual)]
        log(f'Renovação mensal: {len(novos)} candidatos novos da Nasdaq.')
    hoje = atual + novos
    if not hoje:
        log('Sem lista e sem dados para criá-la: a coleta vai usar o universo completo.')
        return 1
    gravar_lista(saida, hoje, f'universo do dia: {len(atual)} da lista + {len(novos)} candidatos')
    log(f'Universo do dia: {len(hoje)} papéis ({len(novos)} candidatos).')
    return 0


def reordenar(lista, pasta, n=N_PADRAO):
    vol = volumes_dos_dados(pasta)
    if len(vol) < n // 2:
        log(f'Só {len(vol)} papéis com dados em {pasta}; a lista não foi mexida.')
        return 1
    antes = set(ler_lista(lista))
    nova = maiores(vol, n)
    gravar_lista(lista, nova, f'{len(nova)} mais negociados (volume financeiro médio de {JANELA} pregões)')
    log(f'Lista refeita: {len(nova)} papéis ({len(set(nova) - antes)} entraram, {len(antes - set(nova))} saíram).')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('montar')
    m.add_argument('lista'); m.add_argument('saida'); m.add_argument('--dados')
    m.add_argument('--n', type=int, default=N_PADRAO); m.add_argument('--renovar', action='store_true')
    r = sub.add_parser('reordenar')
    r.add_argument('lista'); r.add_argument('dados'); r.add_argument('--n', type=int, default=N_PADRAO)
    a = ap.parse_args(argv)
    if a.cmd == 'montar':
        return montar(a.lista, a.saida, a.dados, a.n, a.renovar)
    return reordenar(a.lista, a.dados, a.n)


if __name__ == '__main__':
    sys.exit(main())
