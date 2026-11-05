"""Hipótese O1: travas de crédito e iron condor filtrados por IV Rank, com preços reais da B3 (COTAHIST).

Regras e critério: docs/opcoes/hipotese-travas-credito.md (escritos antes de rodar). Estudo só de leitura.

Uso: python opcoes/travas.py --anos 2018-2026 --saida opcoes_resultado
"""
import argparse
import json
import math
import os
import random
import sys
import time
from datetime import date

import cotahist as ch

# ---------- parâmetros fixados no registro ----------
BASE = {
    'nome': 'base',
    'ivr_tendencia': 50, 'ivr_lateral': 60,   # IV Rank mínimo (None = sem filtro)
    'adx_lateral': 20, 'mme': 200,
    'dte_min': 25, 'dte_max': 50, 'dte_alvo': 35,
    'delta': 0.25, 'largura': 0.05,
    'alvo': 0.50, 'stop': 2.0, 'dte_saida': 21,
    'risco': 0.01, 'custo': 0.005,
    'gatilho': 'simples',
}
TECNICO = {'nome': 'técnica', 'gatilho': 'tecnico'}
VARIANTES = [
    {'nome': 'sem filtro de IV Rank', 'ivr_tendencia': None, 'ivr_lateral': None},
    {'nome': 'IV Rank 40', 'ivr_tendencia': 40, 'ivr_lateral': 50},
    {'nome': 'IV Rank 60', 'ivr_tendencia': 60, 'ivr_lateral': 70},
    {'nome': 'delta 0,20', 'delta': 0.20},
    {'nome': 'delta 0,30', 'delta': 0.30},
    {'nome': 'largura 3%', 'largura': 0.03},
    {'nome': 'largura 8%', 'largura': 0.08},
    {'nome': 'custo x2', 'custo': 0.010},
    {'nome': 'saída aos 14 dias', 'dte_saida': 14},
]
PERIODOS = {'dentro': ('20190101', '20221231'), 'fora': ('20230101', '20261231')}
CAPITAL = 100_000.0
INICIO_PRIO3 = '20220101'


# ---------- indicadores (só dados até o dia) ----------

class Indicadores:
    """MME e ADX de Wilder, atualizados um pregão por vez."""

    def __init__(self, n_mme=200, n_adx=14):
        self.n_mme, self.n_adx = n_mme, n_adx
        self.k = 2 / (n_mme + 1)
        self.mme = None
        self.contagem = 0
        self.ant = None          # (máx, mín, fech) do pregão anterior
        self.tr = self.pdm = self.ndm = None
        self.adx = None
        self._dx = []
        # extras para o gatilho técnico
        self.mme20 = None
        self.atr10 = None
        self.ganho = self.perda = None     # IFR(14) de Wilder
        self.ifr = None
        self.fechs = []                    # últimos 20 fechamentos (Bollinger)
        self.larguras = []                 # largura de Bollinger dos últimos 252 pregões
        self.minima = None

    def atualizar(self, maxima, minima, fech):
        self.contagem += 1
        self.mme = fech if self.mme is None else self.mme + self.k * (fech - self.mme)
        self.mme20 = fech if self.mme20 is None else self.mme20 + 2 / 21 * (fech - self.mme20)
        self.minima = minima
        self.fechs = (self.fechs + [fech])[-20:]
        if len(self.fechs) == 20:
            m = sum(self.fechs) / 20
            dp = (sum((x - m) ** 2 for x in self.fechs) / 20) ** 0.5
            self.larguras = (self.larguras + [4 * dp / m])[-252:]
        if self.ant:
            mud = fech - self.ant[2]
            g, q = max(mud, 0.0), max(-mud, 0.0)
            if self.ganho is None:
                self.ganho, self.perda = g, q
            else:
                self.ganho = (self.ganho * 13 + g) / 14
                self.perda = (self.perda * 13 + q) / 14
            self.ifr = 100.0 if self.perda == 0 else 100 - 100 / (1 + self.ganho / self.perda)
            tr10 = max(maxima - minima, abs(maxima - self.ant[2]), abs(minima - self.ant[2]))
            self.atr10 = tr10 if self.atr10 is None else (self.atr10 * 9 + tr10) / 10
        if self.ant:
            pm, pn, pc = self.ant
            tr = max(maxima - minima, abs(maxima - pc), abs(minima - pc))
            up, dn = maxima - pm, pn - minima
            pdm = up if up > dn and up > 0 else 0.0
            ndm = dn if dn > up and dn > 0 else 0.0
            n = self.n_adx
            if self.tr is None:
                self.tr, self.pdm, self.ndm = tr, pdm, ndm
            else:
                self.tr = self.tr - self.tr / n + tr
                self.pdm = self.pdm - self.pdm / n + pdm
                self.ndm = self.ndm - self.ndm / n + ndm
            if self.tr > 0:
                pdi, ndi = 100 * self.pdm / self.tr, 100 * self.ndm / self.tr
                dx = 100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi > 0 else 0.0
                if self.adx is None:
                    self._dx.append(dx)
                    if len(self._dx) == n:
                        self.adx = sum(self._dx) / n
                else:
                    self.adx = (self.adx * (n - 1) + dx) / n
        self.ant = (maxima, minima, fech)

    def pronto(self):
        return self.contagem >= self.n_mme and self.adx is not None

    def toca_keltner_inferior(self):
        return self.atr10 is not None and self.minima <= self.mme20 - 2 * self.atr10

    def bollinger_estreito(self):
        """Largura de Bollinger (20, 2) abaixo da mediana dos últimos 252 pregões."""
        if len(self.larguras) < 252:
            return False
        return self.larguras[-1] < sorted(self.larguras)[126]


# ---------- dados ----------

def carregar(anos, linhas_do_ano=ch.linhas_do_ano):
    """Devolve (pregoes, spot, ohlc, cadeia, ivs).
    cadeia[(data, ativo)] = lista de (codigo, tipo, strike, vencimento, oferta_compra, oferta_venda)."""
    spot, ohlc, cadeia, ivs = {}, {}, {}, {}
    for ano in anos:
        t0 = time.time()
        o = {}
        s, opcoes, _ = ch.filtrar(linhas_do_ano(ano), ohlc=o)
        spot.update(s)
        ohlc.update(o)
        for x in ch.iv_diaria(s, opcoes, CDI):
            ivs[(x['data'].replace('-', ''), x['ativo'])] = x['iv']
        for r in opcoes:
            sp = s.get((r['data'], r['ativo']))
            if not sp or r['preexe'] <= 0:
                continue
            dte = (ch._dia(r['datven']) - ch._dia(r['data'])).days
            if dte < 0 or dte > 70 or abs(r['preexe'] / sp - 1) > 0.4:
                continue
            f = max(r['fatcot'], 1)
            cadeia.setdefault((r['data'], r['ativo']), []).append(
                (r['codneg'], r['tipo'], r['preexe'], r['datven'], r['preofc'] / f, r['preofv'] / f))
        print(f'{ano}: carregado em {time.time() - t0:.0f}s', flush=True)
    pregoes = sorted({d for d, _ in spot})
    return pregoes, spot, ohlc, cadeia, ivs


CDI = {}   # {AAAAMMDD: taxa anual}, preenchido no main


# ---------- montagem ----------

def _delta(tipo, s, k, t, r, vol):
    d1 = (math.log(s / k) + (r + vol * vol / 2) * t) / (vol * math.sqrt(t))
    return ch._ncdf(d1) if tipo == 'call' else ch._ncdf(d1) - 1


def montar_trava(tipo, cadeia_dia, s, d, p, iv_atm):
    """Trava de crédito: vende a opção de |delta| mais perto de p['delta'] e compra a mais distante com largura perto
    de p['largura'] × preço. Devolve dict com pernas, crédito por opção e largura, ou None."""
    r = math.log(1 + CDI.get(d, ch.CDI_RESERVA))
    hoje = ch._dia(d)
    por_venc = {}
    for c in cadeia_dia:
        if c[1] != tipo or c[4] <= 0 or c[5] <= 0:
            continue
        dte = (ch._dia(c[3]) - hoje).days
        if p['dte_min'] <= dte <= p['dte_max']:
            por_venc.setdefault((dte, c[3]), []).append(c)
    for (dte, venc) in sorted(por_venc, key=lambda x: (abs(x[0] - p['dte_alvo']), x[0])):
        lista = por_venc[(dte, venc)]
        t = dte / 365.0
        otm = [c for c in lista if (c[2] < s if tipo == 'put' else c[2] > s)]
        if not otm:
            continue

        def dlt(c):
            vol = ch.iv(tipo, (c[4] + c[5]) / 2, s, c[2], t, r) or iv_atm
            return abs(_delta(tipo, s, c[2], t, r, vol))
        venda = min(otm, key=lambda c: abs(dlt(c) - p['delta']))
        alvo = venda[2] - p['largura'] * s if tipo == 'put' else venda[2] + p['largura'] * s
        mais_longe = [c for c in lista if (c[2] < venda[2] if tipo == 'put' else c[2] > venda[2])]
        if not mais_longe:
            continue
        compra = min(mais_longe, key=lambda c: abs(c[2] - alvo))
        spread = (venda[5] - venda[4]) + (compra[5] - compra[4])        # ida e volta pelas ofertas, por opção
        if p.get('exec_meio'):   # auditoria: limite otimista, executa no meio das ofertas
            credito = (venda[4] + venda[5]) / 2 - (compra[4] + compra[5]) / 2 - 2 * p['custo']
        else:
            credito = venda[4] - compra[5] - 2 * p['custo']
        largura = abs(venda[2] - compra[2])
        if credito <= 0 or credito >= largura:
            continue
        return {'pernas': [(venda[0], venda[3], -1), (compra[0], compra[3], +1)], 'credito': credito,
                'largura': largura, 'vencimento': venc, 'spread': spread}
    return None


def montar(estrutura, cadeia_dia, s, d, p, iv_atm):
    if estrutura == 'condor':
        a = montar_trava('put', cadeia_dia, s, d, {**p, 'delta': 0.16}, iv_atm)
        b = montar_trava('call', cadeia_dia, s, d, {**p, 'delta': 0.16}, iv_atm)
        if not a or not b or a['vencimento'] != b['vencimento']:
            return None
        return {'pernas': a['pernas'] + b['pernas'], 'credito': a['credito'] + b['credito'],
                'spread': a['spread'] + b['spread'],
                'largura': max(a['largura'], b['largura']), 'vencimento': a['vencimento']}
    return montar_trava('put' if estrutura == 'trava_alta_put' else 'call', cadeia_dia, s, d, p, iv_atm)


def custo_recompra(pos, cadeia_dia, custo, meio=False):
    """Quanto custa, por opção, desmontar a posição agora (compra as vendidas na oferta de venda e vende as compradas
    na de compra). None se faltar oferta em alguma perna."""
    precos = {(c[0], c[3]): c for c in cadeia_dia}
    total = 0.0
    for cod, venc, lado in pos['pernas']:
        c = precos.get((cod, venc))
        if not c or c[4] <= 0 or c[5] <= 0:
            return None
        if meio:
            total += (c[4] + c[5]) / 2 * (1 if lado < 0 else -1)
        else:
            total += c[5] if lado < 0 else -c[4]
    return total + custo * len(pos['pernas'])


def intrinseco(pos, cadeia_ref, s):
    """Valor de recompra no vencimento: só o valor intrínseco das pernas."""
    total = 0.0
    for cod, venc, lado in pos['pernas']:
        k, tipo = pos['strikes'][cod]
        v = max(0.0, s - k) if tipo == 'call' else max(0.0, k - s)
        total += v if lado < 0 else -v
    return total


# ---------- simulação ----------

def escolher(i, s, p):
    """Estrutura e IV Rank mínimo pelo gatilho da versão, só com dados até hoje. (None, None) = não entra."""
    if p['gatilho'] == 'simples':
        if i.adx < p['adx_lateral']:
            return 'condor', p['ivr_lateral']
        if s > i.mme:
            return 'trava_alta_put', p['ivr_tendencia']
        return 'trava_baixa_call', p['ivr_tendencia']
    # técnica (estudo do Diego, 05/11): canal estreito, defesa na banda inferior de Keltner, exaustão por IFR
    if i.adx < p['adx_lateral'] and i.bollinger_estreito():
        return 'condor', p['ivr_lateral']
    if s > i.mme and i.toca_keltner_inferior():
        return 'trava_alta_put', p['ivr_tendencia']
    if i.ifr is not None and i.ifr > 70:
        return 'trava_baixa_call', p['ivr_tendencia']
    return None, None


def simular(dados, p, inicio, fim):
    pregoes, spot, ohlc, cadeia, ivs = dados
    ativos = ch.UNIVERSO
    ind = {a: Indicadores(p['mme']) for a in ativos}
    hist_iv = {a: [] for a in ativos}
    caixa, travado = CAPITAL, 0.0
    posicoes, pendentes, operacoes, curva = {}, {}, [], []
    pico, queda_max = CAPITAL, 0.0
    cdi_acum = 1.0
    anterior = None
    atraso = p.get('atraso', 1)                 # auditoria: pregões entre o sinal e a execução
    sorteio = p.get('sorteio')                  # auditoria: (probabilidade, semente) no lugar do IV Rank e do gatilho
    rng = random.Random(sorteio[1]) if sorteio else None
    elegiveis = sinais = 0
    for d in pregoes:
        ativo_no_periodo = inicio <= d <= fim
        # juros do CDI sobre o caixa livre, do pregão anterior até hoje (a taxa do dia anterior rende hoje)
        if anterior and inicio <= anterior <= fim and ativo_no_periodo:
            dia = (1 + CDI.get(anterior, ch.CDI_RESERVA)) ** (1 / 252) - 1
            caixa += (caixa - travado) * dia
            cdi_acum *= 1 + dia
        for a in ativos:
            if (d, a) not in spot:
                continue
            s = spot[(d, a)]
            mx, mn = ohlc[(d, a)]
            ind[a].atualizar(mx, mn, s)
            if (d, a) in ivs:
                hist_iv[a].append(ivs[(d, a)])
            if not ativo_no_periodo:
                continue
            cad = cadeia.get((d, a), [])
            # 1) execução pendente do sinal (de ontem, ou de `atraso` pregões atrás)
            if a in pendentes:
                pendentes[a][1] -= 1
            if a in pendentes and pendentes[a][1] <= 0 and a not in posicoes:
                estrutura = pendentes.pop(a)[0]
                m = montar(estrutura, cad, s, d, p, ivs.get((d, a), 0.3))
                if m:
                    risco_un = m['largura'] - m['credito']
                    qtd = int(caixa * p['risco'] / risco_un // 100) * 100
                    if qtd > 0 and travado + qtd * risco_un <= caixa:
                        m['strikes'] = {c[0]: (c[2], c[1]) for c in cad}
                        posicoes[a] = {**m, 'qtd': qtd, 'entrada': d, 'estrutura': estrutura, 'risco_un': risco_un}
                        travado += qtd * risco_un
            if a in pendentes and pendentes[a][1] <= 0:
                pendentes.pop(a)
            # 2) saída (nunca no mesmo pregão da entrada: as mesmas ofertas não dizem nada novo)
            if a in posicoes and posicoes[a]['entrada'] != d:
                pos = posicoes[a]
                dte = (ch._dia(pos['vencimento']) - ch._dia(d)).days
                rec = custo_recompra(pos, cad, p['custo'], meio=bool(p.get('exec_meio')))
                # auditoria: decidir pelo preço médio das ofertas (a execução continua na oferta)
                gat = custo_recompra(pos, cad, p['custo'], meio=True) if p.get('saida_meio') else rec
                motivo = None
                if dte <= 0:
                    rec, motivo = intrinseco(pos, cad, s), 'vencimento'
                elif rec is not None and gat is not None:
                    if gat <= pos['credito'] * (1 - p['alvo']):
                        motivo = 'alvo'
                    elif gat >= pos['credito'] * p['stop']:
                        motivo = 'stop'
                    elif dte <= p['dte_saida']:
                        motivo = 'prazo'
                if motivo:
                    rec = min(rec, pos['largura'] + p['custo'] * len(pos['pernas']))
                    pnl = (pos['credito'] - rec) * pos['qtd']
                    caixa += pnl
                    travado -= pos['qtd'] * pos['risco_un']
                    operacoes.append({'ativo': a, 'estrutura': pos['estrutura'], 'entrada': pos['entrada'],
                                      'saida': d, 'motivo': motivo, 'pnl': round(pnl, 2),
                                      'risco': round(pos['qtd'] * pos['risco_un'], 2),
                                      'credito': round(pos['credito'], 4), 'spread': round(pos['spread'], 4)})
                    del posicoes[a]
            # 3) sinal para amanhã
            if a not in posicoes and a not in pendentes and ind[a].pronto() and len(hist_iv[a]) >= ch.JANELA_RANK \
                    and (d, a) in ivs and not (a == 'PRIO3' and d < INICIO_PRIO3):
                elegiveis += 1
                rank = ch.iv_rank(hist_iv[a])
                if sorteio:
                    est = escolher(ind[a], s, {**p, 'gatilho': 'simples'})[0] if rng.random() < sorteio[0] else None
                    minimo = None
                else:
                    est, minimo = escolher(ind[a], s, p)
                if est and (minimo is None or rank >= minimo):
                    pendentes[a] = [est, atraso]
                    sinais += 1
        if ativo_no_periodo:
            aberto = 0.0
            for a, pos in posicoes.items():
                rec = custo_recompra(pos, cadeia.get((d, a), []), p['custo'], meio=bool(p.get('exec_meio')))
                if rec is not None:
                    aberto += (pos['credito'] - min(rec, pos['largura'])) * pos['qtd']
            valor = caixa + aberto
            pico = max(pico, valor)
            queda_max = max(queda_max, 1 - valor / pico)
            curva.append((d, round(valor, 2)))
        anterior = d
    return {'operacoes': operacoes, 'curva': curva, 'final': caixa, 'queda_max': queda_max,
            'cdi': cdi_acum - 1, 'abertas': len(posicoes), 'elegiveis': elegiveis, 'sinais': sinais}


def metricas(res, bova):
    ops = res['operacoes']
    ganhos = sum(o['pnl'] for o in ops if o['pnl'] > 0)
    perdas = -sum(o['pnl'] for o in ops if o['pnl'] < 0)
    por_ativo = {}
    for o in ops:
        por_ativo[o['ativo']] = por_ativo.get(o['ativo'], 0) + o['pnl']
    melhor = max(por_ativo, key=por_ativo.get) if por_ativo else None
    retorno = res['final'] / CAPITAL - 1
    return {
        'operacoes': len(ops),
        'acerto': round(sum(o['pnl'] > 0 for o in ops) / len(ops), 3) if ops else None,
        'fatorLucro': round(ganhos / perdas, 2) if perdas else None,
        'retorno': round(retorno, 4), 'cdi': round(res['cdi'], 4), 'bova11': round(bova, 4),
        'quedaMax': round(res['queda_max'], 4),
        'pnlPorRisco': round(sum(o['pnl'] for o in ops) / sum(o['risco'] for o in ops), 4) if ops else None,
        'porAtivo': {k: round(v, 2) for k, v in sorted(por_ativo.items())},
        'melhorAtivo': melhor,
        'retornoSemMelhor': round(retorno - por_ativo.get(melhor, 0) / CAPITAL, 4) if melhor else None,
        'porEstrutura': {e: sum(1 for o in ops if o['estrutura'] == e) for e in ('trava_alta_put', 'trava_baixa_call', 'condor')},
        'motivos': {m: sum(1 for o in ops if o['motivo'] == m) for m in ('alvo', 'stop', 'prazo', 'vencimento')},
        'abertasNoFim': res['abertas'],
    }


def veredito(m, m_sem):
    criterios = {
        'acima do CDI': m['retorno'] > m['cdi'],
        'fator de lucro >= 1,2': (m['fatorLucro'] or 0) >= 1.2,
        '>= 50 operações': m['operacoes'] >= 50,
        'queda máxima <= 15%': m['quedaMax'] <= 0.15,
        'sem o melhor ativo, acima do CDI': (m['retornoSemMelhor'] or -1) > m['cdi'],
        'filtro de IV Rank melhora o resultado por operação': (m['pnlPorRisco'] or -1) > (m_sem['pnlPorRisco'] or -1),
    }
    return criterios, all(criterios.values())


def retorno_bova(spot, inicio, fim):
    serie = sorted((d, v) for (d, a), v in spot.items() if a == 'BOVA11' and inicio <= d <= fim)
    return serie[-1][1] / serie[0][1] - 1 if len(serie) > 1 else 0.0


def markdown(saida):
    pct = lambda x: '–' if x is None else f'{x * 100:.1f}%'
    l = ['## Hipótese O1: travas de crédito filtradas por IV Rank (B3)', '']
    for periodo in ('fora', 'dentro'):
        l += [f'### {"Fora" if periodo == "fora" else "Dentro"} da amostra ({PERIODOS[periodo][0][:4]}–{PERIODOS[periodo][1][:4]})', '',
              '| Versão | Operações | Acerto | Fator de lucro | Retorno | CDI | BOVA11 | Queda máx. | P&L / risco |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for nome, r in saida['versoes'].items():
            m = r[periodo]
            l.append(f"| {nome} | {m['operacoes']} | {pct(m['acerto'])} | {m['fatorLucro']} | {pct(m['retorno'])} | "
                     f"{pct(m['cdi'])} | {pct(m['bova11'])} | {pct(m['quedaMax'])} | {pct(m['pnlPorRisco'])} |")
        l.append('')
    base = saida['versoes']['base']['fora']
    l += ['### Base, fora da amostra: detalhes', '', f"- Por ativo (R$): {base['porAtivo']}",
          f"- Por estrutura: {base['porEstrutura']}", f"- Motivo de saída: {base['motivos']}",
          f"- Retorno sem o melhor ativo ({base['melhorAtivo']}): {pct(base['retornoSemMelhor'])}", '',
          '### Critérios da versão simples (fora da amostra)', '']
    for k, v in saida['criterios'].items():
        l.append(f'- {"OK" if v else "FALHOU"}: {k}')
    l += ['', f"**Veredito da versão simples: {'APROVADA' if saida['aprovada'] else 'REPROVADA'}**", '',
          '### Critérios da versão técnica (fora da amostra)', '']
    for k, v in saida['criteriosTecnica'].items():
        l.append(f'- {"OK" if v else "FALHOU"}: {k}')
    l += ['', f"**Veredito da versão técnica: {'APROVADA' if saida['aprovadaTecnica'] else 'REPROVADA'}**",
          f"- Técnica melhor que a simples por operação: {'sim' if saida['tecnicaMelhorQueSimples'] else 'não'}", '']
    return '\n'.join(l)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--anos', default='2018-2026')
    ap.add_argument('--saida', default='opcoes_resultado')
    args = ap.parse_args(argv)
    a0, a1 = (int(x) for x in args.anos.split('-'))
    os.makedirs(args.saida, exist_ok=True)
    try:
        CDI.update(ch.baixar_cdi(date(a0, 1, 1), date.today()))
    except Exception as e:  # noqa: BLE001
        print(f'CDI indisponível ({e}); usando {ch.CDI_RESERVA:.0%}', flush=True)
    dados = carregar(range(a0, a1 + 1))
    saida = {'versoes': {}}
    versoes = [{}, TECNICO, {**TECNICO, 'nome': 'técnica sem filtro de IV Rank', 'ivr_tendencia': None,
                                 'ivr_lateral': None}] + VARIANTES
    for v in versoes:
        p = {**BASE, **v}
        saida['versoes'][p['nome']] = {}
        for periodo, (ini, fim) in PERIODOS.items():
            t0 = time.time()
            res = simular(dados, p, ini, fim)
            saida['versoes'][p['nome']][periodo] = metricas(res, retorno_bova(dados[1], ini, fim))
            if p['nome'] == 'base':
                with open(os.path.join(args.saida, f'operacoes_{periodo}.json'), 'w') as f:
                    json.dump(res['operacoes'], f, indent=1)
            print(f"{p['nome']} / {periodo}: {len(res['operacoes'])} operações, {time.time() - t0:.0f}s", flush=True)
    vs = saida['versoes']
    saida['criterios'], saida['aprovada'] = veredito(vs['base']['fora'], vs['sem filtro de IV Rank']['fora'])
    saida['criteriosTecnica'], saida['aprovadaTecnica'] = veredito(vs['técnica']['fora'],
                                                                   vs['técnica sem filtro de IV Rank']['fora'])
    saida['tecnicaMelhorQueSimples'] = (vs['técnica']['fora']['pnlPorRisco'] or -1) > (vs['base']['fora']['pnlPorRisco'] or -1)
    with open(os.path.join(args.saida, 'travas.json'), 'w') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    texto = markdown(saida)
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
