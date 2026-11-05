"""Confirmação da hipótese D (deriva depois do balanço), registrada em docs/hipotese-deriva-confirmacao.md.

Mesmos eventos, surpresa e quintis de D (coleta/testar_fundamentos.py). Só leitura; não muda o app.
Uso: python coleta/confirmar_deriva.py balancos_us.json precos_longos.json [--saida deriva_confirmacao.json]
"""
import argparse
import json
import os
import random
import sys

import numpy as np

from testar_fundamentos import Precos, eventos_d

CUSTO_IDA_VOLTA = 0.002
SORTEIOS = int(os.environ.get('SORTEIOS_D', 500))


def por_trimestre(ev):
    g = {}
    for e in ev:
        g.setdefault(e['tri'], []).append(e)
    return {k: v for k, v in g.items() if len(v) >= 25}


def quintis(grupos, rotulos=None):
    """{tri: (alto, baixo)} com os quintis de surpresa de cada trimestre (rotulos = surpresas embaralhadas)."""
    out = {}
    for k, v in grupos.items():
        s = [e['surpresa'] for e in v] if rotulos is None else rotulos[k]
        q20, q80 = np.percentile(s, 20), np.percentile(s, 80)
        out[k] = ([e for e, x in zip(v, s) if x >= q80], [e for e, x in zip(v, s) if x <= q20])
    return out


def excesso_universo(grupos, Q):
    """Teste 1: deriva do quintil alto menos a média de todos os eventos do mesmo trimestre, depois do custo."""
    media = {k: np.mean([e['deriva'] for e in v]) for k, v in grupos.items()}
    d = [e['deriva'] - media[k] for k, (alto, _) in Q.items() for e in alto]
    return float(np.mean(d)) - CUSTO_IDA_VOLTA


def spread(Q, filtro=lambda e: True):
    a = [e['deriva'] for alto, _ in Q.values() for e in alto if filtro(e)]
    b = [e['deriva'] for _, baixo in Q.values() for e in baixo if filtro(e)]
    return float(np.mean(a) - np.mean(b)) if a and b else None


def carteira(P, eventos, spy):
    """Teste 4: pesos iguais entre as posições abertas; entra no fechamento i+1, sai no i+61; 0,1% na entrada e na saída."""
    n = len(P.cal)
    soma, cont, custo = np.zeros(n), np.zeros(n), np.zeros(n)
    for e in eventos:
        A, i = P.adj[e['t']], e['i']
        ult = A[i + 1]
        for j in range(i + 2, i + 62):
            x = A[j] if A[j] == A[j] else ult
            soma[j] += x / ult - 1
            cont[j] += 1
            ult = x
        custo[i + 2] += 0.001   # a entrada no fechamento de i+1 pesa no primeiro dia da posição
        custo[i + 61] += 0.001
    ret = np.where(cont > 0, (soma - custo) / np.maximum(cont, 1), 0.0)
    S = P.adj[spy]
    rs = np.zeros(n)
    rs[1:] = np.where((S[1:] > 0) & (S[:-1] > 0), S[1:] / S[:-1] - 1, 0.0)
    return ret, rs


def metricas(r):
    v = np.cumprod(1 + r)
    anos = len(r) / 252
    pico = np.maximum.accumulate(v)
    return {'retorno': round(float(v[-1] - 1) * 100, 1), 'anual': round(float(v[-1] ** (1 / anos) - 1) * 100, 2) if anos > 0 else None,
            'quedaMax': round(float((1 - v / pico).max()) * 100, 1)}


def confirmar(P, B, spy):
    ev = eventos_d(P, B, spy)
    grupos = por_trimestre(ev)
    Q = quintis(grupos)
    R = {'eventos': sum(len(v) for v in grupos.values())}
    # 1) contra o próprio universo, com embaralhamento
    exc = excesso_universo(grupos, Q)
    rng = random.Random(11)
    nulo = []
    for _ in range(SORTEIOS):
        rot = {k: rng.sample([e['surpresa'] for e in v], len(v)) for k, v in grupos.items()}
        nulo.append(excesso_universo(grupos, quintis(grupos, rot)))
    R['t1'] = {'excesso': round(exc * 100, 2), 'nuloP50': round(float(np.median(nulo)) * 100, 2), 'nuloP95': round(float(np.percentile(nulo, 95)) * 100, 2)}
    # 2) ano a ano
    anos = {}
    for e in (e for v in grupos.values() for e in v):
        anos.setdefault(e['dia'][:4], 0)
        anos[e['dia'][:4]] += 1
    por_ano = {a: spread(Q, lambda e, a=a: e['dia'][:4] == a) for a in sorted(anos) if anos[a] >= 100}
    por_ano = {a: round(x * 100, 2) for a, x in por_ano.items() if x is not None}
    R['t2'] = {'porAno': por_ano, 'fracaoPositivos': round(sum(x > 0 for x in por_ano.values()) / len(por_ano), 2) if por_ano else 0}
    # 3) só os 200 mais negociados
    g200 = por_trimestre(eventos_d(P, B, spy, top=200))
    s200 = spread(quintis(g200)) if g200 else None
    R['t3'] = {'eventos': sum(len(v) for v in g200.values()), 'spread': None if s200 is None else round(s200 * 100, 2)}
    # 4) carteira contínua
    alto = [e for a, _ in Q.values() for e in a]
    todos = [e for v in grupos.values() for e in v]
    ra, rs = carteira(P, alto, spy)
    rt, _ = carteira(P, todos, spy)
    ini = min(e['i'] for e in todos) + 2
    fim = max(e['i'] for e in todos) + 61
    meio = (ini + fim) // 2
    R['t4'] = {'de': P.cal[ini], 'ate': P.cal[fim], 'meio': P.cal[meio],
               'alto': metricas(ra[ini:fim + 1]), 'todos': metricas(rt[ini:fim + 1]), 'spy': metricas(rs[ini:fim + 1]),
               'metades': [{'alto': metricas(ra[a:b]), 'todos': metricas(rt[a:b]), 'spy': metricas(rs[a:b])} for a, b in ((ini, meio), (meio, fim + 1))]}
    T4 = R['t4']
    c1 = exc > 0 and exc > np.percentile(nulo, 95)
    c2 = R['t2']['fracaoPositivos'] >= 0.6
    c3 = s200 is not None and s200 > 0
    c4 = all(h['alto']['anual'] > h['todos']['anual'] and h['alto']['anual'] > h['spy']['anual'] for h in T4['metades']) \
        and T4['alto']['quedaMax'] <= 1.5 * T4['spy']['quedaMax']
    R['criterios'] = {'excessoUniversoAcimaP95': bool(c1), 'positivoEm60pctDosAnos': bool(c2), 'grandesPositivo': bool(c3),
                      'carteiraVenceTodosESpyNasMetades': bool(c4)}
    R['aprovada'] = bool(c1 and c2 and c3 and c4)
    return R


def resumo(R):
    m = lambda x: f"{x['anual']}% ao ano, queda máx. {x['quedaMax']}%"
    T4 = R['t4']
    return '\n'.join([
        f"## Confirmação de D ({R['eventos']} balanços)", '',
        f"1. Quintil alto menos o próprio trimestre, depois do custo: {R['t1']['excesso']}% (embaralhado p50 {R['t1']['nuloP50']}%, p95 {R['t1']['nuloP95']}%)",
        f"2. Spread por ano: {R['t2']['porAno']} → positivo em {round(R['t2']['fracaoPositivos'] * 100)}% dos anos",
        f"3. Só os 200 mais negociados ({R['t3']['eventos']} balanços): spread {R['t3']['spread']}%",
        f"4. Carteira contínua {T4['de']} a {T4['ate']}: alto {m(T4['alto'])} · todos {m(T4['todos'])} · SPY {m(T4['spy'])}",
        '   Metades: ' + ' | '.join(f"alto {h['alto']['anual']}% · todos {h['todos']['anual']}% · SPY {h['spy']['anual']}%" for h in T4['metades']), '',
        'Critérios: ' + ' · '.join(f"{k} **{'sim' if v else 'não'}**" for k, v in R['criterios'].items()) + f" → **{'CONFIRMADA' if R['aprovada'] else 'NÃO CONFIRMADA'}**", ''])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('balancos')
    ap.add_argument('precos')
    ap.add_argument('--saida', default='deriva_confirmacao.json')
    ap.add_argument('--spy', default='SPY')
    a = ap.parse_args(argv)
    B = json.load(open(a.balancos))
    bruto = json.load(open(a.precos))
    P = Precos(bruto, bruto[a.spy]['dates'])
    B = {t: b for t, b in B.items() if t in P.adj}
    R = confirmar(P, B, a.spy)
    R['registro'] = 'docs/hipotese-deriva-confirmacao.md'
    json.dump(R, open(a.saida, 'w'), indent=1, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    txt = resumo(R)
    print(txt)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write(txt + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
