"""Teste da hipótese Q-BR: carteira de ações de qualidade no Brasil (ROE alto e passivo/ativo baixo).

Segue o registro em docs/hipotese-qualidade-brasil.md (escrito antes de rodar). Só leitura; não muda o app.
Reaproveita a coleta da C-BR (CVM, Yahoo, CDI). Não usa quantidade de ações nem valor de mercado.
Uso: python coleta/testar_qualidade_br.py [--saida qualidade_br.json]
"""
import argparse
import json
import os
import random
import sys
import warnings
from datetime import date

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testar_fundamentos as tf         # noqa: E402
import testar_fundamentos_br as fb      # noqa: E402

N_CART, PRECO_MIN, LIQ_MIN, MIN_ELEG = 15, 1.0, 5e6, 30
MESES_REB = (3, 6, 9, 12)
SORTEIOS = int(os.environ.get('SORTEIOS_C', 200))
CUSTO = tf.CUSTO
INDICE = 'BOVA11'
INICIO = '2012-01-01'
# bancos, holding de banco e seguradoras: o passivo é o dinheiro dos clientes (robustez "sem financeiras")
FINANCEIRAS = {'BBAS3', 'BBDC3', 'BBDC4', 'ITUB4', 'ITSA4', 'BBSE3', 'CXSE3', 'PSSA3', 'IRBR3'}


def empresas_q(acc, mapa):
    """{ticker: {'trim': [{end, filed, ni}], 'bal': [{end, filed, ativo, pl, passivo}]}}"""
    out = {}
    for t, cnpj in mapa.items():
        tri, bal = acc.empresa(cnpj)
        receb = {}
        for (c, ref, tipo), d in acc.receb.items():
            if c == cnpj:
                receb[ref] = min(receb.get(ref, d), d)
        out[t] = {'trim': [{'end': x[0], 'filed': x[1], 'ni': x[3]} for x in tri if x[3] is not None],
                  'bal': [{'end': x[0], 'filed': receb[x[0]], 'ativo': x[1], 'pl': x[2], 'passivo': x[3]}
                          for x in bal if x[0] in receb]}
    return out


def fundamentos_q(b, dia):
    """Lucro dos 12 meses (4 trimestres consecutivos, o último até 200 dias antes) e o último balanço publicado."""
    trim = sorted(tf.disponivel(b['trim'], dia), key=lambda x: x['end'])
    if len(trim) < 4:
        return None
    u = trim[-4:]
    for x, y in zip(u, u[1:]):
        if not (80 <= (date.fromisoformat(y['end']) - date.fromisoformat(x['end'])).days <= 100):
            return None
    if (date.fromisoformat(dia) - date.fromisoformat(u[-1]['end'])).days > 200:
        return None
    bal = [x for x in sorted(tf.disponivel(b['bal'], dia), key=lambda x: x['end'])
           if x.get('pl') is not None and x.get('ativo') and x.get('passivo') is not None]
    if not bal:
        return None
    return {'ni': sum(x['ni'] for x in u), 'pl': bal[-1]['pl'], 'ativo': bal[-1]['ativo'], 'passivo': bal[-1]['passivo']}


def percentis(out, chaves):
    for k, maior_melhor in chaves:
        ordem = sorted(range(len(out)), key=lambda j: out[j][k] if maior_melhor else -out[j][k])
        for r, j in enumerate(ordem):
            out[j]['p_' + k] = r / max(1, len(out) - 1)


def elegiveis(P, B, empresa, i):
    dia = P.cal[i]
    melhor = {}
    for t in B:
        if t not in P.adj or P.adj[t][i] != P.adj[t][i] or P.preco_real(t, i) < PRECO_MIN:
            continue
        a = P.adtv(t, i)
        if a == a and a >= LIQ_MIN and (empresa[t] not in melhor or a > melhor[empresa[t]][0]):
            melhor[empresa[t]] = (a, t)
    out = []
    for _, t in melhor.values():
        f = fundamentos_q(B[t], dia)
        if not f or f['pl'] <= 0 or f['ativo'] <= 0:
            continue
        out.append({'t': t, 'roe': f['ni'] / f['pl'], 'alav': max(0.0, f['passivo']) / f['ativo']})
    if not out:
        return out
    percentis(out, (('roe', True), ('alav', False)))
    for x in out:
        x['nota'] = (x['p_roe'] + x['p_alav']) / 2
    return out


def topo(n, k='nota', filtro=None):
    def escolher(p):
        e = [x for x in p['e'] if not filtro or filtro(x)]
        if filtro:   # sem financeiras: percentis refeitos só entre as que sobram
            e = [dict(x) for x in e]
            percentis(e, (('roe', True), ('alav', False)))
            for x in e:
                x['nota'] = (x['p_roe'] + x['p_alav']) / 2
        return [x['t'] for x in sorted(e, key=lambda x: -x[k])[:n]]
    return escolher


def hipotese(P, B, empresa, cdi):
    reb = [i for i in tf.datas_reb(P.cal, MESES_REB) if P.cal[i] >= INICIO]
    periodos = []
    for i, i2 in zip(reb, reb[1:]):
        e = elegiveis(P, B, empresa, i)
        if len(e) >= MIN_ELEG:
            periodos.append({'i': i, 'i2': i2, 'e': e})
    if not periodos:
        return None
    principal = tf.rodar(P, periodos, topo(N_CART))
    todos = tf.rodar(P, periodos, lambda p: [x['t'] for x in p['e']])
    ind = [P.adj[INDICE][p['i2']] / P.adj[INDICE][p['i']] - 1 for p in periodos]
    cdi_r = [fb.cdi_periodo(cdi, P.cal, p['i'], p['i2']) for p in periodos]
    rng = random.Random(7)
    sorteios = [tf.rodar(P, periodos, lambda p: rng.sample([x['t'] for x in p['e']], N_CART)) for _ in range(SORTEIOS)]
    ret = lambda r: tf.metricas(r)['retorno']
    acaso = [ret(s) for s in sorteios]
    meio = len(periodos) // 2
    metades = []
    for a, b in ((0, meio), (meio, len(periodos))):
        ac = [ret(s[a:b]) for s in sorteios]
        metades.append({'de': P.cal[periodos[a]['i']], 'ate': P.cal[periodos[b - 1]['i2']],
                        'carteira': tf.metricas(principal[a:b]), 'pesosIguais': tf.metricas(todos[a:b]),
                        'indice': tf.metricas(ind[a:b]), 'cdi': tf.metricas(cdi_r[a:b]),
                        'acasoP90': round(float(np.percentile(ac, 90)), 1), 'acasoMediana': round(float(np.median(ac)), 1),
                        'percentilAcaso': round(float(np.mean([x < ret(principal[a:b]) for x in ac])) * 100)})
    R = {
        'de': P.cal[periodos[0]['i']], 'ate': P.cal[periodos[-1]['i2']], 'trimestres': len(periodos),
        'elegiveisMedio': round(float(np.mean([len(p['e']) for p in periodos]))),
        'principal': tf.metricas(principal), 'indice': tf.metricas(ind), 'cdi': tf.metricas(cdi_r),
        'pesosIguais': tf.metricas(todos),
        'acaso': {'p5': round(float(np.percentile(acaso, 5)), 1), 'mediana': round(float(np.median(acaso)), 1),
                  'p95': round(float(np.percentile(acaso, 95)), 1)},
        'percentilAcaso': round(float(np.mean([x < ret(principal) for x in acaso])) * 100),
        'metades': metades,
        'robustez': {
            'só rentabilidade (ROE)': tf.metricas(tf.rodar(P, periodos, topo(N_CART, 'roe'))),
            'só segurança (passivo/ativo)': tf.metricas(tf.rodar(P, periodos, topo(N_CART, 'p_alav'))),
            '10 papéis': tf.metricas(tf.rodar(P, periodos, topo(10))),
            '20 papéis': tf.metricas(tf.rodar(P, periodos, topo(20))),
            'custo × 2': tf.metricas(tf.rodar(P, periodos, topo(N_CART), CUSTO * 2)),
            'sem bancos e seguradoras': tf.metricas(tf.rodar(P, periodos, topo(N_CART, filtro=lambda x: x['t'] not in FINANCEIRAS))),
        },
        'porAno': {},
        'exemplosCarteira': [{'data': P.cal[p['i']], 'carteira': [(x['t'], round(x['roe'] * 100, 1), round(x['alav'] * 100))
                                                                 for x in sorted(p['e'], key=lambda x: -x['nota'])[:N_CART]]}
                             for p in (periodos[0], periodos[len(periodos) // 2], periodos[-1])],
        'carteiraAtual': [(x['t'], round(x['roe'] * 100, 1), round(x['alav'] * 100))
                          for x in sorted(elegiveis(P, B, empresa, len(P.cal) - 1), key=lambda x: -x['nota'])[:N_CART]],
    }
    for p, a, b, c in zip(periodos, principal, ind, cdi_r):
        x = R['porAno'].setdefault(P.cal[p['i2']][:4], [1.0, 1.0, 1.0])
        x[0] *= 1 + a
        x[1] *= 1 + b
        x[2] *= 1 + c
    R['porAno'] = {k: [round((v - 1) * 100, 1) for v in x] for k, x in R['porAno'].items()}
    R['criterios'] = {
        '1. acima do p95 do acaso': R['principal']['retorno'] > R['acaso']['p95'],
        '2. vence o BOVA11 com queda até 1,5×': R['principal']['anual'] > R['indice']['anual'] and
        R['principal']['quedaMax'] <= 1.5 * R['indice']['quedaMax'],
        '3. vence os pesos iguais nas duas metades': all(h['carteira']['retorno'] > h['pesosIguais']['retorno'] for h in metades),
        '4. com custo × 2 vence o BOVA11': R['robustez']['custo × 2']['anual'] > R['indice']['anual'],
        '5. acima do CDI': R['principal']['retorno'] > R['cdi']['retorno'],
        '6. acima do p90 do acaso em cada metade': all(h['carteira']['retorno'] > h['acasoP90'] for h in metades),
    }
    R['aprovada'] = all(R['criterios'].values())
    return R


def markdown(R):
    lin = lambda nome, m: (f"| {nome} | {m['retorno']}% | {m['anual']}% | {m['quedaMax']}% | {m['sharpe']} |"
                           if m else f'| {nome} | – | – | – | – |')
    L = [f"## Hipótese Q-BR: qualidade (ROE e passivo/ativo), Brasil, {R['de']} a {R['ate']} "
         f"({R['trimestres']} trimestres, ~{R['elegiveisMedio']} elegíveis)", '',
         '| Carteira | Retorno | Ao ano | Queda máx. | Sharpe |', '| --- | --- | --- | --- | --- |',
         lin(f'qualidade ({N_CART} papéis)', R['principal']), lin('BOVA11', R['indice']), lin('CDI', R['cdi']),
         lin('pesos iguais, todos os elegíveis', R['pesosIguais']),
         f"| acaso ({SORTEIOS} carteiras) | p5 {R['acaso']['p5']}% · mediana {R['acaso']['mediana']}% · "
         f"p95 {R['acaso']['p95']}% | | | |",
         *[lin('robustez: ' + k, m) for k, m in R['robustez'].items()], '',
         f"Percentil da carteira entre as sorteadas: {R['percentilAcaso']}", '']
    for h in R['metades']:
        L.append(f"- Metade {h['de']} a {h['ate']}: carteira {h['carteira']['retorno']}%, pesos iguais "
                 f"{h['pesosIguais']['retorno']}%, BOVA11 {h['indice']['retorno']}%, CDI {h['cdi']['retorno']}%, "
                 f"acaso mediana {h['acasoMediana']}% e p90 {h['acasoP90']}% (percentil {h['percentilAcaso']})")
    L += ['', '| Ano | Carteira | BOVA11 | CDI |', '| --- | --- | --- | --- |',
          *[f'| {a} | {v[0]}% | {v[1]}% | {v[2]}% |' for a, v in sorted(R['porAno'].items())], '',
          'Carteiras de exemplo (papel, ROE %, passivo/ativo %):',
          *[f"- {x['data']}: {x['carteira']}" for x in R['exemplosCarteira']], f"- hoje: {R['carteiraAtual']}", '']
    L += [f'- {"OK" if v else "FALHOU"}: {k}' for k, v in R['criterios'].items()]
    L += ['', f"**Veredito: {'APROVADA' if R['aprovada'] else 'REPROVADA'}**", '']
    return '\n'.join(L)


def main(argv=None):
    warnings.filterwarnings('ignore')
    ap = argparse.ArgumentParser()
    ap.add_argument('--saida', default='qualidade_br.json')
    a = ap.parse_args(argv)
    tick = fb.universo()
    hoje = date.today()
    fca = fb.cvm.baixar(f'{fb.cvm.BASE}/FCA/DADOS/fca_cia_aberta_{hoje.year}.zip') or \
        fb.cvm.baixar(f'{fb.cvm.BASE}/FCA/DADOS/fca_cia_aberta_{hoje.year - 1}.zip')
    if not fca:
        print('FCA da CVM indisponível')
        return 1
    mapa = fb.cvm.mapa_tickers(fca, set(tick))
    acc = fb.cvm.Acumulador(set(mapa.values()))
    for ano in range(fb.ANO_INI, hoje.year + 1):
        for tipo in ('ITR', 'DFP'):
            c = fb.cvm.baixar(f'{fb.cvm.BASE}/{tipo}/DADOS/{tipo.lower()}_cia_aberta_{ano}.zip')
            if c:
                acc.ler_zip(c, tipo, ano)
                print(f'  {tipo} {ano}: ok', flush=True)
    B = empresas_q(acc, mapa)
    print(f'{len(B)} de {len(tick)} códigos com CNPJ na CVM; sem: {sorted(set(tick) - set(B))}', flush=True)
    bruto = fb.precos_yahoo(sorted(B) + [INDICE])
    if INDICE not in bruto:
        print('BOVA11 sem preço no Yahoo: abortando')
        return 1
    cal = bruto[INDICE]['dates']
    P = tf.Precos(bruto, cal)
    B = {t: b for t, b in B.items() if t in P.adj}
    print(f'{len(B)} papéis com balanços e preços; calendário {cal[0]} a {cal[-1]}', flush=True)
    for t in ('PETR4', 'VALE3', 'ITUB4', 'WEGE3'):     # conferência à mão
        if t in B:
            f = fundamentos_q(B[t], cal[-1])
            if f:
                print(f"  {t}: lucro 12m R$ {f['ni'] / 1e9:.1f} bi, PL R$ {f['pl'] / 1e9:.1f} bi, ROE "
                      f"{f['ni'] / f['pl'] * 100:.1f}%, passivo/ativo {f['passivo'] / f['ativo'] * 100:.0f}%", flush=True)
    for i in tf.datas_reb(P.cal, (6,)):
        if P.cal[i] >= INICIO:
            print(f'  elegíveis em {P.cal[i]}: {len(elegiveis(P, B, mapa, i))}', flush=True)
    cdi = fb.cdi_diario(date.fromisoformat(cal[0]), date.fromisoformat(cal[-1]))
    R = hipotese(P, B, mapa, cdi)
    if not R:
        print('nenhuma data com elegíveis suficientes')
        return 1
    R['registro'] = 'docs/hipotese-qualidade-brasil.md'
    md = markdown(R)
    print(md)
    json.dump(R, open(a.saida, 'w'), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    resumo = os.environ.get('GITHUB_STEP_SUMMARY')
    if resumo:
        open(resumo, 'a', encoding='utf-8').write(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
