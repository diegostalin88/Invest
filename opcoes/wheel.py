"""Hipótese O5: venda de put fora do dinheiro com o caixa no CDI ("wheel"), com preços reais da B3 (COTAHIST).

Regras, critério e auditoria: docs/opcoes/hipotese-wheel.md (escritos antes de rodar). Estudo só de leitura.

Uso: python wheel.py --anos 2018-2026 --saida ../opcoes_resultado
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
from datetime import date

import cotahist as ch
import travas
from travas import CAPITAL, CDI

BASE = {
    'ativos': ['PETR4', 'VALE3', 'ITUB4', 'BBAS3'],
    'dte_min': 25, 'dte_max': 50, 'dte_alvo': 35,
    'put_dist': (0.08, 0.12),     # strike da put entre 8% e 12% abaixo do preço
    'put_delta': 0.14,            # dentro dessa faixa, delta mais perto de 0,14
    'call_dist': 0.05,            # call coberta: strike ≥ máx(preço de custo, 1,05 × preço)
    'custo': 0.005,
    'atraso': 1,                  # pregões entre a escolha e a venda
    'meio': False,                # variante: ordem limite no meio, executa se a máxima do dia alcançar
}


# ---------- proventos, deduzidos do ajuste de strike que a B3 faz nas opções ----------

def proventos(pregoes, cadeia, ativos):
    """{(data, ativo): ('div', valor) ou ('split', razão)}. Na data ex, a B3 reduz o strike de todas as opções em
    aberto pelo valor do provento (ou multiplica, em desdobramento). Compara o strike do mesmo código entre dois
    pregões seguidos."""
    out = {}
    for a in ativos:
        ant = None
        for d in pregoes:
            cad = cadeia.get((d, a))
            if not cad:
                continue
            hoje = {(c[0], c[3]): c[2] for c in cad}
            if ant:
                pares = [(ant[k], hoje[k]) for k in hoje if k in ant and abs(ant[k] - hoje[k]) > 1e-6]
                if len(pares) >= 3:
                    difs = sorted(k0 - k1 for k0, k1 in pares)
                    razoes = sorted(k1 / k0 for k0, k1 in pares)
                    md, mr = statistics.median(difs), statistics.median(razoes)
                    if all(abs(x - md) <= 0.011 for x in difs) and md > 0:
                        out[(d, a)] = ('div', md)
                    elif all(abs(x - mr) <= 0.01 for x in razoes) and abs(mr - 1) > 0.05:
                        out[(d, a)] = ('split', mr)
            ant = hoje
    return out


# ---------- escolha das opções ----------

def _delta_put(s, k, t, r, vol):
    d1 = (math.log(s / k) + (r + vol * vol / 2) * t) / (vol * math.sqrt(t))
    return abs(ch._ncdf(d1) - 1)


def escolher_put(cad, s, d, p, iv_atm):
    r = math.log(1 + CDI.get(d, ch.CDI_RESERVA))
    hoje = ch._dia(d)
    lo, hi = s * (1 - p['put_dist'][1]), s * (1 - p['put_dist'][0])
    por_venc = {}
    for c in cad:
        if c[1] != 'put' or c[4] <= 0 or c[5] <= 0 or not lo <= c[2] <= hi:
            continue
        dte = (ch._dia(c[3]) - hoje).days
        if p['dte_min'] <= dte <= p['dte_max']:
            por_venc.setdefault(dte, []).append(c)
    if not por_venc:
        return None
    dte = min(por_venc, key=lambda x: (abs(x - p['dte_alvo']), x))
    t = dte / 365

    def dl(c):
        vol = ch.iv('put', (c[4] + c[5]) / 2, s, c[2], t, r) or iv_atm
        return _delta_put(s, c[2], t, r, vol)
    return min(por_venc[dte], key=lambda c: abs(dl(c) - p['put_delta']))


def escolher_call(cad, s, d, p, preco_custo):
    hoje = ch._dia(d)
    piso = max(preco_custo, s * (1 + p['call_dist']))
    cands = []
    for c in cad:
        if c[1] != 'call' or c[4] <= 0 or c[5] <= 0 or c[2] < piso:
            continue
        dte = (ch._dia(c[3]) - hoje).days
        if p['dte_min'] <= dte <= p['dte_max']:
            cands.append((abs(dte - p['dte_alvo']), dte, c[2], c))
    return min(cands)[3] if cands else None


# ---------- simulação ----------

def simular(dados, p, inicio, fim, prov=None):
    pregoes, spot, _, cadeia, ivs = dados
    ativos = p['ativos']
    prov = prov if prov is not None else proventos(pregoes, cadeia, ativos)
    n = len(ativos)
    caixa = {a: CAPITAL / n for a in ativos}
    acoes = {a: 0 for a in ativos}
    preco_custo = {a: 0.0 for a in ativos}
    aberta, pend = {a: None for a in ativos}, {a: None for a in ativos}
    ultimo_s = {}
    ops, curva, eventos = [], [], {'dividendos': 0, 'desdobramentos': 0, 'exercicios_put': 0, 'exercicios_call': 0}
    pico, queda_max, cdi_acum, anterior = CAPITAL, 0.0, 1.0, None
    rng = random.Random(p['sorteio'][1]) if p.get('sorteio') else None
    for d in pregoes:
        no = inicio <= d <= fim
        if anterior and inicio <= anterior <= fim and no:
            dia = (1 + CDI.get(anterior, ch.CDI_RESERVA)) ** (1 / 252) - 1
            for a in ativos:
                caixa[a] += caixa[a] * dia        # a garantia (Tesouro Selic) continua rendendo CDI
            cdi_acum *= 1 + dia
        anterior = d
        if not no:
            continue
        for a in ativos:
            if (d, a) not in spot:
                continue
            s = spot[(d, a)]
            ultimo_s[a] = s
            cad = cadeia.get((d, a), [])
            precos = {(c[0], c[3]): c for c in cad}
            ev = prov.get((d, a))
            if ev and acoes[a]:
                if ev[0] == 'div':
                    caixa[a] += acoes[a] * ev[1]
                    eventos['dividendos'] += 1
                else:
                    acoes[a] = int(round(acoes[a] / ev[1]))
                    preco_custo[a] *= ev[1]
                    eventos['desdobramentos'] += 1
            o = aberta[a]
            if o:
                c = precos.get((o['cod'], o['venc']))
                if c:
                    if ev and ev[0] == 'split' and abs(c[2] - o['k']) > 1e-6:
                        o['qtd'] = int(round(o['qtd'] / ev[1]))
                    o['k'] = c[2]                  # strike ajustado pela B3
                if o['venc'] <= d:                 # vencimento
                    exerc = s < o['k'] if o['tipo'] == 'put' else s > o['k']
                    intr = max(0.0, o['k'] - s) if o['tipo'] == 'put' else max(0.0, s - o['k'])
                    if exerc and o['tipo'] == 'put':
                        caixa[a] -= o['qtd'] * (o['k'] + p['custo'])
                        preco_custo[a] = (preco_custo[a] * acoes[a] + o['k'] * o['qtd']) / (acoes[a] + o['qtd'])
                        acoes[a] += o['qtd']
                        eventos['exercicios_put'] += 1
                    elif exerc:
                        caixa[a] += o['qtd'] * (o['k'] - p['custo'])
                        acoes[a] -= o['qtd']
                        eventos['exercicios_call'] += 1
                        if acoes[a] == 0:
                            preco_custo[a] = 0.0
                    ops.append({'ativo': a, 'tipo': o['tipo'], 'entrada': o['entrada'], 'saida': d, 'venc': o['venc'],
                                'cod': o['cod'], 'strike': round(o['k'], 2), 'premio': round(o['premio'], 4),
                                'qtd': o['qtd'], 'exercida': exerc, 'avista_entrada': round(o['s0'], 2),
                                'avista_venc': round(s, 2),
                                'pnl': round((o['premio'] - intr) * o['qtd'], 2),
                                'risco': round(o['k'] * o['qtd'], 2)})
                    aberta[a] = None
            # venda pendente
            pe = pend[a]
            if pe:
                pe['espera'] -= 1
                if pe['espera'] <= 0:
                    pend[a] = None
                    c = precos.get((pe['cod'], pe['venc']))
                    preco = None
                    if c and p['meio']:
                        preco = pe['limite'] if len(c) > 6 and c[6] >= pe['limite'] - 1e-9 else None
                    elif c and c[4] > 0:
                        preco = c[4]                # vende na melhor oferta de compra
                    if preco:
                        qtd = (int(caixa[a] / (c[2] * 100)) * 100 if pe['tipo'] == 'put'
                               else acoes[a] // 100 * 100)
                        if qtd > 0:
                            premio = preco - p['custo']
                            caixa[a] += premio * qtd
                            aberta[a] = {'tipo': pe['tipo'], 'cod': c[0], 'venc': c[3], 'k': c[2], 'qtd': qtd,
                                         'premio': premio, 'entrada': d, 's0': s}
            # escolha para o próximo pregão
            if not aberta[a] and not pend[a]:
                if rng and rng.random() >= p['sorteio'][0]:
                    continue
                if acoes[a] >= 100:
                    c = escolher_call(cad, s, d, p, preco_custo[a])
                    tipo = 'call'
                else:
                    c = escolher_put(cad, s, d, p, ivs.get((d, a), 0.3))
                    tipo = 'put'
                if c:
                    pend[a] = {'tipo': tipo, 'cod': c[0], 'venc': c[3], 'espera': p['atraso'],
                               'limite': (c[4] + c[5]) / 2}
        total = 0.0
        for a in ativos:
            v = caixa[a] + acoes[a] * ultimo_s.get(a, 0.0)
            o = aberta[a]
            if o:
                c = cadeia.get((d, a), [])
                c = next((x for x in c if x[0] == o['cod'] and x[3] == o['venc']), None)
                if c and c[4] > 0 and c[5] > 0:
                    v -= (c[4] + c[5]) / 2 * o['qtd']
                else:
                    s = ultimo_s.get(a, 0.0)
                    v -= (max(0.0, o['k'] - s) if o['tipo'] == 'put' else max(0.0, s - o['k'])) * o['qtd']
            total += v
        pico = max(pico, total)
        queda_max = max(queda_max, 1 - total / pico)
        curva.append((d, round(total, 2)))
    final = curva[-1][1] if curva else CAPITAL
    return {'operacoes': ops, 'curva': curva, 'final': final, 'queda_max': queda_max, 'cdi': cdi_acum - 1,
            'eventos': eventos}


def comprar_e_manter(dados, ativos, inicio, fim, prov):
    """Referência: os mesmos papéis comprados no início, pesos iguais, com os proventos deduzidos somados ao caixa."""
    pregoes, spot = dados[0], dados[1]
    dias = [d for d in pregoes if inicio <= d <= fim]
    total = 0.0
    for a in ativos:
        d0 = next((d for d in dias if (d, a) in spot), None)
        if not d0:
            continue
        qtd, caixa, ult = CAPITAL / len(ativos) / spot[(d0, a)], 0.0, spot[(d0, a)]
        for d in dias:
            ev = prov.get((d, a))
            if ev and d > d0:
                if ev[0] == 'div':
                    caixa += qtd * ev[1]
                else:
                    qtd /= ev[1]
            ult = spot.get((d, a), ult)
        total += qtd * ult + caixa
    return total / CAPITAL - 1


def metricas(res):
    ops = res['operacoes']
    puts = [o for o in ops if o['tipo'] == 'put']
    premios = [o['premio'] / o['strike'] for o in puts if o['strike']]
    anos = {}
    for d, v in res['curva']:
        anos.setdefault(d[:4], []).append(v)
    por_ano, ant = {}, CAPITAL
    for a in sorted(anos):
        por_ano[a] = round(anos[a][-1] / ant - 1, 4)
        ant = anos[a][-1]
    return {
        'retorno': round(res['final'] / CAPITAL - 1, 4), 'cdi': round(res['cdi'], 4),
        'quedaMax': round(res['queda_max'], 4), 'puts': len(puts), 'calls': len(ops) - len(puts),
        'putsExercidas': sum(o['exercida'] for o in puts),
        'premioPutMediano': round(statistics.median(premios), 4) if premios else None,
        'eventos': res['eventos'], 'porAno': por_ano,
    }


def cdi_por_ano(dados, inicio, fim):
    out, acc, ano, anterior = {}, 1.0, None, None
    for d in dados[0]:
        if not inicio <= d <= fim:
            continue
        if anterior:
            acc *= (1 + CDI.get(anterior, ch.CDI_RESERVA)) ** (1 / 252)
        if ano and d[:4] != ano:
            out[ano], acc = round(acc - 1, 4), 1.0
        ano, anterior = d[:4], d
    if ano:
        out[ano] = round(acc - 1, 4)
    return out


def veredito(m, cdi_ano):
    anos_ok = sum(m['porAno'].get(a, -1) > c for a, c in cdi_ano.items())
    c = {
        'retorno acima do CDI': m['retorno'] > m['cdi'],
        'queda máxima <= 20%': m['quedaMax'] <= 0.20,
        '>= 30 puts vendidas': m['puts'] >= 30,
        'pelo menos 3 dos 4 anos acima do CDI': anos_ok >= 3,
    }
    return c, all(c.values())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--anos', default='2018-2026')
    ap.add_argument('--saida', default='../opcoes_resultado')
    args = ap.parse_args(argv)
    a0, a1 = (int(x) for x in args.anos.split('-'))
    os.makedirs(args.saida, exist_ok=True)
    try:
        CDI.update(ch.baixar_cdi(date(a0, 1, 1), date.today()))
    except Exception as e:  # noqa: BLE001
        print(f'CDI indisponível ({e}); sem o CDI real o resultado não vale, abortando', flush=True)
        return 1
    dados = travas.carregar(range(a0, a1 + 1))
    prov = proventos(dados[0], dados[3], BASE['ativos'])
    variantes = {
        'base': {},
        'ordem limite no meio (informativo)': {'meio': True},
        'auditoria: venda 2 pregões depois': {'atraso': 2},
        'auditoria: custo x4': {'custo': 0.02},
        'informativo: put 5% a 8% abaixo': {'put_dist': (0.05, 0.08)},
        'informativo: put 12% a 16% abaixo': {'put_dist': (0.12, 0.16)},
    }
    saida, res_base = {'proventosDetectados': {}}, None
    for (d, a), ev in sorted(prov.items()):
        saida['proventosDetectados'].setdefault(a, []).append([d, ev[0], round(ev[1], 4)])
    for nome, v in variantes.items():
        saida[nome] = {}
        for periodo, (ini, fim) in travas.PERIODOS.items():
            res = simular(dados, {**BASE, **v}, ini, fim, prov)
            m = metricas(res)
            if nome == 'base' and periodo == 'fora':
                res_base = res
                saida['base']['reproduz'] = metricas(simular(dados, BASE, ini, fim, prov)) == m
            m['comprarEManter'] = round(comprar_e_manter(dados, BASE['ativos'], ini, fim, prov), 4)
            saida[nome][periodo] = m
            if nome == 'base' and periodo == 'fora':
                with open(os.path.join(args.saida, 'operacoes_o5_base_fora.json'), 'w') as f:
                    json.dump(res['operacoes'], f, indent=1)
        print(f'{nome}: ok', flush=True)
    ini, fim = travas.PERIODOS['fora']
    cdi_ano = cdi_por_ano(dados, ini, fim)
    # placebo: mesmas regras de montagem, mas a cada pregão livre só vende com probabilidade sorteada (10%)
    plac = sorted(simular(dados, {**BASE, 'sorteio': (0.1, k)}, ini, fim, prov)['final'] for k in range(20))
    saida['placebo20'] = {'retornoMediano': round(statistics.median(plac) / CAPITAL - 1, 4)}
    crit, ok = veredito(saida['base']['fora'], cdi_ano)
    saida['cdiPorAno'], saida['criterios'], saida['aprovada'] = cdi_ano, crit, ok
    with open(os.path.join(args.saida, 'wheel.json'), 'w') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'  # noqa: E731
    t = ['## Hipótese O5: venda de put com o caixa no CDI ("wheel") na B3', '']
    for periodo in ('fora', 'dentro'):
        i0, f0 = travas.PERIODOS[periodo]
        t += [f'### {"Fora" if periodo == "fora" else "Dentro"} da amostra ({i0[:4]}–{f0[:4]})', '',
              '| Variante | Retorno | CDI | Comprar e manter | Queda máx. | Puts | Exercidas | Calls | Prêmio da put ÷ strike (mediana) |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for nome in variantes:
            m = saida[nome][periodo]
            t.append(f"| {nome} | {pct(m['retorno'])} | {pct(m['cdi'])} | {pct(m['comprarEManter'])} | "
                     f"{pct(m['quedaMax'])} | {m['puts']} | {m['putsExercidas']} | {m['calls']} | "
                     f"{pct(m['premioPutMediano'])} |")
        t.append('')
    m = saida['base']['fora']
    t += ['### Base fora da amostra, por ano', '', '| Ano | Wheel | CDI |', '| --- | --- | --- |']
    t += [f"| {a} | {pct(m['porAno'].get(a))} | {pct(c)} |" for a, c in cdi_ano.items()]
    t += ['', f"- Eventos: {m['eventos']}",
          f"- Proventos detectados pelo ajuste de strike (fora + dentro): "
          f"{ {a: len(v) for a, v in saida['proventosDetectados'].items()} }",
          f"- Placebo (20 sorteios, vende em 10% dos pregões livres): retorno mediano {pct(saida['placebo20']['retornoMediano'])}",
          f"- Reproduz o mesmo número ao rodar de novo: {'sim' if saida['base']['reproduz'] else 'NÃO'}", '',
          'Operações sorteadas para conferência:']
    for o in random.Random(1).sample(res_base['operacoes'], min(6, len(res_base['operacoes']))):
        t.append(f"- {o['ativo']} {o['tipo']} {o['cod']} strike {o['strike']}: vendida {o['entrada']} (à vista "
                 f"{o['avista_entrada']}) por {o['premio']:.2f}, venc. {o['venc']} (à vista {o['avista_venc']}), "
                 f"{'exercida' if o['exercida'] else 'virou pó'}, {o['qtd']} opções")
    t += [''] + [f'- {"OK" if v else "FALHOU"}: {k}' for k, v in crit.items()]
    t += ['', f"**Veredito: {'APROVADA' if ok else 'REPROVADA'}**", '']
    texto = '\n'.join(t) + '\n'
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
