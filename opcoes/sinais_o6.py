"""Lista do dia para o teste para frente da O6 (docs/opcoes/protocolo-o6-para-frente.md). Só leitura: não envia
ordem nenhuma.

Para cada papel, no último pregão disponível no COTAHIST: VRP (IV de 30 dias − volatilidade realizada de 21
pregões) e, se VRP ≥ 4, a trava de alta com put da O6 (vendida delta ~0,15, comprada delta ~0,05, 35 a 56 dias),
com as ofertas de cada perna, o crédito no meio das ofertas e as instruções da montagem em duas etapas (compra da
proteção pela oferta de venda, depois venda limite da put de cima) e da recompra no alvo (25% do crédito).

Uso: python sinais_o6.py [--saida sinais_o6.md]
"""
import argparse
import os
import sys
from datetime import date, timedelta

import cotahist as ch
import travas
import vrp


def sinais(dados, p=None):
    """Linhas da lista do último pregão de `dados` (formato de travas.carregar)."""
    p = p or vrp.O6
    pregoes, spot, _, cadeia, ivs = dados
    d = pregoes[-1]
    out = []
    for a in p.get('ativos', ch.UNIVERSO):
        fech = [spot[(x, a)] for x in pregoes if (x, a) in spot]
        linha = {'data': d, 'ativo': a, 'spot': spot.get((d, a)), 'iv': ivs.get((d, a)), 'rv': None, 'vrp': None,
                 'sinal': False, 'trava': None, 'motivo': ''}
        if linha['spot'] is None or linha['iv'] is None or len(fech) <= 21:
            linha['motivo'] = 'sem dados do dia'
            out.append(linha)
            continue
        linha['rv'] = travas.vol_realizada(fech)
        linha['vrp'] = (linha['iv'] - linha['rv']) * 100
        if linha['vrp'] < p['vrp_min']:
            linha['motivo'] = f"VRP abaixo de {p['vrp_min']:g}"
            out.append(linha)
            continue
        cad = cadeia.get((d, a), [])
        m = travas.montar('trava_alta_put', cad, linha['spot'], d, {**p, 'exec_meio': True}, linha['iv'])
        if not m:
            linha['motivo'] = 'nenhuma trava com crédito ≥ 12% da largura no meio das ofertas'
            out.append(linha)
            continue
        precos = {(c[0], c[3]): c for c in cad}
        pernas = []
        for cod, venc, lado in m['pernas']:
            c = precos[(cod, venc)]
            pernas.append({'codigo': cod, 'lado': 'vende' if lado < 0 else 'compra', 'strike': c[2],
                           'vencimento': venc, 'oferta_compra': c[4], 'oferta_venda': c[5]})
        credito = sum((x['oferta_compra'] + x['oferta_venda']) / 2 * (1 if x['lado'] == 'vende' else -1)
                      for x in pernas)
        vend, comp = pernas
        meio = lambda x: (x['oferta_compra'] + x['oferta_venda']) / 2
        alvo = p['alvo_casado'] * credito
        linha.update(sinal=True, motivo='enviar amanhã', trava={
            'pernas': pernas, 'credito': credito, 'largura': m['largura'],
            'credito_largura': credito / m['largura'], 'alvo_recompra': alvo,
            'risco_por_opcao': m['largura'] - credito,
            # etapa 2: meio da vendida + o que a proteção custou acima do meio dela (pagando a oferta de venda)
            'protecao_max': comp['oferta_venda'], 'meio_comprada': meio(comp),
            'venda_limite': meio(vend) + comp['oferta_venda'] - meio(comp),
            # recompra: custo líquido = 25% do crédito, vendendo a comprada pela oferta de compra do fechamento
            'recompra_limite': alvo + comp['oferta_compra']})
        out.append(linha)
    return out


def markdown(linhas):
    d = linhas[0]['data'] if linhas else '-'
    f = lambda x, n=2: '–' if x is None else f'{x:.{n}f}'.replace('.', ',')
    pc = lambda x: '–' if x is None else f(x * 100, 1) + '%'
    l = [f'## O6 para frente: lista do pregão {d[6:]}/{d[4:6]}/{d[:4]}', '',
         'Enviar no pregão seguinte, em duas etapas, sempre a proteção primeiro. A venda vale só no dia: não '
         'executou, cancela e não persegue o preço.', '',
         '| Papel | Preço | IV | Vol. realizada 21d | VRP | Situação |', '| --- | --- | --- | --- | --- | --- |']
    for x in linhas:
        l.append(f"| {x['ativo']} | {f(x['spot'])} | {pc(x['iv'])} | {pc(x['rv'])} | {f(x['vrp'], 1)} | {x['motivo']} |")
    for x in linhas:
        t = x['trava']
        if not t:
            continue
        l += ['', f"### {x['ativo']}: trava de alta com put", '',
              '| Perna | Código | Strike | Vencimento | Oferta de compra | Oferta de venda |',
              '| --- | --- | --- | --- | --- | --- |']
        for p in t['pernas']:
            v = p['vencimento']
            l.append(f"| {p['lado']} | {p['codigo']} | {f(p['strike'])} | {v[6:]}/{v[4:6]}/{v[:4]} | "
                     f"{f(p['oferta_compra'])} | {f(p['oferta_venda'])} |")
        vend, comp = t['pernas']
        l += ['', f"- **Crédito pedido (meio das ofertas):** R$ {f(t['credito'])} por opção "
                  f"({f(t['credito_largura'] * 100, 0)}% da largura de R$ {f(t['largura'])})",
              f"- **Perda máxima:** R$ {f(t['risco_por_opcao'])} por opção (R$ {f(t['risco_por_opcao'] * 100)} "
              f"por lote de 100)", '',
              '**Montagem, na abertura:**', '',
              f"1. **Comprar** 100 {comp['codigo']} pela oferta de venda da tela (no fechamento era "
              f"R$ {f(comp['oferta_venda'])}). Anote o preço pago.",
              f"2. **Vender** 100 {vend['codigo']} com ordem limite, válida só no dia: "
              f"**R$ {f(t['venda_limite'])}** se a proteção custou R$ {f(t['protecao_max'])}. Se custou outro "
              f"preço, o limite é R$ {f(t['venda_limite'] - t['protecao_max'])} + o preço pago.", '',
              '**Recompra no alvo (com a trava montada, renovar todo dia até o vencimento):**', '',
              f"1. **Comprar** 100 {vend['codigo']} com ordem limite de **R$ {f(t['recompra_limite'])}**, "
              f"isto é, R$ {f(t['alvo_recompra'])} + a oferta de compra de {comp['codigo']} na tela "
              f"(R$ {f(comp['oferta_compra'])} no fechamento).",
              f"2. Só depois de executada, **vender** 100 {comp['codigo']} pela oferta de compra."]
    return '\n'.join(l) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--saida', default='sinais_o6.md')
    a = ap.parse_args(argv)
    hoje = date.today()
    try:
        travas.CDI.update(ch.baixar_cdi(hoje - timedelta(days=500), hoje))
    except Exception as e:  # noqa: BLE001
        print(f'CDI do Banco Central indisponível ({e}): sem ele o delta sai errado, abortando')
        return 1
    dados = travas.carregar([hoje.year - 1, hoje.year])
    texto = markdown(sinais(dados))
    pregoes, spot = dados[0], dados[1]
    for at in ch.UNIVERSO:      # conferência: os 22 fechamentos usados na volatilidade realizada
        f = [(x, spot[(x, at)]) for x in pregoes if (x, at) in spot][-22:]
        print(at, ' '.join(f'{x[6:]}/{x[4:6]}:{v:.2f}' for x, v in f))
    with open(a.saida, 'w', encoding='utf-8') as fh:
        fh.write(texto)
    resumo = os.environ.get('GITHUB_STEP_SUMMARY')
    if resumo:
        with open(resumo, 'a', encoding='utf-8') as fh:
            fh.write(texto)
    print(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
