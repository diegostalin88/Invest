"""Teste das hipóteses C (carteira valor + qualidade) e D (deriva depois do balanço).

Segue o registro em docs/hipotese-fundamentos.md. Só leitura; não muda o app.
Uso: python coleta/testar_fundamentos.py balancos_us.json precos_longos.json [--saida fundamentos_teste.json]
"""
import argparse
import bisect
import json
import os
import random
import sys
from datetime import date, timedelta

import numpy as np

CUSTO, N_CART, TOP_LIQ, PRECO_MIN, SORTEIOS = 0.001, 30, 500, 5.0, int(os.environ.get("SORTEIOS_C", 200))
MESES_REB, MESES_SEM = (2, 5, 8, 11), (5, 11)


# ---------- preços ----------
class Precos:
    def __init__(self, bruto, cal):
        self.cal = cal
        pos = {d: i for i, d in enumerate(cal)}
        n = len(cal)
        self.adj, self.close, self.dv, self.splits = {}, {}, {}, {}
        for t, p in bruto.items():
            a, c, v = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
            for d, x, y, z in zip(p['dates'], p['adj'], p['close'], p['vol']):
                i = pos.get(d)
                if i is not None:
                    a[i], c[i], v[i] = x, y, y * z
            self.adj[t], self.close[t], self.dv[t] = a, c, v
            self.splits[t] = sorted(p.get('splits') or [])

    def fator(self, t, dia):
        """Produto das razões de desdobramento DEPOIS de `dia` (o Yahoo ajusta o passado por elas)."""
        f = 1.0
        for d, r in self.splits[t]:
            if d > dia:
                f *= r
        return f

    def preco_real(self, t, i):
        return self.close[t][i] * self.fator(t, self.cal[i])

    def adtv(self, t, i, n=60):
        x = self.dv[t][max(0, i - n + 1):i + 1]
        x = x[~np.isnan(x)]
        return float(x.mean()) if len(x) >= n * 0.8 else np.nan

    def ultimo_adj(self, t, i, desde):
        a = self.adj[t]
        for j in range(i, desde - 1, -1):
            if a[j] == a[j]:
                return a[j]
        return np.nan


# ---------- fundamentos sem olhar o futuro ----------
def disponivel(lista, dia, chave='filed'):
    """Itens com `filed` < dia (o número só vale no pregão seguinte ao da publicação)."""
    return [x for x in lista if x[chave] < dia]


def fundamentos_em(b, dia, fator_split):
    trim = sorted(disponivel(b['trim'], dia), key=lambda x: x['end'])
    if len(trim) < 4:
        return None
    u = trim[-4:]
    for x, y in zip(u, u[1:]):
        if not (80 <= (date.fromisoformat(y['end']) - date.fromisoformat(x['end'])).days <= 100):
            return None
    if (date.fromisoformat(dia) - date.fromisoformat(u[-1]['end'])).days > 200:
        return None
    if any('ni' not in x or 'gp' not in x for x in u):
        return None
    bal = [x for x in sorted(disponivel(b['bal'], dia), key=lambda x: x['end']) if x.get('ativo') and x.get('pl') is not None]
    ac = sorted(disponivel(b['acoes'], dia), key=lambda x: x['end'])
    if not bal or not ac:
        return None
    return {'ni': sum(x['ni'] for x in u), 'gp': sum(x['gp'] for x in u), 'ativo': bal[-1]['ativo'], 'pl': bal[-1]['pl'],
            'acoes': ac[-1]['v'] * fator_split(ac[-1]['end'])}


def metricas(rets):
    r = np.array(rets)
    if not len(r):
        return None
    v = np.cumprod(1 + r)
    dd = float(np.max(1 - v / np.maximum.accumulate(v)))
    anos = len(r) / 4
    sd = r.std()
    return {'periodos': len(r), 'retorno': round((v[-1] - 1) * 100, 1), 'anual': round((v[-1] ** (1 / anos) - 1) * 100, 1),
            'quedaMax': round(dd * 100, 1), 'sharpe': round(float(r.mean() / sd * 2), 2) if sd > 0 else None}


def metricas_p(rets, por_ano):
    m = metricas(rets)
    if m:
        anos = len(rets) / por_ano
        v = float(np.prod(1 + np.array(rets)))
        m['anual'] = round((v ** (1 / anos) - 1) * 100, 1)
        sd = np.std(rets)
        m['sharpe'] = round(float(np.mean(rets) / sd * np.sqrt(por_ano)), 2) if sd > 0 else None
    return m


# ---------- Hipótese C ----------
def datas_reb(cal, meses):
    fins = [i for i in range(len(cal) - 1) if cal[i][:7] != cal[i + 1][:7]] + [len(cal) - 1]
    return [i for i in fins if int(cal[i][5:7]) in meses]


def elegiveis(P, B, i):
    dia = P.cal[i]
    liq = []
    for t in B:
        if t not in P.adj or P.adj[t][i] != P.adj[t][i]:
            continue
        if P.preco_real(t, i) < PRECO_MIN:
            continue
        a = P.adtv(t, i)
        if a == a:
            liq.append((a, t))
    liq.sort(reverse=True)
    out = []
    for _, t in liq[:TOP_LIQ]:
        f = fundamentos_em(B[t], dia, lambda fim, t=t: P.fator(t, fim))
        if not f or f['pl'] <= 0 or f['ni'] <= 0 or f['acoes'] <= 0 or f['ativo'] <= 0:
            continue
        mcap = P.close[t][i] * f['acoes']  # close ajustado por desdobramento × ações convertidas para a base de hoje
        out.append({'t': t, 'valor': f['ni'] / mcap, 'qualidade': f['gp'] / f['ativo']})
    if not out:
        return out
    for k in ('valor', 'qualidade'):
        ordem = sorted(range(len(out)), key=lambda j: out[j][k])
        for r, j in enumerate(ordem):
            out[j]['p_' + k] = r / max(1, len(out) - 1)
    for x in out:
        x['nota'] = (x['p_valor'] + x['p_qualidade']) / 2
    return out


def rodar(P, periodos, escolher, custo=CUSTO):
    antes, rets = {}, []
    for p in periodos:
        lista = escolher(p)
        if not lista:
            rets.append(0.0)
            antes = {}
            continue
        w = 1 / len(lista)
        novos = {t: w for t in lista}
        giro = sum(abs(novos.get(t, 0) - antes.get(t, 0)) for t in set(novos) | set(antes))
        bruto, deriva = 0.0, {}
        for t in lista:
            a, b = P.adj[t][p['i']], P.ultimo_adj(t, p['i2'], p['i'])
            r = b / a - 1 if a > 0 and b > 0 else 0.0
            bruto += w * r
            deriva[t] = w * (1 + r)
        tot = sum(deriva.values())
        antes = {t: v / tot for t, v in deriva.items()}
        rets.append(bruto - giro * custo)
    return rets


def hipotese_c(P, B, spy):
    reb = datas_reb(P.cal, MESES_REB)
    periodos = []
    for i, i2 in zip(reb, reb[1:]):
        e = elegiveis(P, B, i)
        if len(e) >= 2 * N_CART:
            periodos.append({'i': i, 'i2': i2, 'e': e})
    if not periodos:
        return None
    topo = lambda n, k='nota': (lambda p: [x['t'] for x in sorted(p['e'], key=lambda x: -x[k])[:n]])
    principal = rodar(P, periodos, topo(N_CART))
    todos = rodar(P, periodos, lambda p: [x['t'] for x in p['e']])
    spy_r = [P.adj[spy][p['i2']] / P.adj[spy][p['i']] - 1 for p in periodos]
    rng = random.Random(7)
    acaso = [metricas(rodar(P, periodos, lambda p: rng.sample([x['t'] for x in p['e']], N_CART)))['retorno'] for _ in range(SORTEIOS)]
    # semestral: só maio e novembro, mesmo universo de cada data
    reb_s = datas_reb(P.cal, MESES_SEM)
    per_s = [{'i': i, 'i2': i2, 'e': elegiveis(P, B, i)} for i, i2 in zip(reb_s, reb_s[1:]) if i >= periodos[0]['i']]
    per_s = [p for p in per_s if len(p['e']) >= 2 * N_CART]
    meio = len(periodos) // 2
    m = {'principal': metricas(principal), 'spy': metricas(spy_r), 'pesosIguais': metricas(todos)}
    R = {
        'de': P.cal[periodos[0]['i']], 'ate': P.cal[periodos[-1]['i2']], 'trimestres': len(periodos),
        'elegiveisMedio': round(float(np.mean([len(p['e']) for p in periodos]))),
        **m,
        'acaso': {'p5': round(float(np.percentile(acaso, 5)), 1), 'mediana': round(float(np.median(acaso)), 1), 'p95': round(float(np.percentile(acaso, 95)), 1)},
        'metades': [{'de': P.cal[ps[0]['i']], 'ate': P.cal[ps[-1]['i2']], 'carteira': metricas(principal[a:b]), 'pesosIguais': metricas(todos[a:b]), 'spy': metricas(spy_r[a:b])}
                    for a, b, ps in ((0, meio, periodos[:meio]), (meio, len(periodos), periodos[meio:]))],
        'robustez': {
            'soValor': metricas(rodar(P, periodos, topo(N_CART, 'valor'))),
            'soQualidade': metricas(rodar(P, periodos, topo(N_CART, 'qualidade'))),
            'top15': metricas(rodar(P, periodos, topo(15))), 'top60': metricas(rodar(P, periodos, topo(60))),
            'custo2x': metricas(rodar(P, periodos, topo(N_CART), CUSTO * 2)),
            'semestral': metricas_p(rodar(P, per_s, topo(N_CART)), 2) if per_s else None,
        },
        'carteiraAtual': topo(N_CART)({'e': elegiveis(P, B, len(P.cal) - 1)}),
    }
    c1 = R['principal']['retorno'] > R['acaso']['p95']
    c2 = R['principal']['anual'] > R['spy']['anual'] and R['principal']['quedaMax'] <= 1.5 * R['spy']['quedaMax']
    c3 = all(h['carteira']['retorno'] > h['pesosIguais']['retorno'] for h in R['metades'])
    c4 = R['robustez']['custo2x']['anual'] > R['spy']['anual']
    R['criterios'] = {'acimaP95Acaso': c1, 'venceSpyComQuedaAte1_5x': c2, 'vencePesosIguaisNasDuasMetades': c3, 'custo2xVenceSpy': c4}
    R['aprovada'] = c1 and c2 and c3 and c4
    return R


# ---------- Hipótese D ----------
def eventos_d(P, B, spy, top=TOP_LIQ):
    """Eventos de D: um por balanço trimestral de papel elegível (liquidez no fim do mês anterior, preço ≥ 5)."""
    cal = P.cal
    fins = [i for i in range(len(cal) - 1) if cal[i][:7] != cal[i + 1][:7]]
    rank = {}  # liquidez no último fim de mês antes de cada data
    for i in fins:
        liq = sorted(((a, t) for a, t in ((P.adtv(t, i), t) for t in B if t in P.adj) if a == a), reverse=True)
        rank[i] = {t for _, t in liq[:top]}
    ev = []
    for t, b in B.items():
        if t not in P.adj:
            continue
        trim = sorted([x for x in b['trim'] if 'ni' in x], key=lambda x: x['end'])
        por_fim = {x['end']: x for x in trim}
        anuncios = sorted(b.get('anuncios') or [])
        bal = sorted([x for x in b['bal'] if x.get('ativo')], key=lambda x: x['end'])
        for x in trim:
            fim = date.fromisoformat(x['end'])
            ant = [por_fim[e] for e in por_fim if 350 <= (fim - date.fromisoformat(e)).days <= 380]
            if not ant:
                continue
            f = x['filed']
            k = bisect.bisect_right(anuncios, f)
            dia = anuncios[k - 1] if k and (date.fromisoformat(f) - date.fromisoformat(anuncios[k - 1])).days <= 60 else f
            i = bisect.bisect_left(cal, dia)
            if i < 2 or i + 61 >= len(cal):
                continue
            mf = [j for j in fins if j < i]
            if not mf or t not in rank[mf[-1]]:
                continue
            if P.preco_real(t, i) < PRECO_MIN:
                continue
            bb = [y for y in bal if y['filed'] < dia or y['end'] == x['end']]
            if not bb:
                continue
            A = P.adj[t]
            a0, a1, a2 = A[i - 2], A[i + 1], A[i + 61]
            s1, s2 = P.adj[spy][i + 1], P.adj[spy][i + 61]
            if not (a0 > 0 and a1 > 0 and a2 > 0):
                continue
            ev.append({'t': t, 'dia': cal[i], 'i': i, 'tri': cal[i][:4] + 'T' + str((int(cal[i][5:7]) - 1) // 3 + 1),
                       'surpresa': (x['ni'] - ant[0]['ni']) / bb[-1]['ativo'], 'reacao': a1 / a0 - 1,
                       'deriva': a2 / a1 - 1, 'derivaSpy': s2 / s1 - 1})
    return ev


def hipotese_d(P, B, spy):
    ev = eventos_d(P, B, spy)
    if not ev:
        return None
    grupos = {}
    for e in ev:
        grupos.setdefault(e['tri'], []).append(e)
    grupos = {k: v for k, v in grupos.items() if len(v) >= 25}

    def spread(rotulos=None):
        alto, baixo = [], []
        for k, v in grupos.items():
            s = [e['surpresa'] for e in v] if rotulos is None else rotulos[k]
            q20, q80 = np.percentile(s, 20), np.percentile(s, 80)
            alto += [e for e, x in zip(v, s) if x >= q80]
            baixo += [e for e, x in zip(v, s) if x <= q20]
        return alto, baixo

    alto, baixo = spread()
    dif = np.mean([e['deriva'] for e in alto]) - np.mean([e['deriva'] for e in baixo])
    rng = random.Random(11)
    nulo = []
    for _ in range(500):
        rot = {k: rng.sample([e['surpresa'] for e in v], len(v)) for k, v in grupos.items()}
        a, b = spread(rot)
        nulo.append(np.mean([e['deriva'] for e in a]) - np.mean([e['deriva'] for e in b]))
    trs = sorted(grupos)
    meio = trs[len(trs) // 2]
    metades = []
    for cond in (lambda e: e['tri'] < meio, lambda e: e['tri'] >= meio):
        a, b = [e for e in alto if cond(e)], [e for e in baixo if cond(e)]
        metades.append(round(float(np.mean([e['deriva'] for e in a]) - np.mean([e['deriva'] for e in b])) * 100, 2))
    excesso_alto = float(np.mean([e['deriva'] - e['derivaSpy'] for e in alto])) - 0.002
    pct = lambda l: round(float(np.mean(l)) * 100, 2)
    R = {'eventos': sum(len(v) for v in grupos.values()), 'trimestres': len(grupos), 'de': trs[0], 'ate': trs[-1],
         'reacao': {'alto': pct([e['reacao'] for e in alto]), 'baixo': pct([e['reacao'] for e in baixo])},
         'deriva60': {'alto': pct([e['deriva'] for e in alto]), 'baixo': pct([e['deriva'] for e in baixo]),
                      'altoMenosBaixo': round(dif * 100, 2), 'nuloP50': round(float(np.median(nulo)) * 100, 2),
                      'nuloP95': round(float(np.percentile(nulo, 95)) * 100, 2), 'metades': metades},
         'altoMenosSpyDepoisDoCusto': round(excesso_alto * 100, 2),
         'mediaTodosDeriva': pct([e['deriva'] for v in grupos.values() for e in v]),
         'mediaSpyMesmasDatas': pct([e['derivaSpy'] for v in grupos.values() for e in v])}
    c1 = dif > 0 and dif > np.percentile(nulo, 95)
    c2 = all(m > 0 for m in metades)
    c3 = excesso_alto > 0
    R['criterios'] = {'acimaP95Embaralhado': bool(c1), 'positivoNasDuasMetades': bool(c2), 'altoVenceSpyDepoisDoCusto': bool(c3)}
    R['aprovada'] = bool(c1 and c2 and c3)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('balancos')
    ap.add_argument('precos')
    ap.add_argument('--saida', default='fundamentos_teste.json')
    ap.add_argument('--spy', default='SPY')
    a = ap.parse_args(argv)
    B = json.load(open(a.balancos))
    bruto = json.load(open(a.precos))
    cal = bruto[a.spy]['dates']
    P = Precos(bruto, cal)
    B = {t: b for t, b in B.items() if t in P.adj}
    print(f'{len(B)} papéis com balanços e preços; calendário {cal[0]} a {cal[-1]}', flush=True)
    R = {'registro': 'docs/hipotese-fundamentos.md', 'papeis': len(B), 'C': hipotese_c(P, B, a.spy), 'D': hipotese_d(P, B, a.spy)}
    json.dump(R, open(a.saida, 'w'), indent=1, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    L = ['## Hipóteses C e D (fundamentos)', '']
    C = R['C']
    if C:
        lin = lambda nome, m: f"| {nome} | {m['retorno']}% | {m['anual']}% | {m['quedaMax']}% | {m['sharpe']} |" if m else f'| {nome} | — | — | — | — |'
        L += [f"### C · valor + qualidade · EUA · {C['de']} a {C['ate']} ({C['trimestres']} trimestres, ~{C['elegiveisMedio']} elegíveis)", '',
              '| carteira | retorno | anual | queda máx. | Sharpe |', '|---|---|---|---|---|',
              lin(f'valor + qualidade (top {N_CART})', C['principal']), lin('SPY', C['spy']), lin('pesos iguais, todos os elegíveis', C['pesosIguais']),
              f"| acaso ({SORTEIOS} sorteios) | p5 {C['acaso']['p5']}% · mediana {C['acaso']['mediana']}% · p95 {C['acaso']['p95']}% | | | |",
              *[lin('robustez: ' + k, m) for k, m in C['robustez'].items()], '',
              'Metades: ' + ' · '.join(f"{h['de']}–{h['ate']}: carteira {h['carteira']['retorno']}% × pesos iguais {h['pesosIguais']['retorno']}% × SPY {h['spy']['retorno']}%" for h in C['metades']), '',
              'Critérios: ' + ' · '.join(f"{k} **{'sim' if v else 'não'}**" for k, v in C['criterios'].items()) + f" → **{'APROVADA' if C['aprovada'] else 'REPROVADA'}**", '']
    D = R['D']
    if D:
        L += [f"### D · deriva depois do balanço · EUA · {D['de']} a {D['ate']} ({D['eventos']} balanços)", '',
              f"Reação (−2 a +1 pregão): quintil alto {D['reacao']['alto']}% · baixo {D['reacao']['baixo']}%",
              f"Deriva 60 pregões: alto {D['deriva60']['alto']}% · baixo {D['deriva60']['baixo']}% · diferença {D['deriva60']['altoMenosBaixo']}% (embaralhado p50 {D['deriva60']['nuloP50']}%, p95 {D['deriva60']['nuloP95']}%) · metades {D['deriva60']['metades']}",
              f"Quintil alto menos SPY, depois do custo: {D['altoMenosSpyDepoisDoCusto']}% · média de todos {D['mediaTodosDeriva']}% × SPY {D['mediaSpyMesmasDatas']}%",
              'Critérios: ' + ' · '.join(f"{k} **{'sim' if v else 'não'}**" for k, v in D['criterios'].items()) + f" → **{'APROVADA' if D['aprovada'] else 'REPROVADA'}**", '']
    print('\n'.join(L))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write('\n'.join(L) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
