"""Gera data/agente.json: o resumo diário que o agente analista (skill `analista-invest`) lê.

Junta, em menos de 200 KB, o que hoje está espalhado em dezenas de MB: saúde da coleta, termômetro do
índice, amplitude, CDI/IPCA/PTAX do Banco Central, listas do dia, vendidos, calendário de balanços, um
resumo por papel (Ibovespa inteiro, os EUA mais negociados e a watchlist) e o placar do teste para frente
da estratégia congelada.

Só descreve. Nada aqui é sinal de compra ou venda; o agente também não pode tratar como tal.

Uso: python coleta/agente.py PASTA_DO_SITE [BANCO_COTAHIST]
  lê PASTA/data/carteira.json e PASTA/antigo/data/ (EUA) e PASTA/antigo/data/br/ (Brasil), quando existem;
  grava PASTA/data/agente.json. BANCO_COTAHIST (opcional, DuckDB de coleta/cotahist_db.py) dá o volume dos papéis
  da B3 que o app não acompanha, para o radar amplo de vendidos (radarVendidos).
"""
import glob
import json
import math
import os
import sys
from datetime import date, datetime, timezone

try:
    from calendario import pregoes_entre
    from encerrados import separar as separar_encerrados
except ImportError:  # rodando de fora da pasta coleta/
    from coleta.calendario import pregoes_entre
    from coleta.encerrados import separar as separar_encerrados

VERSAO = 1
LIMITE_BYTES = 200 * 1024  # 24/11/2026: era 100 KB; subiu com os indicadores técnicos (tec)
N_LISTA = 10
N_PAPEIS_EUA = 60
DIAS_BALANCO = 14
# radar amplo de vendidos (25/11/2026): o relatório INTEIRO da FINRA e da B3, não só os papéis com preço no app
N_RADAR = 40
RADAR_EUA_MIN_VOL = 100_000        # ações por dia (média da FINRA); abaixo disso "dias para zerar" é ruído
RADAR_EUA_MIN_QTD = 500_000        # ações vendidas; em papéis minúsculos a variação % explode sem significar nada
RADAR_EUA_MERCADOS_FORA = ('OTC',)  # marketClassCode da FINRA: balcão fica de fora (NYSE, NNM, SC, ARCA, BZX, AMEX entram)
RADAR_BR_MIN_VALOR = 5_000_000     # R$ alugados
RADAR_BR_MIN_VOLFIN = 200_000      # R$ negociados por dia (média de 20 pregões)
BASE_CARTEIRA = {'BOVA11', 'IVVB11', 'BTC'}
DIAS_FINRA_VELHO = 15
AVISO = ('Resumo descritivo gerado pelo Invest. Não é recomendação de investimento. Nenhum campo é sinal de '
         'compra ou venda; a estratégia técnica está congelada desde 04/11/2026 e perdeu para o índice.')


# ---------------- leitura ----------------
def ler_json(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def ler_precos(pasta):
    saida = {}
    for arq in sorted(glob.glob(os.path.join(pasta, 'precos_*.json'))):
        obj = ler_json(arq) or {}
        if obj.get('formato') == 'colunar-v1':
            cal = obj.get('datas') or []
            for t, a in (obj.get('ativos') or {}).items():
                n = len(a['close'])
                datas = a['dates'] if 'dates' in a else cal[a['i0']:a['i0'] + n]
                saida[t] = {'dates': datas, 'close': a['close'], 'volume': a.get('volume') or [0] * n}
                for k in ('open', 'high', 'low'):  # 24/11/2026: OHLC para ATR e estocástico
                    if a.get(k) and len(a[k]) == n:
                        saida[t][k] = a[k]
        else:
            saida.update(obj)
    return saida


def volume_cotahist(banco, n=20):
    """{codneg: (quantidade média, volume financeiro médio)} dos últimos n pregões de cada papel no banco COTAHIST.
    Sem duckdb ou sem banco devolve {} (o radar do Brasil fica só com os papéis que o app acompanha)."""
    if not banco or not os.path.exists(banco):
        return {}
    try:
        import duckdb
        con = duckdb.connect(banco, read_only=True)
        try:
            linhas = con.execute("""
                WITH ult AS (SELECT data FROM (SELECT DISTINCT data FROM pregoes) ORDER BY data DESC LIMIT ?)
                SELECT codneg, avg(quantidade), avg(volume) FROM pregoes WHERE data IN (SELECT data FROM ult)
                GROUP BY codneg""", [n]).fetchall()
        finally:
            con.close()
        return {c: (q, v) for c, q, v in linhas}
    except Exception as e:  # noqa: BLE001 - opcional, nunca derruba o agente.json
        print(f'agente: volume do COTAHIST indisponível ({e})', file=sys.stderr)
        return {}


def radar_vendidos(todos_arq, precos, nome, vol_b3=None):
    """Os N_RADAR papéis com mais dias para zerar a posição vendida no relatório inteiro da bolsa.
    Cada item: [ticker, dias, variacaoPct (EUA) ou valor alugado em R$ mi (BR), fora do app (1/0), nome]."""
    ativos = (todos_arq or {}).get('ativos') or {}
    if not ativos:
        return None
    itens = []
    for t, a in ativos.items():
        fora = 0 if t in precos else 1
        if nome == 'us':
            if (a.get('mercado') or '').upper() in RADAR_EUA_MERCADOS_FORA or (a.get('volMedio') or 0) < RADAR_EUA_MIN_VOL \
                    or (a.get('qtd') or 0) < RADAR_EUA_MIN_QTD:
                continue
            dias = a.get('diasFinra')
            if dias is None:
                continue
            itens.append([t, r(dias, 1), a.get('variacaoPct'), fora, a.get('nome')])
        else:
            if (a.get('valor') or 0) < RADAR_BR_MIN_VALOR:
                continue
            s = precos.get(t)
            if s:
                qm = media([v for v in s.get('volume', [])[-20:] if v])
                fin = media([c * v for c, v in zip(s['close'][-20:], s.get('volume', [])[-20:]) if c and v])
            else:
                qm, fin = (vol_b3 or {}).get(t, (None, None))
            if not qm or (fin or 0) < RADAR_BR_MIN_VOLFIN:
                continue
            itens.append([t, r(a['qtd'] / qm, 1), r(a['valor'] / 1e6, 1), fora, None])
    itens.sort(key=lambda x: (-x[1], x[0]))
    return {'fonte': todos_arq.get('fonte'), 'data': todos_arq.get('data'), 'papeisNoRelatorio': len(ativos),
            'arquivoCompleto': f'vendidos-todos-{nome}.json', 'itens': itens[:N_RADAR]}


# ---------------- contas ----------------
def r(x, casas=4):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(x, casas)


def ret(c, k):
    return c[-1] / c[-1 - k] - 1 if len(c) > k and c[-1 - k] else None


def media(v):
    return sum(v) / len(v) if v else None


def desvio(v):
    m = media(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) if len(v) > 1 else None


def vol_anual(c, janela=21):
    rets = [c[i] / c[i - 1] - 1 for i in range(max(1, len(c) - janela), len(c)) if c[i - 1]]
    d = desvio(rets)
    return d * math.sqrt(252) if d is not None else None


def dist_mm(c, n):
    return c[-1] / media(c[-n:]) - 1 if len(c) >= n else None


def queda_topo(c, janela=252):
    pico = max(c[-janela:])
    return 1 - c[-1] / pico if pico else None


# ---------------- indicadores técnicos (24/11/2026, pedido do Diego) ----------------
# Contexto para o Consultor e para o alerta informativo do app. NENHUM destes indicadores foi testado como regra
# neste projeto (a estratégia técnica está congelada desde 04/11/2026); não são sinal de compra ou venda.
MIN_TEC, JANELA_TEC = 60, 400


def ema(v, n):
    k, e, out = 2 / (n + 1), None, []
    for x in v:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def ifr(c, n=14):
    """IFR (RSI) de Wilder, 0–100. Sem variação nenhuma: 50."""
    if len(c) <= n:
        return None
    dif = [c[i] - c[i - 1] for i in range(1, len(c))]
    g = sum(max(d, 0) for d in dif[:n]) / n
    p = sum(max(-d, 0) for d in dif[:n]) / n
    for d in dif[n:]:
        g = (g * (n - 1) + max(d, 0)) / n
        p = (p * (n - 1) + max(-d, 0)) / n
    if g == 0 and p == 0:
        return 50.0
    return 100.0 if p == 0 else 100 - 100 / (1 + g / p)


def atr_wilder(h, lo, c, n=14):
    if len(c) <= n:
        return None
    tr = [max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1])) for i in range(1, len(c))]
    a = sum(tr[:n]) / n
    for x in tr[n:]:
        a = (a * (n - 1) + x) / n
    return a


def tecnico(s, desde=0):
    """Indicadores técnicos descritivos do papel. Precisa de ≥ MIN_TEC fechamentos válidos; high/low são opcionais
    (sem eles, estocástico e ATR ficam de fora e suporte/resistência usam o fechamento). `desde`: só usa a série a partir
    desse índice (depois de um salto de escala, para não misturar duas escalas de preço)."""
    cl = s.get('close') or []
    hi, lo = s.get('high'), s.get('low')
    idx = [i for i, x in enumerate(cl) if x and i >= desde][-JANELA_TEC:]
    if len(idx) < MIN_TEC:
        return None
    c = [cl[i] for i in idx]
    ohlc = bool(hi and lo and len(hi) == len(cl) and len(lo) == len(cl)
                and all(hi[i] and lo[i] and hi[i] >= lo[i] for i in idx))
    h = [hi[i] for i in idx] if ohlc else None
    l_ = [lo[i] for i in idx] if ohlc else None
    p = c[-1]
    o = {'ifr14': r(ifr(c, 14), 3), 'ifr2': r(ifr(c, 2), 3)}
    if ohlc:
        hh, ll = max(h[-14:]), min(l_[-14:])
        if hh > ll:
            o['estoc'] = r((p - ll) / (hh - ll) * 100, 3)
    linha = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]
    sinal = ema(linha, 9)
    o['macd'] = r((linha[-1] - sinal[-1]) / p, 3) if p else None
    dif = [a - b for a, b in zip(linha[-4:], sinal[-4:])]
    cruz = 0
    for a, b in zip(dif, dif[1:]):
        if a <= 0 < b:
            cruz = 1
        elif a >= 0 > b:
            cruz = -1
    o['macdCruz'] = cruz
    o['mm21'], o['mm50'] = r(dist_mm(c, 21), 3), r(dist_mm(c, 50), 3)
    j = c[-20:]
    m = media(j)
    dp = math.sqrt(sum((x - m) ** 2 for x in j) / len(j))
    if m:
        o['bbLarg'] = r(4 * dp / m, 3)
    if dp:
        o['bbPct'] = r((p - (m - 2 * dp)) / (4 * dp), 3)
    if ohlc:
        a = atr_wilder(h, l_, c)
        if a is not None:
            o['atr'] = r(a, 3)
            o['atrPct'] = r(a / p, 3) if p else None
    o['sup'] = r(min((l_ if ohlc else c)[-20:]), 3)
    o['res'] = r(max((h if ohlc else c)[-20:]), 3)
    return {k: v for k, v in o.items() if v is not None}


# ---------------- dado suspeito (25/11/2026, achados do Consultor) ----------------
# Caso RAIZ4: o Yahoo emendou o código novo (RAIZ55) multiplicado por 40 e depois por 100, sem registrar grupamento,
# e o m1 saiu +3.209%. Regra: salto de ESCALA (preço > 10× ou < 0,1× a mediana dos 20 pregões anteriores) ou alta
# > +150% num pregão, sem desdobramento registrado, ANULA os campos cuja janela contém o salto. Queda grande sozinha
# (≥ 45% além da queda do índice no dia) só vira alerta: a queda real e geral de 26/10/2026 (Ibovespa −13,9%; MOVI3 e
# MGLU3 −58%, confirmadas no COTAHIST da B3) não pode ser apagada.
ESCALA_SALTO, ALTA_SALTO = 10.0, 1.5
JANELAS = {'d1': 1, 'm1': 21, 'a1': 252, 'mm200': 200, 'topo52': 252, 'vol': 21, 'volFinMi': 20}


def saltos(datas, c, ret_idx=None, desd=()):
    """[(i, data, preço anterior, preço, 'escala'|'alta'|'queda')] de uma série sem zeros/None."""
    out, desd, ini = [], set(desd or ()), 0
    for i in range(1, len(c)):
        a, b = c[i - 1], c[i]
        if not a or not b:
            continue
        d = datas[i] if datas and i < len(datas) else None
        if d in desd:
            continue
        ant = sorted(c[max(ini, i - 20):i])  # depois de um salto de escala, a referência é a escala nova
        med = ant[len(ant) // 2]
        x = b / a - 1
        ri = (ret_idx or {}).get(d, 0) if d else 0
        if med and (b > ESCALA_SALTO * med or b < med / ESCALA_SALTO):
            out.append((i, d, a, b, 'escala'))
            ini = i
        elif x > ALTA_SALTO and ri < ALTA_SALTO / 2:
            out.append((i, d, a, b, 'alta'))
        elif x - min(0, ri) <= -SALTO_SUSPEITO:
            out.append((i, d, a, b, 'queda'))
    return out


def resumo_papel(s, fund=None, vend=None, ret_idx=None, desd=()):
    val = [i for i, x in enumerate(s['close']) if x]
    c = [s['close'][i] for i in val]
    if len(c) < 2:
        return None
    ds = s.get('dates') or []
    datas = [ds[i] for i in val] if len(ds) == len(s['close']) else []
    vol = s.get('volume') or []
    pares = [(x, y) for x, y in zip(s['close'][-20:], vol[-20:]) if x and y]
    sal = saltos(datas, c, ret_idx, desd)
    anula = [e for e in sal if e[4] in ('escala', 'alta')]
    desde = val[anula[-1][0]] if anula else 0
    o = {'p': r(c[-1], 2), 'd1': r(ret(c, 1)), 'm1': r(ret(c, 21)), 'a1': r(ret(c, 252)),
         'mm200': r(dist_mm(c, 200)), 'topo52': r(queda_topo(c)), 'vol': r(vol_anual(c), 3),
         'volFinMi': r(sum(x * y for x, y in pares) / len(pares) / 1e6, 1) if pares else None,
         'tec': tecnico(s, desde)}
    alertas = []
    for i, d, a, b, tipo in sal:
        if len(c) - 1 - i >= 252:
            continue  # fora de todas as janelas
        if tipo == 'queda':
            alertas.append(f'queda de {round((b / a - 1) * 100)}% em {d or "?"} além do índice ({r(a, 2)} → {r(b, 2)}); confirme se é evento real')
            continue
        nulos = [k for k, w in JANELAS.items() if len(c) - 1 - i < w and o.get(k) is not None]
        for k in nulos:
            o[k] = None
        alertas.append(f'salto de {"escala" if tipo == "escala" else "alta"} em {d or "?"} ({r(a, 4)} → {r(b, 4)}) sem desdobramento '
                       f'registrado; anulados: {", ".join(nulos) or "nenhum"}; tec {"só com os pregões depois do salto" if o.get("tec") is not None else "anulado"}')
    if fund:
        for k_src, k_dst in (('pe', 'pl'), ('pb', 'pvp'), ('roe', 'roe'), ('netMargin', 'margem'),
                             ('revenueGrowth', 'cresc'), ('debtToEquity', 'divPl')):
            if fund.get(k_src) is not None:
                o[k_dst] = r(fund[k_src], 3)
        if fund.get('sector'):
            o['setor'] = fund['sector']
        if fund.get('nextEarningsDate'):
            o['balanco'] = fund['nextEarningsDate']
        if fund.get('alertaEvento'):
            o['alerta8k'] = fund['alertaEvento']
        if fund.get('operatingMargins') is not None:
            o['margemOp'] = r(fund['operatingMargins'], 3)
        alertas += alertas_fundamentos(fund)
    if vend:
        o['vendido'] = vendido_completo(vend, fund or {})
        if vend.get('finraVelho'):
            alertas.append(vend['finraVelho'])
    if alertas:
        o['alertasDado'] = alertas
    return {k: v for k, v in o.items() if v is not None}


def alertas_fundamentos(f):
    """Valores fora de faixas plausíveis (podem estar certos; é para conferir, não para descartar)."""
    al = []
    roe, pe, nm, om = f.get('roe'), f.get('pe'), f.get('netMargin'), f.get('operatingMargins')
    if roe is not None and roe > 1:
        al.append(f'ROE de {round(roe * 100)}%: patrimônio pequeno ou recompras; confira')
    if pe is not None and (pe > 100 or pe < 0):
        al.append(f'P/L {r(pe, 1)}: lucro perto de zero ou negativo, P/L sem sentido')
    if nm is not None and om is not None and nm > 0 and (om < 0 or (om > 0 and nm > 2 * om)):
        al.append(f'margem líquida {round(nm * 100)}% contra operacional {round(om * 100)}%: lucro não operacional')
    return al


def vendido_completo(v, f):
    """BR (aluguel B3): qtd, valor em R$, preço médio, dias para zerar, % das ações e do free float.
    EUA (FINRA + Yahoo): qtd e dias para cobrir do FINRA com a data, % do float, shortRatio e ações vendidas do Yahoo."""
    o = {k: v[k] for k in ('dias', 'variacaoPct', 'diasFinra', 'qtd', 'valor', 'precoMedio', 'dataFinra') if v.get(k) is not None}
    so, fl = f.get('sharesOutstanding'), f.get('floatShares')
    if v.get('qtd') and so:
        o['pctAcoes'] = r(v['qtd'] / so, 4)
    if v.get('qtd') and fl:
        o['pctFloat'] = r(v['qtd'] / fl, 4)
    for k_src, k_dst in (('shortPercentOfFloat', 'shortPctFloat'), ('shortRatio', 'shortRatio'),
                         ('sharesShort', 'sharesShort'), ('dateShortInterest', 'dataShortInterest')):
        if v.get('mercado') == 'us' and f.get(k_src) is not None:
            o[k_dst] = f[k_src] if isinstance(f[k_src], str) else r(f[k_src], 4)
    return o or None


def termometro(indice):
    if not indice:
        return None
    s = (indice.get('series') or {}).get(indice.get('principal'))
    if not s or len(s.get('close') or []) < 260:
        return None
    c, d = s['close'], s['dates']
    fim_mes = [c[i] for i in range(len(c)) if i == len(c) - 1 or d[i][:7] != d[i + 1][:7]]
    mm10 = media(fim_mes[-10:]) if len(fim_mes) >= 10 else None
    q = 1 - c[-1] / max(c)
    o = {'nome': s.get('nome'), 'data': d[-1], 'ult': r(c[-1], 2), 'distMM200': r(dist_mm(c, 200)),
         'acimaMM10m': (c[-1] > mm10) if mm10 else None, 'distMM10m': r(c[-1] / mm10 - 1) if mm10 else None,
         'quedaTopo': r(q), 'quedaTopo52': r(queda_topo(c)), 'ret1m': r(ret(c, 21)), 'ret3m': r(ret(c, 63)),
         'ret12m': r(ret(c, 252)), 'vol': r(vol_anual(c), 3)}
    if mm10:  # mesma regra do termômetro do app (descrição, não sinal)
        o['ambiente'] = 'tendência de alta' if o['acimaMM10m'] and q < 0.10 else 'queda' if not o['acimaMM10m'] and q >= 0.15 else 'misto'
    rf = (indice.get('series') or {}).get(indice.get('rendaFixa'))
    if rf and len(rf.get('close') or []) > 252:
        o['rendaFixa'] = {'nome': rf.get('nome'), 'ret12m': r(ret(rf['close'], 252)), 'ret1m': r(ret(rf['close'], 21))}
    return o


# ---------------- situações parecidas (15/11/2026, pedido do Diego) ----------------
# "Quem está passando pela mesma situação" da MGLU3 em 03/11: queda forte desde a máxima de 60 pregões, com o
# histórico DO PRÓPRIO PAPEL nas vezes anteriores em que caiu assim (cada papel tem a sua cara; não mistura cestas).
# É contexto para o Diego decidir. NÃO é sinal: o cenário "queda ≥ 30% + Otimista" foi reprovado em 04/11
# (docs/cenario-queda-reversao.md, perfil de loteria). Nada aqui foi escolhido olhando o resultado.
QUEDA_SITUACAO, JANELA_SITUACAO, HORIZONTES, ESPACO_EPISODIOS, N_SITUACOES, SALTO_SUSPEITO = 0.30, 60, (20, 60), 60, 15, 0.45


def episodios_queda(c, limiar=QUEDA_SITUACAO, janela=JANELA_SITUACAO, espaco=ESPACO_EPISODIOS):
    """Índices dos dias em que o fechamento ficou `limiar` abaixo da máxima dos `janela` pregões (contando o dia);
    um novo episódio só começa `espaco` pregões depois do anterior."""
    eps, ult = [], -10 ** 9
    for i in range(janela - 1, len(c)):
        pico = max(c[i - janela + 1:i + 1])
        if pico and c[i] <= (1 - limiar) * pico and i - ult >= espaco:
            eps.append(i)
            ult = i
    return eps


def situacoes(precos, vend, indice):
    s_ind = ((indice or {}).get('series') or {}).get((indice or {}).get('principal')) or {}
    idx = dict(zip(s_ind.get('dates') or [], s_ind.get('close') or []))
    di, ci = s_ind.get('dates') or [], s_ind.get('close') or []
    ret_idx = {di[k]: ci[k] / ci[k - 1] - 1 for k in range(1, len(ci)) if ci[k] and ci[k - 1]}  # queda do mercado no dia
    out = []
    for t, s in precos.items():
        d, c, v = s.get('dates') or [], s.get('close') or [], s.get('volume') or []
        if len(c) < JANELA_SITUACAO + 5 or not all(c[-JANELA_SITUACAO:]):
            continue
        pico = max(c[-JANELA_SITUACAO:])
        queda = 1 - c[-1] / pico if pico else 0
        if queda < QUEDA_SITUACAO:
            continue
        eps = episodios_queda(c)
        atual = eps[-1] if eps and eps[-1] >= len(c) - ESPACO_EPISODIOS else None
        hist = []
        for i in eps:
            if i == atual:
                continue
            caso = [d[i]]
            for h in HORIZONTES:
                if i + h < len(c) and c[i]:
                    rp = c[i + h] / c[i] - 1
                    ri = idx[d[i + h]] / idx[d[i]] - 1 if d[i] in idx and d[i + h] in idx and idx[d[i]] else None
                    caso += [r(rp), r(rp - ri) if ri is not None else None]
                else:
                    caso += [None, None]
            hist.append(caso)
        saltos = [(d[k], c[k] / c[k - 1] - 1) for k in range(max(1, len(c) - JANELA_SITUACAO), len(c)) if c[k - 1] and c[k] / c[k - 1] - 1 - min(0, ret_idx.get(d[k], 0)) <= -SALTO_SUSPEITO]  # desconta a queda do índice no dia (26/10/2026: queda real e geral)
        v5, v60 = media([x for x in v[-5:] if x]), media([x for x in v[-JANELA_SITUACAO - 5:-5] if x])  # 5 pregões contra os 60 anteriores

        def resumo_h(k):  # k = posição do excesso sobre o índice no caso
            xs = [h[k] for h in hist if h[k] is not None]
            return {'n': len(xs), 'mediana': r(sorted(xs)[len(xs) // 2]) if xs else None, 'acimaIndice': r(sum(x > 0 for x in xs) / len(xs), 2) if xs else None}
        o = {'p': t, 'queda60': r(queda, 3), 'desde': d[atual] if atual is not None else None,
             'diasVendido': (vend.get(t) or {}).get('dias'), 'volumeRel': r(v5 / v60, 2) if v5 and v60 else None,
             'historico': {'casos': len(hist), 'h20': resumo_h(2), 'h60': resumo_h(4), 'ultimos': hist[-5:]}}
        if saltos:
            o['saltoSuspeito'] = [[dt, r(x, 3)] for dt, x in saltos]
        out.append(o)
    out.sort(key=lambda o: -o['queda60'])
    return out[:N_SITUACOES]


def placar_diario(diario, indice):
    if not diario or not isinstance(diario.get('sinais'), list):
        return None
    sinais = diario['sinais']
    fech = [x for x in sinais if x.get('estado') == 'fechado' and x.get('ret') is not None]
    o = {'inicio': diario.get('inicio'), 'anotados': len(sinais), 'fechados': len(fech),
         'abertos': sum(1 for x in sinais if x.get('estado') == 'aberto'), 'metaFechados': 100, 'reavaliacao': '2027-11-04',
         'regrasDesligadas': sorted(k for k, v in (diario.get('regras') or {}).items() if v.get('desligada'))}
    if fech:
        rets = [x['ret'] for x in fech]
        o.update({'retMedio': r(media(rets)), 'acerto': r(sum(1 for x in rets if x > 0) / len(rets), 3)})
        s = (indice or {}).get('series', {}).get((indice or {}).get('principal')) if indice else None
        if s:
            pos = {d: i for i, d in enumerate(s['dates'])}
            ri = [s['close'][pos[x['dataSaida']]] / s['close'][pos[x['dataEntrada']]] - 1
                  for x in fech if x.get('dataEntrada') in pos and x.get('dataSaida') in pos]
            if ri:
                o['indiceMesmasDatas'] = r(media(ri))
    return o


def mercado(pasta, nome, hoje, n_papeis=None, extras=(), guardar=None, vol_b3=None):
    m = ler_json(os.path.join(pasta, 'manifest.json'))
    if not m:
        return None
    precos = ler_precos(pasta)
    fund = ler_json(os.path.join(pasta, m.get('arquivoFundamentos') or 'fundamentos.json')) or {}
    # 25/11/2026: ações e BDRs da watchlist fora do universo (coleta/extras.py), com o mesmo tratamento
    pasta_ext = os.path.join(pasta, 'extras')
    precos_ext = {t: s for t, s in ler_precos(pasta_ext).items() if t not in precos} if os.path.isdir(pasta_ext) else {}
    fund_ext = ler_json(os.path.join(pasta_ext, 'fundamentos.json')) or {} if precos_ext else {}
    if guardar is not None:
        guardar[nome] = {**precos_ext, **precos}
    vend_arq = ler_json(os.path.join(pasta, m.get('arquivoVendidos') or 'vendidos.json')) or {}
    vend_todos = ler_json(os.path.join(pasta, 'vendidos-todos.json'))
    indice = ler_json(os.path.join(pasta, m.get('arquivoIndice') or 'indice.json'))
    diario = ler_json(os.path.join(pasta, 'diario.json'))

    # dias de vendidos: quantidade vendida ÷ volume médio de 20 dias (o FINRA já manda o dele)
    vend = {}
    try:
        idade_vend = (hoje - date.fromisoformat(vend_arq['data'])).days if vend_arq.get('data') else None
    except ValueError:
        idade_vend = None
    finra_velho = (f'dado FINRA de {vend_arq["data"]} ({idade_vend} dias; publicação quinzenal)'
                   if nome == 'us' and idade_vend is not None and idade_vend > DIAS_FINRA_VELHO else None)
    for t, a in (vend_arq.get('ativos') or {}).items():
        s = precos.get(t) or precos_ext.get(t)
        vm = media([v for v in (s or {}).get('volume', [])[-20:] if v]) if s else None
        dias = a.get('diasFinra') if a.get('diasFinra') is not None else (a['qtd'] / vm if vm and a.get('qtd') else None)
        vend[t] = {'dias': r(dias, 1), 'variacaoPct': a.get('variacaoPct'), 'qtd': a.get('qtd'), 'mercado': nome,
                   'valor': a.get('valor'),  # preço médio = valor ÷ qtd (na linha Total da B3 o AvgPric vem vazio)
                   'precoMedio': r(a['valor'] / a['qtd'], 2) if a.get('valor') and a.get('qtd') else None,
                   'dataFinra': vend_arq.get('data') if nome == 'us' else None, 'finraVelho': finra_velho}

    s_ind = ((indice or {}).get('series') or {}).get((indice or {}).get('principal')) or {}
    di, ci = s_ind.get('dates') or [], s_ind.get('close') or []
    ret_idx = {di[k]: ci[k] / ci[k - 1] - 1 for k in range(1, len(ci)) if ci[k] and ci[k - 1]}
    if guardar is not None:
        guardar[nome + ':indice'] = ret_idx
    resumos = {t: resumo_papel(s, fund.get(t), vend.get(t), ret_idx) for t, s in precos.items()}
    resumos = {t: v for t, v in resumos.items() if v}
    resumos_ext = {}
    for t, s in precos_ext.items():
        v = resumo_papel(s, fund_ext.get(t), vend.get(t), ret_idx)
        if v:
            v['extra'] = True
            resumos_ext[t] = v
    com = lambda k: [(t, v[k]) for t, v in resumos.items() if v.get(k) is not None]  # noqa: E731

    def top(k, rev=True, n=N_LISTA):
        return [[t, x] for t, x in sorted(com(k), key=lambda kv: (-kv[1] if rev else kv[1], kv[0]))[:n]]
    listas = {'altas': top('d1'), 'quedas': top('d1', False), 'maisNegociados': top('volFinMi'),
              'longeDoTopo': top('topo52'), 'maisVolateis': top('vol')}
    vendidos = sorted(([t, v['dias'], v.get('variacaoPct')] for t, v in vend.items() if v.get('dias') is not None and t in resumos),
                      key=lambda x: -x[1])[:N_LISTA]
    acima = [v['mm200'] > 0 for v in resumos.values() if 'mm200' in v]
    balancos = []
    for t, f in fund.items():
        d = (f or {}).get('nextEarningsDate')
        try:
            dd = (date.fromisoformat(d[:10]) - hoje).days if d else None
        except ValueError:
            dd = None
        if dd is not None and 0 <= dd <= DIAS_BALANCO and t in resumos:
            balancos.append([d[:10], t])
    balancos.sort()

    if n_papeis:
        escolhidos = {t for t, _ in sorted(com('volFinMi'), key=lambda kv: -kv[1])[:n_papeis]}
        for lst in listas.values():
            escolhidos |= {t for t, _ in lst}
        escolhidos |= {x[0] for x in vendidos} | {t for _, t in balancos} | (set(extras) & set(resumos))
    else:
        escolhidos = set(resumos)
    ult = m.get('ultimoPregao')
    return {
        'mercado': nome, 'moeda': m.get('moeda'),
        'saude': {'geradoEm': m.get('geradoEm'), 'ultimoPregao': ult, 'papeis': len(resumos), 'extras': len(resumos_ext),
                  'avisos': m.get('avisos') or [], 'fundamentos': len(fund),
                  'vendidos': {'fonte': vend_arq.get('fonte'), 'data': vend_arq.get('data')} if vend_arq else None},
        'termometro': termometro(indice),
        'amplitude': {'acimaMM200': r(sum(acima) / len(acima), 3), 'papeis': len(acima)} if acima else None,
        'listas': listas, 'vendidos': vendidos, 'radarVendidos': radar_vendidos(vend_todos, {**precos_ext, **precos}, nome, vol_b3),
        'balancosProximos': balancos[:30],
        'testeParaFrente': placar_diario(diario, indice),
        'situacoes': situacoes(precos, vend, indice),
        'papeis': {t: ({**resumos, **resumos_ext})[t] for t in sorted(escolhidos | set(resumos_ext))},
    }


def carteira_resumo(cart):
    if not cart:
        return None, None, None
    cdi = cart.get('cdi') or {}
    acum = cdi.get('acum') or []
    ipca = cart.get('ipca') or {}
    var = ipca.get('var') or []
    a12 = 1.0
    for v in var[-12:]:
        a12 *= 1 + v / 100
    macro = {'cdi': {'data': (cdi.get('datas') or [None])[-1], 'ret1m': r(ret(acum, 21)), 'ret12m': r(ret(acum, 252))} if acum else None,
             'ipca': {'mes': (ipca.get('meses') or [None])[-1], 'varMes': r(var[-1] / 100) if var else None,
                      'acum12m': r(a12 - 1) if len(var) >= 12 else None},
             'ptax': cart.get('ptax')}
    ativos = cart.get('ativos') or {}
    ref = {}
    for t in ('BOVA11', 'IVVB11', 'BTC'):
        a = ativos.get(t)
        if a and len(a.get('fech') or []) > 22:
            ref[t] = {'data': a['datas'][-1], 'ret1m': r(ret(a['fech'], 21)), 'ret12m': r(ret(a['fech'], 252 if t != 'BTC' else 365))}
    if {'BOVA11', 'IVVB11'} <= set(ref) and macro['cdi']:
        for k in ('ret1m', 'ret12m'):
            vals = [ref['BOVA11'].get(k), ref['IVVB11'].get(k), macro['cdi'].get(k)]
            if None not in vals:
                ref.setdefault('ref13', {})[k] = r(sum(vals) / 3)
    watch = {}
    for t, a in ativos.items():
        if t in BASE_CARTEIRA or a.get('apoio'):
            continue
        serie = a.get('fechUSD') or a.get('fech') or []
        o = resumo_papel({'close': serie, 'volume': [], 'dates': a.get('datas') or []}, desd=[d[0] for d in a.get('desdobramentos') or [] if d]) or {}  # montar() troca pela série ajustada se houver
        o.pop('volFinMi', None)
        o['moeda'] = a.get('moeda') or 'BRL'
        if a.get('alavancado'):
            o['alavancado'] = a['alavancado']
        f = a.get('fund') or {}
        for k in ('lpa', 'vpa', 'dy', 'pl'):
            if f.get(k) is not None:
                o[k] = r(f[k], 3)
        watch[t] = o
    return macro, ref, watch


def saude_carteira(cart):
    """falhas = só o que falhou e deveria existir; encerrados = papéis que deixaram de negociar (continuam na coleta)."""
    if 'encerrados' in cart:
        enc, falhas = cart['encerrados'], cart.get('falhas') or []
    else:  # carteira.json anterior a 25/11/2026
        enc, falhas = separar_encerrados(cart.get('falhas') or [])
    return {'geradoEm': cart.get('geradoEm'), 'falhas': falhas, 'encerrados': enc}


def dias_uteis(de, ate, mercado='br'):
    """Pregões (calendário da B3 ou da NYSE, com feriados) depois de `de` até `ate`."""
    if not de:
        return None
    return pregoes_entre(de, ate, mercado)


def montar(site, hoje=None, cotahist=None):
    hoje = hoje or datetime.now(timezone.utc).date()
    cart = ler_json(os.path.join(site, 'data', 'carteira.json'))
    macro, ref, watch = carteira_resumo(cart)
    foc = ler_json(os.path.join(site, 'data', 'focus.json'))
    if foc:
        macro = dict(macro or {})
        macro['focus'] = {k: v for k, v in foc.items() if k != 'fonte'}
    base = os.path.join(site, 'antigo', 'data')
    series = {}
    us = mercado(base, 'us', hoje, n_papeis=N_PAPEIS_EUA, extras=watch or (), guardar=series) if os.path.isdir(base) else None
    br = mercado(os.path.join(base, 'br'), 'br', hoje, extras=watch or (), guardar=series, vol_b3=volume_cotahist(cotahist)) if os.path.isdir(os.path.join(base, 'br')) else None
    # watchlist: a carteira.json só tem fechamento SEM proventos (o motor da carteira precisa dela assim). Se o papel
    # está no universo ou nos extras, retornos e tec vêm da série ajustada (OHLC, proventos reinvestidos) desse mercado,
    # para bater com mercados.*.papeis (25/11/2026); senão ficam com o fechamento e semProventos = true.
    for t, o in (watch or {}).items():
        mk = ('us', 'br') if o.get('moeda') == 'USD' else ('br', 'us')
        s = next((series[k][t] for k in mk if t in series.get(k, {})), None)
        k_m = next((k for k in mk if t in series.get(k, {})), None)
        novo = resumo_papel(s, ret_idx=series.get(f'{k_m}:indice')) if s else None
        if novo:
            for k in ('p', 'd1', 'm1', 'a1', 'mm200', 'topo52', 'vol', 'tec', 'alertasDado'):
                o.pop(k, None)
                if novo.get(k) is not None:
                    o[k] = novo[k]
        else:
            o['semProventos'] = True
    series.clear()
    atrasos = [dias_uteis(m['saude']['ultimoPregao'], hoje, mk) for mk, m in (('us', us), ('br', br)) if m and m['saude'].get('ultimoPregao')]
    atraso = max(atrasos) if atrasos else None
    return {
        'versao': VERSAO, 'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'aviso': AVISO,
        'saude': {'carteira': saude_carteira(cart) if cart else None,
                  'diasUteisDesdeUltimoPregao': atraso,
                  'dadosVelhos': atraso is None or atraso > 3,
                  'mercadosAusentes': [n for n, m in (('us', us), ('br', br)) if not m]},
        'macro': macro, 'referencias': ref, 'watchlist': watch,
        'mercados': {k: v for k, v in (('br', br), ('us', us)) if v},
        'legenda': {'d1/m1/a1': 'retorno de 1 pregão, 21 pregões e 252 pregões (fração: 0.05 = 5%)',
                    'mm200': 'distância do preço para a média de 200 pregões', 'topo52': 'queda desde a máxima de 52 semanas',
                    'vol': 'volatilidade anualizada de 21 pregões', 'volFinMi': 'volume financeiro médio de 20 pregões, milhões na moeda do mercado',
                    'd1/m1/a1/mm200/topo52/vol': 'retornos com proventos reinvestidos (série ajustada) em mercados.*.papeis e na watchlist; semProventos = só preço (papel sem série ajustada)',
                    'extra': 'papel da watchlist fora do universo, baixado pelo mesmo caminho (série ajustada, fundamentos, vendidos); não entra em amplitude, listas, termômetro nem situações',
                    'alertasDado': 'dado para conferir: salto de escala ou alta > 150% num pregão sem desdobramento registrado (os campos cuja janela contém o salto são anulados), queda ≥ 45% além do índice (só aviso), ROE > 100%, P/L > 100 ou negativo, lucro não operacional (margem líquida > 0 com operacional < 0, ou líquida > 2× a operacional), dado FINRA com mais de 15 dias',
                    'margemOp': 'margem operacional (Yahoo operatingMargins), fração',
                    'radarVendidos': 'os 40 papéis com mais dias para zerar a posição vendida no relatório INTEIRO da bolsa (FINRA ou B3), inclusive papéis que o app não acompanha; itens = [ticker, dias, variação % da posição vendida (EUA) ou R$ mi alugados (BR), fora (1 = sem preço nem fundamentos no app), nome]; o relatório completo fica no arquivo arquivoCompleto, na mesma pasta do Drive; contexto, não sinal',
                    'vendido.dias': 'dias de volume para zerar a posição vendida (aluguel B3 ou short interest FINRA)',
                    'vendido BR': 'aluguel B3: qtd (ações alugadas), valor (R$), precoMedio (R$), pctAcoes = qtd ÷ ações emitidas, pctFloat = qtd ÷ free float (Yahoo)',
                    'vendido EUA': 'FINRA: qtd, diasFinra (dias para cobrir), dataFinra; Yahoo: shortPctFloat (fração do float vendida), shortRatio, sharesShort, dataShortInterest; pctFloat = qtd FINRA ÷ float do Yahoo',
                    'saude.carteira': 'falhas = papéis que deveriam existir e não vieram; encerrados = papéis que deixaram de negociar (última data na B3 e sucessor), mantidos na coleta da carteira',
                    'ref13': '1/3 BOVA11 + 1/3 IVVB11 + 1/3 CDI', 'macro.focus': 'boletim Focus do Banco Central: mediana das expectativas em % (selic no fim do ano, ipca e pib do ano, cambio em R$/US$ no fim do ano); antes = 4 semanas atrás', 'testeParaFrente': 'placar da estratégia congelada (regras de 04/11/2026)',
                    'tec': 'indicadores técnicos; indicador não testado como regra; contexto, não sinal de compra ou venda',
                    'tec.ifr14/ifr2': 'IFR (RSI) de Wilder de 14 e 2 pregões, 0–100 (abaixo de 30 / 10 costuma ser lido como sobrevendido; acima de 70 / 90, sobrecomprado); indicador não testado como regra; contexto',
                    'tec.estoc': 'estocástico %K de 14 pregões, 0–100: posição do fechamento entre a mínima e a máxima de 14 pregões; indicador não testado como regra; contexto',
                    'tec.macd': 'histograma do MACD (12,26; sinal 9) dividido pelo preço; positivo = MACD acima do sinal; indicador não testado como regra; contexto',
                    'tec.macdCruz': '+1 se o MACD cruzou para cima do sinal nos últimos 3 pregões, -1 se cruzou para baixo, 0 sem cruzamento; indicador não testado como regra; contexto',
                    'tec.mm21/mm50': 'distância do preço para a média de 21 e de 50 pregões (fração); mm200 fica fora de tec; indicador não testado como regra; contexto',
                    'tec.bbPct/bbLarg': 'Bollinger 20,2: %B = posição do preço entre a banda inferior (0) e a superior (1), pode sair de 0–1; bbLarg = (superior − inferior) ÷ média; indicador não testado como regra; contexto',
                    'tec.atr/atrPct': 'ATR de Wilder de 14 pregões, na moeda do papel, e em fração do preço; indicador não testado como regra; contexto',
                    'tec.sup/res': 'mínima e máxima dos últimos 20 pregões (suporte e resistência simples), na moeda do papel; indicador não testado como regra; contexto',
                    'situacoes': 'papéis hoje ≥30% abaixo da máxima de 60 pregões; historico = vezes anteriores do MESMO papel: [data, ret20, excesso20 sobre o índice, ret60, excesso60]; saltoSuspeito = queda ≥45% num pregão além da queda do índice no dia (confirmar se é evento real ou erro de ajuste); contexto, não sinal'},
    }


def compactar(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    site = argv[1]
    obj = montar(site, cotahist=argv[2] if len(argv) > 2 else None)
    txt = compactar(obj)
    # se passar do limite (200 KB), corta a lista de papéis dos EUA (o Ibovespa fica inteiro)
    us = obj['mercados'].get('us')
    while len(txt.encode()) > LIMITE_BYTES and us and len(us['papeis']) > 10:
        nomes = sorted(us['papeis'], key=lambda t: -(us['papeis'][t].get('volFinMi') or 0))
        us['papeis'] = {t: us['papeis'][t] for t in sorted(nomes[:int(len(nomes) * 0.8)])}
        txt = compactar(obj)
    os.makedirs(os.path.join(site, 'data'), exist_ok=True)
    with open(os.path.join(site, 'data', 'agente.json'), 'w', encoding='utf-8') as f:
        f.write(txt)
    s = obj['saude']
    print(f"agente.json: {len(txt.encode()) / 1024:.1f} KB · mercados {', '.join(obj['mercados']) or 'nenhum'}"
          f" · {s['diasUteisDesdeUltimoPregao']} dias úteis desde o último pregão"
          f"{' · DADOS VELHOS' if s['dadosVelhos'] else ''}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
