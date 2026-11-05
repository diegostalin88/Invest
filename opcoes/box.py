"""Hipótese O4: box de 4 pontas como renda fixa, com preços reais da B3 (COTAHIST).

Regras, critério e auditoria: docs/opcoes/hipotese-box.md (escritos antes de rodar). Estudo só de leitura.

Uso: python box.py --anos 2018-2026 --saida ../opcoes_resultado
"""
import argparse
import json
import os
import random
import statistics
import sys
from datetime import date

import cotahist as ch
import travas
from travas import CAPITAL, CDI

BASE = {'dte_min': 20, 'dte_max': 70, 'custo': 0.005, 'fracao': 1 / 6,
        'meio': False,          # informativo: preço no meio das ofertas
        'atraso': 0,            # auditoria: compra o mesmo box N pregões depois
        'negociado': False,     # auditoria: só pernas com negócio no dia
        'posicao': 0}           # auditoria: 0 = melhor box, 2 = terceiro melhor


def _preco(c, lado, meio):
    """Preço de uma perna: compra (lado +1) na oferta de venda, vende (−1) na de compra; ou no meio."""
    if meio:
        return (c[4] + c[5]) / 2
    return c[5] if lado > 0 else c[4]


def custo_box(pernas, meio, custo):
    """pernas = (call K1, call K2, put K1, put K2). Preço pago por unidade."""
    c1, c2, p1, p2 = pernas
    return _preco(c1, +1, meio) - _preco(c2, -1, meio) + _preco(p2, +1, meio) - _preco(p1, -1, meio) + 4 * custo


def boxes(cad, d, p):
    """Todos os boxes negociáveis no dia: lista de (venc, K1, K2, pernas)."""
    hoje = ch._dia(d)
    por = {}
    for c in cad:
        if c[4] <= 0 or c[5] <= 0:
            continue
        if p['negociado'] and (len(c) < 8 or c[6] <= 0):
            continue
        dte = (ch._dia(c[3]) - hoje).days
        if p['dte_min'] <= dte <= p['dte_max']:
            por.setdefault((c[3], c[2]), {})[c[1]] = c
    out = []
    vencs = sorted({v for v, _ in por})
    for v in vencs:
        ks = sorted(k for vv, k in por if vv == v and len(por[(vv, k)]) == 2)
        for i, k1 in enumerate(ks):
            for k2 in ks[i + 1:]:
                a, b = por[(v, k1)], por[(v, k2)]
                out.append((v, k1, k2, (a['call'], b['call'], a['put'], b['put'])))
    return out


def du_ate(pregoes_idx, pregoes, d, venc):
    """Pregões de d (exclusive) até o vencimento (inclusive). None se o vencimento passa do fim dos dados."""
    if venc > pregoes[-1]:
        return None
    j = next((i for i in range(pregoes_idx[d], len(pregoes)) if pregoes[i] >= venc), None)
    return None if j is None else j - pregoes_idx[d]


def cdi_periodo(pregoes, i0, i1):
    """CDI acumulado dos pregões i0 (exclusive) a i1 (inclusive): a taxa do dia anterior rende no dia."""
    acc = 1.0
    for i in range(i0 + 1, i1 + 1):
        acc *= (1 + CDI.get(pregoes[i - 1], ch.CDI_RESERVA)) ** (1 / 252)
    return acc - 1


def taxa(box, pago, p, du):
    recebe = box[2] - box[1] - 2 * p['custo']
    if pago <= 0 or du <= 0 or recebe <= 0:
        return None, recebe
    return (recebe / pago) ** (252 / du) - 1, recebe


def simular(dados, p, inicio, fim):
    pregoes, spot, _, cadeia, _ = dados
    idx = {d: i for i, d in enumerate(pregoes)}
    caixa = CAPITAL                    # o dinheiro em caixa rende CDI; o pago no box sai do caixa até o vencimento
    abertos, operacoes, curva = [], [], []
    pico, queda_max, cdi_acum, anterior = CAPITAL, 0.0, 1.0, None
    escolhidos = {}                    # auditoria de atraso: box escolhido aguardando compra
    todos = []                         # informativo: taxa − CDI de todos os boxes possíveis no dia da escolha
    mes_visto, n_no_mes = None, 0
    for d in pregoes:
        no = inicio <= d <= fim
        if anterior and inicio <= anterior <= fim and no:
            dia = (1 + CDI.get(anterior, ch.CDI_RESERVA)) ** (1 / 252) - 1
            caixa += caixa * dia
            cdi_acum *= 1 + dia
        anterior = d
        if not no:
            continue
        for b in [b for b in abertos if b['venc'] <= d]:          # vencimentos
            caixa += b['qtd'] * b['recebe']
            operacoes.append({**b, 'saida': d, 'pnl': round(b['qtd'] * (b['recebe'] - b['pago']), 2),
                              'risco': round(b['qtd'] * b['pago'], 2), 'motivo': 'vencimento'})
            abertos.remove(b)
        if d[:6] != mes_visto:
            mes_visto, n_no_mes = d[:6], 0
        n_no_mes += 1
        for a in ch.UNIVERSO:
            cad = cadeia.get((d, a), [])
            compra = None
            if a in escolhidos:
                escolhidos[a]['espera'] -= 1
                if escolhidos[a]['espera'] <= 0:
                    bx = escolhidos.pop(a)['box']
                    precos = {(c[0], c[3]): c for c in cad}
                    pernas = tuple(precos.get((c[0], c[3])) for c in bx[3])
                    if all(c and c[4] > 0 and c[5] > 0 for c in pernas):
                        compra = (bx[0], bx[1], bx[2], pernas)
            elif n_no_mes == 2 and cad and not any(b['ativo'] == a for b in abertos):
                cands = []
                for bx in boxes(cad, d, p):
                    du = du_ate(idx, pregoes, d, bx[0])
                    if not du:
                        continue
                    tx, _ = taxa(bx, custo_box(bx[3], p['meio'], p['custo']), p, du)
                    if tx is None:
                        continue
                    cdi_a = (1 + cdi_periodo(pregoes, idx[d], idx[d] + du)) ** (252 / du) - 1
                    todos.append(tx - cdi_a)
                    cands.append((tx, bx))
                cands.sort(key=lambda x: -x[0])
                if len(cands) > p['posicao'] and cands[p['posicao']][0] > 0:
                    bx = cands[p['posicao']][1]
                    if p['atraso']:
                        escolhidos[a] = {'box': bx, 'espera': p['atraso']}
                    else:
                        compra = bx
            if not compra:
                continue
            du = du_ate(idx, pregoes, d, compra[0])
            pago = custo_box(compra[3], p['meio'], p['custo'])
            tx, recebe = taxa(compra, pago, p, du or 0)
            if not du or tx is None:
                continue
            patrimonio = caixa + sum(b['qtd'] * b['pago'] for b in abertos)
            qtd = min(int(patrimonio * p['fracao'] / pago // 100), int(caixa / pago // 100)) * 100
            if qtd <= 0:
                continue
            caixa -= qtd * pago
            cdi_a = (1 + cdi_periodo(pregoes, idx[d], idx[d] + du)) ** (252 / du) - 1
            abertos.append({'ativo': a, 'entrada': d, 'venc': compra[0], 'k1': compra[1], 'k2': compra[2],
                            'pago': pago, 'recebe': recebe, 'taxa': round(tx, 4), 'cdi': round(cdi_a, 4),
                            'qtd': qtd, 'pernas': [c[0] for c in compra[3]]})
        valor = caixa + sum(b['qtd'] * b['pago'] for b in abertos)   # box marcado pelo custo (sem risco de preço)
        pico = max(pico, valor)
        queda_max = max(queda_max, 1 - valor / pico)
        curva.append((d, round(valor, 2)))
    final = caixa + sum(b['qtd'] * b['pago'] for b in abertos)
    return {'operacoes': operacoes, 'curva': curva, 'final': final, 'queda_max': queda_max,
            'cdi': cdi_acum - 1, 'abertas': len(abertos), 'todos': todos}


def metricas(res):
    ops = res['operacoes']
    acima = [o for o in ops if o['taxa'] > o['cdi']]
    exc = sorted(o['taxa'] - o['cdi'] for o in ops)
    todos = sorted(res['todos'])
    q = lambda xs, f: round(xs[int(f * (len(xs) - 1))], 4) if xs else None  # noqa: E731
    return {
        'operacoes': len(ops),
        'retorno': round(res['final'] / CAPITAL - 1, 4),
        'cdi': round(res['cdi'], 4),
        'acimaDoCdi': round(len(acima) / len(ops), 4) if ops else None,
        'excessoMediano': q(exc, 0.5),
        'comPrejuizo': sum(o['pnl'] < 0 for o in ops),
        'quedaMax': round(res['queda_max'], 4),
        'todosBoxes': {'n': len(todos), 'p25': q(todos, 0.25), 'mediana': q(todos, 0.5), 'p75': q(todos, 0.75)},
    }


def veredito(m):
    c = {
        'retorno acima do CDI': m['retorno'] > m['cdi'],
        'pelo menos 50% dos boxes acima do CDI do período': (m['acimaDoCdi'] or 0) >= 0.5,
        '>= 50 boxes': m['operacoes'] >= 50,
        'nenhum box com prejuízo nominal': m['comPrejuizo'] == 0,
    }
    return c, all(c.values())


def por_ano(ops):
    out = {}
    for o in ops:
        a = out.setdefault(o['saida'][:4], {'boxes': 0, 'acima': 0, 'exc': []})
        a['boxes'] += 1
        a['acima'] += o['taxa'] > o['cdi']
        a['exc'].append(o['taxa'] - o['cdi'])
    return {k: {'boxes': v['boxes'], 'acimaDoCdi': round(v['acima'] / v['boxes'], 3),
                'excessoMediano': round(statistics.median(v['exc']), 4)} for k, v in sorted(out.items())}


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
    variantes = {
        'base': {},
        'meio das ofertas (otimista)': {'meio': True},
        'auditoria: compra 1 pregão depois': {'atraso': 1},
        'auditoria: custo x4': {'custo': 0.02},
        'auditoria: só pernas negociadas no dia': {'negociado': True},
        'auditoria: terceiro melhor box': {'posicao': 2},
    }
    saida, res_base = {}, None
    for nome, v in variantes.items():
        saida[nome] = {}
        for periodo, (ini, fim) in travas.PERIODOS.items():
            res = simular(dados, {**BASE, **v}, ini, fim)
            saida[nome][periodo] = metricas(res)
            if nome == 'base' and periodo == 'fora':
                res_base = res
                saida['base']['porAno'] = por_ano(res['operacoes'])
                saida['base']['reproduz'] = metricas(simular(dados, BASE, ini, fim)) == saida['base']['fora']
                with open(os.path.join(args.saida, 'operacoes_o4_base_fora.json'), 'w') as f:
                    json.dump(res['operacoes'], f, indent=1)
        print(f'{nome}: ok', flush=True)
    crit, ok = veredito(saida['base']['fora'])
    saida['criterios'], saida['aprovada'] = crit, ok
    with open(os.path.join(args.saida, 'box.json'), 'w') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'  # noqa: E731
    pp = lambda x: '–' if x is None else f'{x * 100:+.2f} p.p.'  # noqa: E731
    t = ['## Hipótese O4: box de 4 pontas como renda fixa (B3)', '']
    for periodo in ('fora', 'dentro'):
        ini, fim = travas.PERIODOS[periodo]
        t += [f'### {"Fora" if periodo == "fora" else "Dentro"} da amostra ({ini[:4]}–{fim[:4]})', '',
              '| Variante | Boxes | Retorno | CDI | Boxes acima do CDI | Taxa − CDI (mediana) | Com prejuízo | '
              'Todos os boxes do dia: p25 / mediana / p75 (n) |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for nome in variantes:
            m = saida[nome][periodo]
            tb = m['todosBoxes']
            t.append(f"| {nome} | {m['operacoes']} | {pct(m['retorno'])} | {pct(m['cdi'])} | {pct(m['acimaDoCdi'])} | "
                     f"{pp(m['excessoMediano'])} | {m['comPrejuizo']} | {pp(tb['p25'])} / {pp(tb['mediana'])} / "
                     f"{pp(tb['p75'])} ({tb['n']}) |")
        t.append('')
    t += ['### Base fora da amostra, por ano', '', '| Ano | Boxes | Acima do CDI | Taxa − CDI (mediana) |',
          '| --- | --- | --- | --- |']
    t += [f"| {a} | {v['boxes']} | {pct(v['acimaDoCdi'])} | {pp(v['excessoMediano'])} |"
          for a, v in saida['base']['porAno'].items()]
    t += ['', f"- Reproduz o mesmo número ao rodar de novo: {'sim' if saida['base']['reproduz'] else 'NÃO'}", '']
    t += ['Boxes sorteados para conferência:']
    for o in random.Random(1).sample(res_base['operacoes'], min(5, len(res_base['operacoes']))):
        t.append(f"- {o['ativo']} venc. {o['venc']}, K1 {o['k1']} / K2 {o['k2']} ({', '.join(o['pernas'])}): entrada "
                 f"{o['entrada']}, pago {o['pago']:.4f}, recebe {o['recebe']:.4f}, taxa {pct(o['taxa'])} contra CDI {pct(o['cdi'])}")
    t += ['']
    t += [f'- {"OK" if v else "FALHOU"}: {k}' for k, v in crit.items()]
    t += ['', f"**Veredito: {'APROVADA' if ok else 'REPROVADA'}**", '']
    texto = '\n'.join(t) + '\n'
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
