"""Hipótese O3: as entradas simples da O1 (crédito) e da O2 (débito), com ordem limite no meio das ofertas e sem
saída antes do vencimento. Regras e critério: docs/opcoes/hipotese-vencimento.md (escritos antes de rodar).

Uso: python vencimento.py --anos 2018-2026 --saida ../opcoes_resultado
"""
import argparse
import json
import os
import sys
import time
from datetime import date

import cotahist as ch
import debito
import travas

O3 = {'limite': True, 'ate_vencimento': True}

# nome: (simulador, parâmetros)
VERSOES = {
    'crédito': (travas.simular, {**travas.BASE, **O3, 'nome': 'crédito'}),
    'débito': (debito.simular, {**debito.BASE, **O3, 'nome': 'débito'}),
}
COMPARACOES = {
    'crédito sem filtro de IV Rank': (travas.simular, {**VERSOES['crédito'][1], 'ivr_tendencia': None,
                                                       'ivr_lateral': None}),
    'débito sem filtro de IV Rank': (debito.simular, {**VERSOES['débito'][1], 'ivr_max': None}),
    'crédito pelas ofertas, até o vencimento': (travas.simular, {**VERSOES['crédito'][1], 'limite': False}),
    'débito pelas ofertas, até o vencimento': (debito.simular, {**VERSOES['débito'][1], 'limite': False}),
}


def markdown(saida):
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'
    l = ['## Hipótese O3: ordem limite no meio e até o vencimento (B3)', '']
    for periodo in ('fora', 'dentro'):
        ini, fim = travas.PERIODOS[periodo]
        l += [f'### {"Fora" if periodo == "fora" else "Dentro"} da amostra ({ini[:4]}–{fim[:4]})', '',
              '| Versão | Operações | Acerto | Fator de lucro | Retorno | CDI | BOVA11 | Queda máx. | P&L / risco | '
              'Ordens executadas / parciais / não |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for nome, r in saida['versoes'].items():
            m, o = r[periodo], r[periodo + 'Ordens']
            l.append(f"| {nome} | {m['operacoes']} | {pct(m['acerto'])} | {m['fatorLucro']} | {pct(m['retorno'])} | "
                     f"{pct(m['cdi'])} | {pct(m['bova11'])} | {pct(m['quedaMax'])} | {pct(m['pnlPorRisco'])} | "
                     f"{o['todas']} / {o['parte']} / {o['nenhuma']} |")
        l.append('')
    for nome in VERSOES:
        m = saida['versoes'][nome]['fora']
        l += [f'### Versão {nome}, fora da amostra', '', f"- Por ativo (R$): {m['porAtivo']}",
              f"- Por estrutura: {m['porEstrutura']}", f"- Motivo de saída: {m['motivos']}",
              f"- Retorno sem o melhor ativo ({m['melhorAtivo']}): {pct(m['retornoSemMelhor'])}", '']
        for k, v in saida['criterios'][nome].items():
            l.append(f'- {"OK" if v else "FALHOU"}: {k}')
        l += ['', f"**Veredito da versão {nome}: {'APROVADA' if saida['aprovada'][nome] else 'REPROVADA'}**", '']
    return '\n'.join(l) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--anos', default='2018-2026')
    ap.add_argument('--saida', default='../opcoes_resultado')
    args = ap.parse_args(argv)
    a0, a1 = (int(x) for x in args.anos.split('-'))
    os.makedirs(args.saida, exist_ok=True)
    try:
        travas.CDI.update(ch.baixar_cdi(date(a0, 1, 1), date.today()))
    except Exception as e:  # noqa: BLE001
        print(f'CDI indisponível ({e}); sem o CDI real o resultado não vale, abortando', flush=True)
        return 1
    dados = travas.carregar(range(a0, a1 + 1))
    saida = {'versoes': {}}
    for nome, (sim, p) in {**VERSOES, **COMPARACOES}.items():
        saida['versoes'][nome] = {}
        for periodo, (ini, fim) in travas.PERIODOS.items():
            t0 = time.time()
            res = sim(dados, p, ini, fim)
            saida['versoes'][nome][periodo] = travas.metricas(res, travas.retorno_bova(dados[1], ini, fim))
            saida['versoes'][nome][periodo + 'Ordens'] = res['ordens']
            if nome in VERSOES:
                with open(os.path.join(args.saida, f'operacoes_o3_{nome}_{periodo}.json'), 'w') as f:
                    json.dump(res['operacoes'], f, indent=1)
            print(f"{nome} / {periodo}: {len(res['operacoes'])} operações, {time.time() - t0:.0f}s", flush=True)
    vs = saida['versoes']
    saida['criterios'], saida['aprovada'] = {}, {}
    for nome in VERSOES:
        saida['criterios'][nome], saida['aprovada'][nome] = travas.veredito(
            vs[nome]['fora'], vs[f'{nome} sem filtro de IV Rank']['fora'])
    with open(os.path.join(args.saida, 'vencimento.json'), 'w') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    texto = markdown(saida)
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
