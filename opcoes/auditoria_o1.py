"""Auditoria adversarial da hipótese O1 (docs/opcoes/auditoria-o1.md). Tenta derrubar o resultado de travas.py.

Uso: python auditoria_o1.py --sorteios 100 --saida ../opcoes_resultado
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

FORA = travas.PERIODOS['fora']


def por_ano(ops):
    out = {}
    for o in ops:
        a = out.setdefault(o['saida'][:4], {'operacoes': 0, 'pnl': 0.0, 'risco': 0.0})
        a['operacoes'] += 1
        a['pnl'] += o['pnl']
        a['risco'] += o['risco']
    return {k: {**v, 'pnl': round(v['pnl'], 2), 'pnlPorRisco': round(v['pnl'] / v['risco'], 4)}
            for k, v in sorted(out.items())}


def pior_mes(res):
    meses = {}
    for d, v in res['curva']:
        meses.setdefault(d[:6], []).append(v)
    chaves = sorted(meses)
    pior = None
    for i in range(1, len(chaves)):
        r = meses[chaves[i]][-1] / meses[chaves[i - 1]][-1] - 1
        if pior is None or r < pior[1]:
            pior = (chaves[i], round(r, 4))
    return pior


def conferencia(dados, ops, n=5, semente=1):
    """Mostra as cotações brutas de algumas operações sorteadas, para conferir à mão."""
    _, spot, _, cadeia, _ = dados
    linhas = []
    for o in random.Random(semente).sample(ops, min(n, len(ops))):
        linhas.append(f"- {o['ativo']} {o['estrutura']}: entrada {o['entrada']} (à vista {spot.get((o['entrada'], o['ativo']), 0):.2f}), "
                      f"saída {o['saida']} por {o['motivo']}, P&L R$ {o['pnl']}, risco R$ {o['risco']}")
    return linhas


def rodar(dados, p):
    res = travas.simular(dados, p, *FORA)
    return res, travas.metricas(res, travas.retorno_bova(dados[1], *FORA))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--anos', default='2018-2026')
    ap.add_argument('--sorteios', type=int, default=100)
    ap.add_argument('--saida', default='../opcoes_resultado')
    args = ap.parse_args(argv)
    a0, a1 = (int(x) for x in args.anos.split('-'))
    os.makedirs(args.saida, exist_ok=True)
    try:
        travas.CDI.update(ch.baixar_cdi(date(a0, 1, 1), date.today()))
    except Exception as e:  # noqa: BLE001
        print(f'CDI indisponível ({e})', flush=True)
    dados = travas.carregar(range(a0, a1 + 1))
    versoes = {'simples': travas.BASE, 'técnica': {**travas.BASE, **travas.TECNICO}}
    rel = {}
    for nome, p in versoes.items():
        res, m = rodar(dados, p)
        r = {'original': m, 'porAno': por_ano(res['operacoes']), 'piorMes': pior_mes(res),
             'conferencia': conferencia(dados, res['operacoes']),
             'frequencia': round(res['sinais'] / res['elegiveis'], 4) if res['elegiveis'] else 0}
        # 1) reprodução: a mesma simulação de novo tem que dar o mesmo número
        _, m2 = rodar(dados, p)
        r['reproduz'] = m2 == m
        # 2) execução atrasada: 2 e 3 pregões depois do sinal
        r['atraso2'] = rodar(dados, {**p, 'atraso': 2})[1]
        r['atraso3'] = rodar(dados, {**p, 'atraso': 3})[1]
        # 2b) saída decidida pelo preço médio das ofertas (incluída depois do 1º resultado: ver o doc)
        r['saidaMeio'] = rodar(dados, {**p, 'saida_meio': True})[1]
        # 2c) limite otimista: entrada e saída no meio das ofertas (incluído depois do 1º resultado)
        r['execMeio'] = rodar(dados, {**p, 'exec_meio': True, 'saida_meio': True})[1]
        # 2d) quanto a diferença entre as ofertas pesa: ida e volta ÷ crédito, na entrada
        razoes = sorted(o['spread'] / o['credito'] for o in res['operacoes'] if o['credito'] > 0)
        r['spreadSobreCredito'] = {'mediana': round(statistics.median(razoes), 3) if razoes else None,
                                   'p25': round(razoes[len(razoes) // 4], 3) if razoes else None,
                                   'p75': round(razoes[3 * len(razoes) // 4], 3) if razoes else None}
        # 3) custos mais altos
        r['custo4x'] = rodar(dados, {**p, 'custo': p['custo'] * 4})[1]
        # 4) placebo: mesma frequência de entrada, dias sorteados (sem IV Rank e sem gatilho técnico)
        placebo = []
        for semente in range(args.sorteios):
            pm = rodar(dados, {**p, 'sorteio': (r['frequencia'], semente)})[1]
            placebo.append((pm['pnlPorRisco'] or 0, pm['retorno']))
        pr = sorted(x[0] for x in placebo)
        r['placebo'] = {
            'n': len(placebo),
            'pnlPorRiscoMediana': round(statistics.median(pr), 4) if pr else None,
            'retornoMediana': round(statistics.median(x[1] for x in placebo), 4) if placebo else None,
            'percentilOriginal': round(sum(x < (m['pnlPorRisco'] or 0) for x in pr) / len(pr), 3) if pr else None,
        }
        rel[nome] = r
        print(f'{nome}: auditado', flush=True)
    with open(os.path.join(args.saida, 'auditoria_o1.json'), 'w') as f:
        json.dump(rel, f, indent=2, ensure_ascii=False)
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'
    t = ['## Auditoria adversarial da hipótese O1', '']
    for nome, r in rel.items():
        m = r['original']
        t += [f'### Versão {nome}', '',
              f"- Reproduz o mesmo número ao rodar de novo: {'sim' if r['reproduz'] else 'NÃO'}",
              f"- Original: {m['operacoes']} operações, P&L/risco {pct(m['pnlPorRisco'])}, retorno {pct(m['retorno'])} "
              f"(CDI {pct(m['cdi'])}), fator de lucro {m['fatorLucro']}, queda máx. {pct(m['quedaMax'])}",
              f"- Execução 2 pregões depois: P&L/risco {pct(r['atraso2']['pnlPorRisco'])}, retorno {pct(r['atraso2']['retorno'])}",
              f"- Execução 3 pregões depois: P&L/risco {pct(r['atraso3']['pnlPorRisco'])}, retorno {pct(r['atraso3']['retorno'])}",
              f"- Saída decidida pelo preço médio: P&L/risco {pct(r['saidaMeio']['pnlPorRisco'])}, retorno {pct(r['saidaMeio']['retorno'])}, "
              f"acerto {pct(r['saidaMeio']['acerto'])}",
              f"- Limite otimista, tudo no meio das ofertas: P&L/risco {pct(r['execMeio']['pnlPorRisco'])}, "
              f"retorno {pct(r['execMeio']['retorno'])}, acerto {pct(r['execMeio']['acerto'])}, fator de lucro {r['execMeio']['fatorLucro']}",
              f"- Diferença entre ofertas (ida e volta) ÷ crédito na entrada: mediana {r['spreadSobreCredito']['mediana']} "
              f"(p25 {r['spreadSobreCredito']['p25']}, p75 {r['spreadSobreCredito']['p75']})",
              f"- Custo × 4: P&L/risco {pct(r['custo4x']['pnlPorRisco'])}, retorno {pct(r['custo4x']['retorno'])}",
              f"- Placebo ({r['placebo']['n']} sorteios, frequência {pct(r['frequencia'])}): P&L/risco mediano "
              f"{pct(r['placebo']['pnlPorRiscoMediana'])}, retorno mediano {pct(r['placebo']['retornoMediana'])}; "
              f"o original fica no percentil {pct(r['placebo']['percentilOriginal'])}",
              f"- Pior mês: {r['piorMes']}", '', '| Ano | Operações | P&L (R$) | P&L/risco |', '| --- | --- | --- | --- |']
        t += [f"| {a} | {v['operacoes']} | {v['pnl']} | {pct(v['pnlPorRisco'])} |" for a, v in r['porAno'].items()]
        t += ['', 'Operações sorteadas para conferência:'] + r['conferencia'] + ['']
    texto = '\n'.join(t) + '\n'
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
