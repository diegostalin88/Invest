"""Hipótese O7: strangle comprado com metade dos juros do CDI, só com IV Rank baixo, com preços reais da B3.

Regras, critério e auditoria: docs/opcoes/hipotese-strangle.md (escritos antes de rodar). Estudo só de leitura.

Uso: python strangle.py --anos 2018-2026 --saida ../opcoes_resultado
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
from travas import CAPITAL, CDI, INICIO_PRIO3, Indicadores

BASE = {'ativos': ['BOVA11'], 'ivr_max': 20, 'gatilho': 'ivr', 'orcamento': 0.5, 'delta': 0.20,
        'dte_min': 25, 'dte_max': 50, 'dte_alvo': 35, 'custo': 0.005, 'atraso': 1}


def escolher_strangle(cad, s, d, p, iv_atm):
    r = math.log(1 + CDI.get(d, ch.CDI_RESERVA))
    hoje = ch._dia(d)
    por = {}
    for c in cad:
        if c[4] <= 0 or c[5] <= 0:
            continue
        if (c[1] == 'call' and c[2] <= s) or (c[1] == 'put' and c[2] >= s):
            continue
        dte = (ch._dia(c[3]) - hoje).days
        if p['dte_min'] <= dte <= p['dte_max']:
            por.setdefault(dte, {'call': [], 'put': []})[c[1]].append(c)
    for dte in sorted(por, key=lambda x: (abs(x - p['dte_alvo']), x)):
        if not por[dte]['call'] or not por[dte]['put']:
            continue
        t = dte / 365

        def dl(c):
            vol = ch.iv(c[1], (c[4] + c[5]) / 2, s, c[2], t, r) or iv_atm
            return abs(travas._delta(c[1], s, c[2], t, r, vol))
        return tuple(min(por[dte][tp], key=lambda c: abs(dl(c) - p['delta'])) for tp in ('call', 'put'))
    return None


def simular(dados, p, inicio, fim):
    pregoes, spot, ohlc, cadeia, ivs = dados
    ativos = p['ativos']
    ind = {a: Indicadores(200) for a in ativos}
    hist_iv = {a: [] for a in ativos}
    caixa, abertos, pend, ops, curva = CAPITAL, {}, {}, [], []
    pico, queda_max, cdi_acum, anterior = CAPITAL, 0.0, 1.0, None
    mes, orc, juros_mes, juros_ant = None, 0.0, 0.0, 0.0
    rng = random.Random(p['sorteio'][1]) if p.get('sorteio') else None
    elegiveis = sinais = 0
    for d in pregoes:
        no = inicio <= d <= fim
        if anterior and inicio <= anterior <= fim and no:
            dia = (1 + CDI.get(anterior, ch.CDI_RESERVA)) ** (1 / 252) - 1
            juros_mes += caixa * dia
            caixa += caixa * dia
            cdi_acum *= 1 + dia
        anterior = d
        if no and d[:6] != mes:
            mes, juros_ant, juros_mes = d[:6], juros_mes, 0.0
            orc = p['orcamento'] * juros_ant
        for a in ativos:
            if (d, a) not in spot:
                continue
            s = spot[(d, a)]
            mx, mn = ohlc[(d, a)][:2]
            ind[a].atualizar(mx, mn, s, *ohlc[(d, a)][2:3])
            if (d, a) in ivs:
                hist_iv[a].append(ivs[(d, a)])
            if not no:
                continue
            cad = cadeia.get((d, a), [])
            precos = {(c[0], c[3]): c for c in cad}
            o = abertos.get(a)
            if o:
                for i, (cod, venc, k, tp) in enumerate(o['pernas']):
                    c = precos.get((cod, venc))
                    if c:
                        o['pernas'][i] = (cod, venc, c[2], tp)      # strike ajustado pela B3 nos proventos
                if o['venc'] <= d:
                    recebe = sum(max(0.0, s - k) if tp == 'call' else max(0.0, k - s) for _, _, k, tp in o['pernas'])
                    recebe = max(0.0, recebe - 2 * p['custo'])
                    caixa += recebe * o['qtd']
                    ops.append({'ativo': a, 'entrada': o['entrada'], 'saida': d, 'venc': o['venc'],
                                'pernas': [x[0] for x in o['pernas']], 'pago': round(o['pago'], 4),
                                'recebe': round(recebe, 4), 'qtd': o['qtd'], 'avista_entrada': o['s0'],
                                'avista_venc': round(s, 2),
                                'pnl': round((recebe - o['pago']) * o['qtd'], 2), 'risco': round(o['pago'] * o['qtd'], 2)})
                    del abertos[a]
            pe = pend.get(a)
            if pe:
                pe['espera'] -= 1
                if pe['espera'] <= 0:
                    del pend[a]
                    cs = [precos.get((c[0], c[3])) for c in pe['pernas']]
                    if all(c and c[5] > 0 for c in cs) and orc > 0:
                        pago = sum(c[5] for c in cs) + 2 * p['custo']
                        qtd = int(orc / (pago * 100)) * 100
                        if qtd > 0:
                            caixa -= pago * qtd
                            orc = 0.0                        # um strangle por mês
                            abertos[a] = {'pernas': [(c[0], c[3], c[2], c[1]) for c in cs], 'venc': cs[0][3],
                                          'pago': pago, 'qtd': qtd, 'entrada': d, 's0': round(s, 2)}
            if a in abertos or a in pend or orc <= 0 or any(pend.values()):
                continue
            if not ind[a].pronto() or len(hist_iv[a]) < ch.JANELA_RANK or (d, a) not in ivs:
                continue
            if a == 'PRIO3' and d < INICIO_PRIO3:
                continue
            elegiveis += 1
            if rng:
                ok = rng.random() < p['sorteio'][0]
            elif p['gatilho'] == 'bollinger':
                ok = ind[a].bollinger_estreito()
            else:
                ok = ch.iv_rank(hist_iv[a]) < p['ivr_max']
            if not ok:
                continue
            st = escolher_strangle(cad, s, d, p, ivs[(d, a)])
            if st:
                pend[a] = {'pernas': st, 'espera': p['atraso']}
                sinais += 1
        if no:
            v = caixa
            for a, o in abertos.items():
                precos = {(c[0], c[3]): c for c in cadeia.get((d, a), [])}
                for cod, venc, k, tp in o['pernas']:
                    c = precos.get((cod, venc))
                    if c and c[4] > 0:
                        v += c[4] * o['qtd']               # marcado pela oferta de compra
            pico = max(pico, v)
            queda_max = max(queda_max, 1 - v / pico)
            curva.append((d, round(v, 2)))
    final = caixa + sum(o['pago'] * o['qtd'] for o in abertos.values())
    return {'operacoes': ops, 'curva': curva, 'final': final, 'queda_max': queda_max, 'cdi': cdi_acum - 1,
            'elegiveis': elegiveis, 'sinais': sinais}


def metricas(res):
    ops = res['operacoes']
    pago = sum(o['pago'] * o['qtd'] for o in ops)
    recebe = sum(o['recebe'] * o['qtd'] for o in ops)
    anos = {}
    for o in ops:
        a = anos.setdefault(o['saida'][:4], [0.0, 0.0, 0])
        a[0] += o['pago'] * o['qtd']
        a[1] += o['recebe'] * o['qtd']
        a[2] += 1
    return {
        'strangles': len(ops), 'retorno': round(res['final'] / CAPITAL - 1, 4), 'cdi': round(res['cdi'], 4),
        'quedaMax': round(res['queda_max'], 4), 'pagoTotal': round(pago, 2), 'recebidoTotal': round(recebe, 2),
        'resultadoOpcoes': round((recebe - pago) / pago, 4) if pago else None,
        'acerto': round(sum(o['recebe'] > o['pago'] for o in ops) / len(ops), 4) if ops else None,
        'melhorMultiplo': round(max((o['recebe'] / o['pago'] for o in ops if o['pago']), default=0), 2),
        'porAno': {k: {'strangles': v[2], 'resultado': round((v[1] - v[0]) / v[0], 4) if v[0] else None}
                   for k, v in sorted(anos.items())},
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--anos', default='2018-2026')
    ap.add_argument('--saida', default='../opcoes_resultado')
    ap.add_argument('--sorteios', type=int, default=100)
    args = ap.parse_args(argv)
    a0, a1 = (int(x) for x in args.anos.split('-'))
    os.makedirs(args.saida, exist_ok=True)
    try:
        CDI.update(ch.baixar_cdi(date(a0, 1, 1), date.today()))
    except Exception as e:  # noqa: BLE001
        print(f'CDI indisponível ({e}); sem o CDI real o resultado não vale, abortando', flush=True)
        return 1
    dados = travas.carregar(range(a0, a1 + 1))
    versoes = {'BOVA11': {**BASE}, '6 papéis': {**BASE, 'ativos': list(ch.UNIVERSO)}}
    saida, crit, aprov = {}, {}, {}
    ini, fim = travas.PERIODOS['fora']
    t = ['## Hipótese O7: strangle comprado com metade dos juros do CDI (B3)', '']
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'  # noqa: E731
    for nome, p in versoes.items():
        variantes = {'original': p, 'Bollinger estreito no lugar do IV Rank': {**p, 'gatilho': 'bollinger'},
                     'orçamento de 100% dos juros': {**p, 'orcamento': 1.0},
                     'auditoria: compra 2 pregões depois': {**p, 'atraso': 2},
                     'auditoria: custo x4': {**p, 'custo': 0.02}}
        saida[nome] = {}
        for vn, vp in variantes.items():
            saida[nome][vn] = {per: metricas(simular(dados, vp, i0, f0)) for per, (i0, f0) in travas.PERIODOS.items()}
        res = simular(dados, p, ini, fim)
        m = saida[nome]['original']['fora']
        saida[nome]['reproduz'] = metricas(simular(dados, p, ini, fim)) == m
        freq = res['sinais'] / res['elegiveis'] if res['elegiveis'] else 0
        plac = sorted((metricas(simular(dados, {**p, 'sorteio': (freq, k)}, ini, fim))['resultadoOpcoes'] or -1)
                      for k in range(args.sorteios))
        perc = sum(x < (m['resultadoOpcoes'] or -1) for x in plac) / len(plac) if plac else None
        saida[nome]['placebo'] = {'n': len(plac), 'mediana': round(statistics.median(plac), 4) if plac else None,
                                  'percentilOriginal': round(perc, 3) if perc is not None else None}
        crit[nome] = {
            'retorno acima do CDI': m['retorno'] > m['cdi'],
            'resultado das opções positivo': (m['resultadoOpcoes'] or -1) > 0,
            '>= 20 strangles': m['strangles'] >= 20,
            'placebo: percentil >= 95': (perc or 0) >= 0.95,
        }
        aprov[nome] = all(crit[nome].values())
        with open(os.path.join(args.saida, f'operacoes_o7_{nome}_fora.json'), 'w') as f:
            json.dump(res['operacoes'], f, indent=1)
        print(f'{nome}: ok', flush=True)
        for per in ('fora', 'dentro'):
            i0, f0 = travas.PERIODOS[per]
            t += [f'### {nome}, {"fora" if per == "fora" else "dentro"} da amostra ({i0[:4]}–{f0[:4]})', '',
                  '| Variante | Strangles | Retorno | CDI | Opções: (recebido − pago) ÷ pago | Acerto | Melhor múltiplo | Queda máx. |',
                  '| --- | --- | --- | --- | --- | --- | --- | --- |']
            for vn in variantes:
                x = saida[nome][vn][per]
                t.append(f"| {vn} | {x['strangles']} | {pct(x['retorno'])} | {pct(x['cdi'])} | {pct(x['resultadoOpcoes'])} | "
                         f"{pct(x['acerto'])} | {x['melhorMultiplo']} | {pct(x['quedaMax'])} |")
            t.append('')
        t += [f"- Por ano (fora): {m['porAno']}",
              f"- Placebo ({saida[nome]['placebo']['n']} sorteios, frequência {pct(freq)}): resultado das opções mediano "
              f"{pct(saida[nome]['placebo']['mediana'])}; o original fica no percentil {pct(saida[nome]['placebo']['percentilOriginal'])}",
              f"- Reproduz o mesmo número ao rodar de novo: {'sim' if saida[nome]['reproduz'] else 'NÃO'}", '',
              'Strangles sorteados para conferência:']
        for o in random.Random(1).sample(res['operacoes'], min(5, len(res['operacoes']))):
            t.append(f"- {o['ativo']} {', '.join(o['pernas'])}: compra {o['entrada']} (à vista {o['avista_entrada']}) por "
                     f"{o['pago']:.2f}, venc. {o['venc']} (à vista {o['avista_venc']}), recebe {o['recebe']:.2f}, {o['qtd']} de cada")
        t += [''] + [f'- {"OK" if v else "FALHOU"}: {k}' for k, v in crit[nome].items()]
        t += ['', f"**Veredito {nome}: {'APROVADA' if aprov[nome] else 'REPROVADA'}**", '']
    saida['criterios'], saida['aprovada'] = crit, aprov
    with open(os.path.join(args.saida, 'strangle.json'), 'w') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    texto = '\n'.join(t) + '\n'
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
