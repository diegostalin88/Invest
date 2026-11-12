"""Gera data/agente.json: o resumo diário que o agente analista (skill `analista-invest`) lê.

Junta, em menos de 100 KB, o que hoje está espalhado em dezenas de MB: saúde da coleta, termômetro do
índice, amplitude, CDI/IPCA/PTAX do Banco Central, listas do dia, vendidos, calendário de balanços, um
resumo por papel (Ibovespa inteiro, os EUA mais negociados e a watchlist) e o placar do teste para frente
da estratégia congelada.

Só descreve. Nada aqui é sinal de compra ou venda; o agente também não pode tratar como tal.

Uso: python coleta/agente.py PASTA_DO_SITE
  lê PASTA/data/carteira.json e PASTA/antigo/data/ (EUA) e PASTA/antigo/data/br/ (Brasil), quando existem;
  grava PASTA/data/agente.json.
"""
import glob
import json
import math
import os
import sys
from datetime import date, datetime, timezone

VERSAO = 1
LIMITE_BYTES = 100 * 1024
N_LISTA = 10
N_PAPEIS_EUA = 60
DIAS_BALANCO = 14
BASE_CARTEIRA = {'BOVA11', 'IVVB11', 'BTC'}
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
        else:
            saida.update(obj)
    return saida


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


def resumo_papel(s, fund=None, vend=None):
    c = [x for x in s['close'] if x]
    if len(c) < 2:
        return None
    vol = s.get('volume') or []
    pares = [(x, y) for x, y in zip(s['close'][-20:], vol[-20:]) if x and y]
    o = {'p': r(c[-1], 2), 'd1': r(ret(c, 1)), 'm1': r(ret(c, 21)), 'a1': r(ret(c, 252)),
         'mm200': r(dist_mm(c, 200)), 'topo52': r(queda_topo(c)), 'vol': r(vol_anual(c), 3),
         'volFinMi': r(sum(x * y for x, y in pares) / len(pares) / 1e6, 1) if pares else None}
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
    if vend:
        o['vendido'] = {k: vend[k] for k in ('dias', 'variacaoPct', 'diasFinra') if vend.get(k) is not None} or None
    return {k: v for k, v in o.items() if v is not None}


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


def mercado(pasta, nome, hoje, n_papeis=None, extras=()):
    m = ler_json(os.path.join(pasta, 'manifest.json'))
    if not m:
        return None
    precos = ler_precos(pasta)
    fund = ler_json(os.path.join(pasta, m.get('arquivoFundamentos') or 'fundamentos.json')) or {}
    vend_arq = ler_json(os.path.join(pasta, m.get('arquivoVendidos') or 'vendidos.json')) or {}
    indice = ler_json(os.path.join(pasta, m.get('arquivoIndice') or 'indice.json'))
    diario = ler_json(os.path.join(pasta, 'diario.json'))

    # dias de vendidos: quantidade vendida ÷ volume médio de 20 dias (o FINRA já manda o dele)
    vend = {}
    for t, a in (vend_arq.get('ativos') or {}).items():
        s = precos.get(t)
        vm = media([v for v in (s or {}).get('volume', [])[-20:] if v]) if s else None
        dias = a.get('diasFinra') if a.get('diasFinra') is not None else (a['qtd'] / vm if vm and a.get('qtd') else None)
        vend[t] = {'dias': r(dias, 1), 'variacaoPct': a.get('variacaoPct'), 'qtd': a.get('qtd')}

    resumos = {t: resumo_papel(s, fund.get(t), vend.get(t)) for t, s in precos.items()}
    resumos = {t: v for t, v in resumos.items() if v}
    com = lambda k: [(t, v[k]) for t, v in resumos.items() if v.get(k) is not None]  # noqa: E731

    def top(k, rev=True, n=N_LISTA):
        return [[t, x] for t, x in sorted(com(k), key=lambda kv: (-kv[1] if rev else kv[1], kv[0]))[:n]]
    listas = {'altas': top('d1'), 'quedas': top('d1', False), 'maisNegociados': top('volFinMi'),
              'longeDoTopo': top('topo52'), 'maisVolateis': top('vol')}
    vendidos = sorted(([t, v['dias'], v.get('variacaoPct')] for t, v in vend.items() if v.get('dias') is not None),
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
        'saude': {'geradoEm': m.get('geradoEm'), 'ultimoPregao': ult, 'papeis': len(resumos),
                  'avisos': m.get('avisos') or [], 'fundamentos': len(fund),
                  'vendidos': {'fonte': vend_arq.get('fonte'), 'data': vend_arq.get('data')} if vend_arq else None},
        'termometro': termometro(indice),
        'amplitude': {'acimaMM200': r(sum(acima) / len(acima), 3), 'papeis': len(acima)} if acima else None,
        'listas': listas, 'vendidos': vendidos, 'balancosProximos': balancos[:30],
        'testeParaFrente': placar_diario(diario, indice),
        'papeis': {t: resumos[t] for t in sorted(escolhidos)},
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
        o = resumo_papel({'close': serie, 'volume': []}) or {}
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


def dias_uteis(de, ate):
    if not de:
        return None
    d0 = date.fromisoformat(de)
    return sum(1 for k in range(1, (ate - d0).days + 1) if date.fromordinal(d0.toordinal() + k).weekday() < 5)


def montar(site, hoje=None):
    hoje = hoje or datetime.now(timezone.utc).date()
    cart = ler_json(os.path.join(site, 'data', 'carteira.json'))
    macro, ref, watch = carteira_resumo(cart)
    base = os.path.join(site, 'antigo', 'data')
    us = mercado(base, 'us', hoje, n_papeis=N_PAPEIS_EUA, extras=watch or ()) if os.path.isdir(base) else None
    br = mercado(os.path.join(base, 'br'), 'br', hoje, extras=watch or ()) if os.path.isdir(os.path.join(base, 'br')) else None
    ultimos = [m['saude']['ultimoPregao'] for m in (us, br) if m and m['saude'].get('ultimoPregao')]
    atraso = dias_uteis(min(ultimos), hoje) if ultimos else None
    return {
        'versao': VERSAO, 'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'aviso': AVISO,
        'saude': {'carteira': {'geradoEm': (cart or {}).get('geradoEm'), 'falhas': (cart or {}).get('falhas')} if cart else None,
                  'diasUteisDesdeUltimoPregao': atraso,
                  'dadosVelhos': atraso is None or atraso > 3,
                  'mercadosAusentes': [n for n, m in (('us', us), ('br', br)) if not m]},
        'macro': macro, 'referencias': ref, 'watchlist': watch,
        'mercados': {k: v for k, v in (('br', br), ('us', us)) if v},
        'legenda': {'d1/m1/a1': 'retorno de 1 pregão, 21 pregões e 252 pregões (fração: 0.05 = 5%)',
                    'mm200': 'distância do preço para a média de 200 pregões', 'topo52': 'queda desde a máxima de 52 semanas',
                    'vol': 'volatilidade anualizada de 21 pregões', 'volFinMi': 'volume financeiro médio de 20 pregões, milhões na moeda do mercado',
                    'vendido.dias': 'dias de volume para zerar a posição vendida (aluguel B3 ou short interest FINRA)',
                    'ref13': '1/3 BOVA11 + 1/3 IVVB11 + 1/3 CDI', 'testeParaFrente': 'placar da estratégia congelada (regras de 04/11/2026)'},
    }


def compactar(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    site = argv[1]
    obj = montar(site)
    txt = compactar(obj)
    # se passar do limite, corta a lista de papéis dos EUA (o Ibovespa fica inteiro)
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
