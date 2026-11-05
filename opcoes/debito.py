"""Hipótese O2: travas de débito direcionais com IV Rank baixo, com preços reais da B3 (COTAHIST).

Regras e critério: docs/opcoes/hipotese-travas-debito.md (escritos antes de rodar). Estudo só de leitura.
Reaproveita a carga de dados, os indicadores e as métricas de travas.py (hipótese O1).

Uso: python debito.py --anos 2018-2026 --saida ../opcoes_resultado
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import date

import cotahist as ch
import travas
from travas import CAPITAL, CDI, INICIO_PRIO3, Indicadores

BASE = {
    'nome': 'base', 'gatilho': 'simples',
    'ivr_max': 35,                      # IV Rank máximo (None = sem filtro)
    'adx_min': 20, 'mme': 200,
    'rompimento_vol': 1.5,              # técnica: volume do dia ≥ 1,5 × média de 20
    'dte_min': 25, 'dte_max': 50, 'dte_alvo': 35,
    'largura': 0.05,
    'alvo': 0.75,                       # sai quando a trava vale ≥ 75% da largura
    'stop': 0.50,                       # sai quando a trava vale ≤ 50% do débito
    'dias_saida': 7,                    # sai faltando ≤ 7 dias corridos (~5 pregões)
    'risco': 0.01, 'custo': 0.005,
}
TECNICO = {'nome': 'técnica', 'gatilho': 'tecnico'}
VARIANTES = [
    {'nome': 'sem filtro de IV Rank', 'ivr_max': None},
    {**TECNICO, 'nome': 'técnica sem filtro de IV Rank', 'ivr_max': None},
    {'nome': 'IV Rank até 25', 'ivr_max': 25},
    {'nome': 'IV Rank até 45', 'ivr_max': 45},
    {'nome': 'largura 3%', 'largura': 0.03},
    {'nome': 'largura 8%', 'largura': 0.08},
    {'nome': 'alvo 50% da largura', 'alvo': 0.50},
    {'nome': 'custo x2', 'custo': 0.010},
]


def escolher(i, s, p):
    """'alta' (trava de alta com call), 'baixa' (trava de baixa com put) ou None, só com dados até hoje."""
    if p['gatilho'] == 'simples':
        if i.adx is None or i.adx < p['adx_min']:
            return None
        return 'alta' if s > i.mme else 'baixa'
    # técnica (estudo do Diego, 05/11): rompimento com volume
    if i.max20 is None or not i.vol20:
        return None
    forte = i.volume >= p['rompimento_vol'] * i.vol20
    if forte and s > i.max20:
        return 'alta'
    if forte and s < i.min20:
        return 'baixa'
    return None


def montar(direcao, cad, s, d, p):
    """Compra a opção mais perto do dinheiro e vende a mais distante com largura perto de p['largura'] × preço."""
    tipo = 'call' if direcao == 'alta' else 'put'
    hoje = ch._dia(d)
    por_venc = {}
    for c in cad:
        if c[1] != tipo or c[4] <= 0 or c[5] <= 0:
            continue
        dte = (ch._dia(c[3]) - hoje).days
        if p['dte_min'] <= dte <= p['dte_max']:
            por_venc.setdefault((dte, c[3]), []).append(c)
    for (dte, venc) in sorted(por_venc, key=lambda x: (abs(x[0] - p['dte_alvo']), x[0])):
        lista = por_venc[(dte, venc)]
        compra = min(lista, key=lambda c: abs(c[2] - s))
        alvo = compra[2] + p['largura'] * s if tipo == 'call' else compra[2] - p['largura'] * s
        mais_longe = [c for c in lista if (c[2] > compra[2] if tipo == 'call' else c[2] < compra[2])]
        if not mais_longe:
            continue
        venda = min(mais_longe, key=lambda c: abs(c[2] - alvo))
        largura = abs(venda[2] - compra[2])
        spread = (compra[5] - compra[4]) + (venda[5] - venda[4])
        if p.get('exec_meio'):
            debito = (compra[4] + compra[5]) / 2 - (venda[4] + venda[5]) / 2 + 2 * p['custo']
        else:
            debito = compra[5] - venda[4] + 2 * p['custo']
        if not 0 < debito < largura:
            continue
        return {'pernas': [(compra[0], compra[3], +1), (venda[0], venda[3], -1)], 'debito': debito,
                'largura': largura, 'vencimento': venc, 'spread': spread, 'tipo': tipo,
                'strikes': {compra[0]: compra[2], venda[0]: venda[2]}}
    return None


def valor(pos, cad, custo, meio=False):
    """Quanto se recebe, por opção, desmontando agora (vende a comprada na oferta de compra e recompra a vendida na
    oferta de venda). None se faltar oferta."""
    precos = {(c[0], c[3]): c for c in cad}
    total = 0.0
    for cod, venc, lado in pos['pernas']:
        c = precos.get((cod, venc))
        if not c or c[4] <= 0 or c[5] <= 0:
            return None
        if meio:
            total += (c[4] + c[5]) / 2 * lado
        else:
            total += c[4] if lado > 0 else -c[5]
    return total - custo * len(pos['pernas'])


def intrinseco(pos, s):
    total = 0.0
    for cod, _, lado in pos['pernas']:
        k = pos['strikes'][cod]
        total += lado * (max(0.0, s - k) if pos['tipo'] == 'call' else max(0.0, k - s))
    return total


def simular(dados, p, inicio, fim):
    pregoes, spot, ohlc, cadeia, ivs = dados
    ativos = ch.UNIVERSO
    ind = {a: Indicadores(p['mme']) for a in ativos}
    hist_iv = {a: [] for a in ativos}
    caixa, travado = CAPITAL, 0.0
    posicoes, pendentes, operacoes, curva = {}, {}, [], []
    pico, queda_max, cdi_acum, anterior = CAPITAL, 0.0, 1.0, None
    atraso = p.get('atraso', 1)
    sorteio = p.get('sorteio')
    rng = random.Random(sorteio[1]) if sorteio else None
    meio = bool(p.get('exec_meio'))
    elegiveis = sinais = 0
    for d in pregoes:
        no_periodo = inicio <= d <= fim
        if anterior and inicio <= anterior <= fim and no_periodo:
            dia = (1 + CDI.get(anterior, ch.CDI_RESERVA)) ** (1 / 252) - 1
            caixa += (caixa - travado) * dia
            cdi_acum *= 1 + dia
        for a in ativos:
            if (d, a) not in spot:
                continue
            s = spot[(d, a)]
            mx, mn = ohlc[(d, a)][:2]
            ind[a].atualizar(mx, mn, s, *ohlc[(d, a)][2:3])
            if (d, a) in ivs:
                hist_iv[a].append(ivs[(d, a)])
            if not no_periodo:
                continue
            cad = cadeia.get((d, a), [])
            # 1) execução pendente
            if a in pendentes:
                pendentes[a][1] -= 1
            if a in pendentes and pendentes[a][1] <= 0 and a not in posicoes:
                direcao = pendentes.pop(a)[0]
                m = montar(direcao, cad, s, d, p)
                if m:
                    qtd = int(caixa * p['risco'] / m['debito'] // 100) * 100
                    if qtd > 0 and travado + qtd * m['debito'] <= caixa:
                        posicoes[a] = {**m, 'qtd': qtd, 'entrada': d, 'direcao': direcao}
                        caixa -= qtd * m['debito']          # o débito sai do caixa na entrada
            if a in pendentes and pendentes[a][1] <= 0:
                pendentes.pop(a)
            # 2) saída (a partir do pregão seguinte à entrada)
            if a in posicoes and posicoes[a]['entrada'] != d:
                pos = posicoes[a]
                dte = (ch._dia(pos['vencimento']) - ch._dia(d)).days
                v = valor(pos, cad, p['custo'], meio=meio)
                gat = valor(pos, cad, p['custo'], meio=True) if p.get('saida_meio') else v
                motivo = None
                if dte <= 0:
                    v, motivo = intrinseco(pos, s), 'vencimento'
                elif v is not None and gat is not None:
                    if gat >= p['alvo'] * pos['largura']:
                        motivo = 'alvo'
                    elif gat <= p['stop'] * pos['debito']:
                        motivo = 'stop'
                    elif dte <= p['dias_saida']:
                        motivo = 'prazo'
                if motivo:
                    v = max(0.0, min(v, pos['largura']))
                    caixa += v * pos['qtd']
                    pnl = (v - pos['debito']) * pos['qtd']
                    operacoes.append({'ativo': a, 'estrutura': f"trava_{pos['direcao']}_{pos['tipo']}",
                                      'entrada': pos['entrada'], 'saida': d, 'motivo': motivo,
                                      'pnl': round(pnl, 2), 'risco': round(pos['debito'] * pos['qtd'], 2),
                                      'credito': round(pos['debito'], 4), 'spread': round(pos['spread'], 4)})
                    del posicoes[a]
            # 3) sinal para amanhã
            if a not in posicoes and a not in pendentes and ind[a].pronto() and len(hist_iv[a]) >= ch.JANELA_RANK \
                    and (d, a) in ivs and not (a == 'PRIO3' and d < INICIO_PRIO3):
                elegiveis += 1
                rank = ch.iv_rank(hist_iv[a])
                if sorteio:
                    direcao = ('alta' if s > ind[a].mme else 'baixa') if rng.random() < sorteio[0] else None
                    ok = direcao is not None
                else:
                    direcao = escolher(ind[a], s, p)
                    ok = direcao is not None and (p['ivr_max'] is None or rank <= p['ivr_max'])
                if ok:
                    pendentes[a] = [direcao, atraso]
                    sinais += 1
        if no_periodo:
            aberto = 0.0
            for a, pos in posicoes.items():
                v = valor(pos, cadeia.get((d, a), []), p['custo'], meio=meio)
                aberto += (v if v is not None else pos['debito']) * pos['qtd']
            total = caixa + aberto
            pico = max(pico, total)
            queda_max = max(queda_max, 1 - total / pico)
            curva.append((d, round(total, 2)))
        anterior = d
    # posições ainda abertas no fim voltam ao caixa pelo débito pago (sem lucro nem perda)
    final = caixa + sum(pos['debito'] * pos['qtd'] for pos in posicoes.values())
    return {'operacoes': operacoes, 'curva': curva, 'final': final, 'queda_max': queda_max,
            'cdi': cdi_acum - 1, 'abertas': len(posicoes), 'elegiveis': elegiveis, 'sinais': sinais}


def markdown(saida):
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'
    l = ['## Hipótese O2: travas de débito direcionais com IV Rank baixo (B3)', '']
    for periodo in ('fora', 'dentro'):
        ini, fim = travas.PERIODOS[periodo]
        l += [f'### {"Fora" if periodo == "fora" else "Dentro"} da amostra ({ini[:4]}–{fim[:4]})', '',
              '| Versão | Operações | Acerto | Fator de lucro | Retorno | CDI | BOVA11 | Queda máx. | P&L / risco |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for nome, r in saida['versoes'].items():
            m = r[periodo]
            l.append(f"| {nome} | {m['operacoes']} | {pct(m['acerto'])} | {m['fatorLucro']} | {pct(m['retorno'])} | "
                     f"{pct(m['cdi'])} | {pct(m['bova11'])} | {pct(m['quedaMax'])} | {pct(m['pnlPorRisco'])} |")
        l.append('')
    for nome, chave in (('simples', 'base'), ('técnica', 'técnica')):
        m = saida['versoes'][chave]['fora']
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
        CDI.update(ch.baixar_cdi(date(a0, 1, 1), date.today()))
    except Exception as e:  # noqa: BLE001
        print(f'CDI indisponível ({e}); sem o CDI real o resultado não vale, abortando', flush=True)
        return 1
    dados = travas.carregar(range(a0, a1 + 1))
    saida = {'versoes': {}}
    for v in [{}, TECNICO] + VARIANTES:
        p = {**BASE, **v}
        saida['versoes'][p['nome']] = {}
        for periodo, (ini, fim) in travas.PERIODOS.items():
            t0 = time.time()
            res = simular(dados, p, ini, fim)
            saida['versoes'][p['nome']][periodo] = travas.metricas(res, travas.retorno_bova(dados[1], ini, fim))
            if p['nome'] in ('base', 'técnica'):
                with open(os.path.join(args.saida, f"operacoes_o2_{p['nome']}_{periodo}.json"), 'w') as f:
                    json.dump(res['operacoes'], f, indent=1)
            print(f"{p['nome']} / {periodo}: {len(res['operacoes'])} operações, {time.time() - t0:.0f}s", flush=True)
    vs = saida['versoes']
    saida['criterios'], saida['aprovada'] = {}, {}
    for nome, chave, sem in (('simples', 'base', 'sem filtro de IV Rank'),
                             ('técnica', 'técnica', 'técnica sem filtro de IV Rank')):
        saida['criterios'][nome], saida['aprovada'][nome] = travas.veredito(vs[chave]['fora'], vs[sem]['fora'])
    with open(os.path.join(args.saida, 'debito.json'), 'w') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    texto = markdown(saida)
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
