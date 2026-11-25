"""Teste da hipótese C-BR: carteira de ações por lucro/preço e dividendos no Brasil.

Segue o registro em docs/hipotese-fundamentos-brasil.md (escrito antes de rodar). Só leitura; não muda o app.
Baixa balanços da CVM (ITR/DFP 2010 em diante), preços do Yahoo (.SA) e o CDI do Banco Central.
Uso: python coleta/testar_fundamentos_br.py [--saida fundamentos_br.json]
"""
import argparse
import io
import warnings
import json
import os
import random
import sys
import zipfile
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import balancos_cvm as cvm            # noqa: E402
import testar_fundamentos as tf       # noqa: E402

N_CART, PRECO_MIN, LIQ_MIN, MIN_ELEG = 15, 1.0, 5e6, 30
MCAP_ESCALA = 1e9      # valor de mercado abaixo de R$ 1 bi = quantidade de ações em milhares na CVM
MESES_REB, MESES_SEM = (3, 6, 9, 12), (3, 9)
SORTEIOS = int(os.environ.get('SORTEIOS_C', 200))
CUSTO = tf.CUSTO
ANO_INI = 2010
INDICE = 'BOVA11'
URL_CDI = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial={ini}&dataFinal={fim}'


# ---------- universo ----------
def universo(caminho=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ibovespa_reserva.txt')):
    """Códigos da reserva do IBOVESPA, sem units (terminados em 11)."""
    tickers = []
    for linha in open(caminho, encoding='utf-8'):
        tickers += [t.strip().upper() for t in linha.split('#', 1)[0].split() if t.strip()]
    return [t for t in dict.fromkeys(tickers) if not t.endswith('11')]


# ---------- balanços da CVM ----------
class AcumuladorBR(cvm.Acumulador):
    """Acrescenta ao acumulador do app a composição do capital (ações totais menos tesouraria)."""

    def __init__(self, cnpjs):
        super().__init__(cnpjs)
        self.acoes = {}    # (cnpj, dt_refer, tipo) -> (versao, quantidade)
        self.colunas_capital = None

    def ler_zip(self, conteudo, tipo, ano):
        super().ler_zip(conteudo, tipo, ano)
        z = zipfile.ZipFile(io.BytesIO(conteudo))
        nome = next((n for n in z.namelist() if 'composicao_capital' in n.lower()), None)
        for r in cvm.linhas(z, nome, self.cnpjs) if nome else []:
            if self.colunas_capital is None:
                self.colunas_capital = list(r)
            if r.get('CNPJ_CIA') not in self.cnpjs:
                continue
            q = _num(r.get('QT_ACAO_TOTAL_CAP_INTEGR'))
            if not q:
                q = (_num(r.get('QT_ACAO_ORDIN_CAP_INTEGR')) or 0) + (_num(r.get('QT_ACAO_PREF_CAP_INTEGR')) or 0)
            tes = _num(r.get('QT_ACAO_TOTAL_TESOURO'))
            if tes is None:
                tes = (_num(r.get('QT_ACAO_ORDIN_TESOURO')) or 0) + (_num(r.get('QT_ACAO_PREF_TESOURO')) or 0)
            if not q:
                continue
            k = (r['CNPJ_CIA'], r['DT_REFER'], tipo)
            ver = int(r.get('VERSAO') or 0)
            if k not in self.acoes or ver >= self.acoes[k][0]:
                self.acoes[k] = (ver, q - (tes or 0))

    def empresa_br(self, cnpj):
        """{'trim': [{end, filed, ni}], 'bal': [{end, filed, ativo, pl}], 'acoes': [{end, filed, v}]}"""
        t, b = self.empresa(cnpj)
        receb = {}
        for (c, ref, tipo), d in self.receb.items():
            if c == cnpj:
                receb[ref] = min(receb.get(ref, d), d)
        trim = [{'end': x[0], 'filed': x[1], 'ni': x[3]} for x in t if x[3] is not None]
        bal = [{'end': x[0], 'filed': receb[x[0]], 'ativo': x[1], 'pl': x[2]} for x in b if x[0] in receb]
        ac = {}
        for (c, ref, tipo), (_, q) in self.acoes.items():
            if c == cnpj and ref in receb and q > 0:
                ac[ref] = q
        acoes = [{'end': ref, 'filed': receb[ref], 'v': q} for ref, q in sorted(ac.items())]
        return {'trim': trim, 'bal': bal, 'acoes': acoes}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def balancos(tickers, baixar=cvm.baixar, hoje=None, fre=False):
    hoje = hoje or date.today()
    fca = baixar(f'{cvm.BASE}/FCA/DADOS/fca_cia_aberta_{hoje.year}.zip') or \
        baixar(f'{cvm.BASE}/FCA/DADOS/fca_cia_aberta_{hoje.year - 1}.zip')
    if not fca:
        raise RuntimeError('FCA da CVM indisponível')
    mapa = cvm.mapa_tickers(fca, set(tickers))
    acc = AcumuladorBR(set(mapa.values()))
    for ano in range(ANO_INI, hoje.year + 1):
        for tipo in ('ITR', 'DFP'):
            c = baixar(f'{cvm.BASE}/{tipo}/DADOS/{tipo.lower()}_cia_aberta_{ano}.zip')
            if c:
                acc.ler_zip(c, tipo, ano)
                print(f'  {tipo} {ano}: ok', flush=True)
    print(f'colunas da composição do capital: {acc.colunas_capital}', flush=True)
    B = {t: acc.empresa_br(c) for t, c in mapa.items()}
    if fre:   # confirmação: ações do FRE antes de 2020, onde os ITR/DFP não têm a composição do capital
        extra = {}
        for ano in range(ANO_INI, 2021):
            c = baixar(f'{cvm.BASE}/FRE/DADOS/fre_cia_aberta_{ano}.zip')
            if c:
                for cnpj, lst in acoes_fre(c, ano, set(mapa.values())).items():
                    extra.setdefault(cnpj, []).extend(lst)
                print(f'  FRE {ano}: ok', flush=True)
        for t, cnpj in mapa.items():
            prim = min((x['filed'] for x in B[t]['acoes']), default='9999')
            B[t]['acoes'] = sorted([x for x in extra.get(cnpj, []) if x['filed'] < prim] + B[t]['acoes'],
                                   key=lambda x: x['filed'])
        print(f"  FRE: ações antes de 2020 para {sum(1 for c in mapa.values() if extra.get(c))} de {len(mapa)} empresas",
              flush=True)
    return B, mapa


def _coluna(cab, *partes):
    """Primeira coluna cujo nome contém todas as partes (sem diferença de maiúsculas)."""
    for c in cab:
        if all(x.lower() in c.lower() for x in partes):
            return c
    return None


def acoes_fre(conteudo, ano, cnpjs):
    """Quantidade total de ações pelo capital social do Formulário de Referência (confirmação de 2012–2020).
    Devolve {cnpj: [{'end', 'filed', 'v'}]}; integralizado, ou emitido se não houver; a última versão."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = z.namelist()
    idx = next((n for n in nomes if n.lower() == f'fre_cia_aberta_{ano}.csv'), None)
    cap = next((n for n in nomes if 'capital_social' in n.lower() and 'classe' not in n.lower()), None)
    receb, receb_ver = {}, {}   # (cnpj, ref) -> (versão, data) da mais recente; (cnpj, ref, versão) -> data
    for r in cvm.linhas(z, idx) if idx else []:
        c, ref, dt = r.get('CNPJ_CIA'), r.get('DT_REFER'), r.get('DT_RECEB')
        if c in cnpjs and ref and dt:
            ver = int(_num(r.get('VERSAO')) or 0)
            receb_ver[(c, ref, ver)] = min(receb_ver.get((c, ref, ver), dt), dt)
            if (c, ref) not in receb or (ver, dt) > receb[(c, ref)]:
                receb[(c, ref)] = (ver, dt)
    out, melhor = {}, {}
    cab = None
    for r in cvm.linhas(z, cap) if cap else []:
        if cab is None:
            cab = list(r)
            print(f'  FRE {ano}: colunas do capital social {cab}', flush=True)
            col = {'cnpj': _coluna(cab, 'cnpj'), 'ref': _coluna(cab, 'data_refer') or _coluna(cab, 'dt_refer'),
                   'ver': _coluna(cab, 'versao'), 'tipo': _coluna(cab, 'tipo_capital'),
                   'qt': _coluna(cab, 'quantidade_total') or _coluna(cab, 'qtd_total') or _coluna(cab, 'total_acoes')}
        c = r.get(col['cnpj'])
        if c not in cnpjs or not col['qt']:
            continue
        tipo = (r.get(col['tipo']) or '').lower()
        prio = 2 if 'integraliz' in tipo else 1 if 'emitid' in tipo else 0
        q = _num(r.get(col['qt']))
        if not prio or not q:
            continue
        ref = r.get(col['ref']) or f'{ano}-01-01'
        ver = int(_num(r.get(col['ver'])) or 0)
        k = (c, ref)
        if k not in melhor or (prio, ver) >= melhor[k][0]:
            melhor[k] = ((prio, ver), q)
    for (c, ref), ((_, ver), q) in melhor.items():
        # data de entrega da versão usada (correção de 07/11/2026: antes era a da primeira entrega)
        filed = receb_ver.get((c, ref, ver)) or (receb.get((c, ref)) or (None, None))[1] or f'{ano}-06-30'
        out.setdefault(c, []).append({'end': ref, 'filed': filed, 'v': q})
    return out


# ---------- preços ----------
def precos_yahoo(tickers, inicio=f'{ANO_INI}-01-01', tentativas=3):
    """Baixa em lote e tenta de novo, um a um, os que falharem (o Yahoo às vezes falha por acaso)."""
    out = _precos_yahoo(tickers, inicio)
    for _ in range(tentativas):
        faltam = [t for t in tickers if t not in out]
        if not faltam:
            break
        for t in faltam:
            out.update(_precos_yahoo([t], inicio, threads=False))
    print(f'sem preço no Yahoo: {sorted(set(tickers) - set(out))}', flush=True)
    return out


def _precos_yahoo(tickers, inicio, threads=True):
    import yfinance as yf
    out = {}
    df = yf.download([t + '.SA' for t in tickers], start=inicio, auto_adjust=False, actions=True,
                     group_by='ticker', threads=threads, progress=False)
    for t in tickers:
        try:
            d = df[t + '.SA'].dropna(subset=['Close', 'Adj Close'])
        except (KeyError, TypeError):
            continue
        if len(d) < 250:
            continue
        sp = d['Stock Splits'] if 'Stock Splits' in d else None
        out[t] = {'dates': [x.strftime('%Y-%m-%d') for x in d.index], 'adj': [float(x) for x in d['Adj Close']],
                  'close': [float(x) for x in d['Close']], 'vol': [float(x) for x in d['Volume']],
                  'splits': [[i.strftime('%Y-%m-%d'), float(r)] for i, r in sp.items() if r and r > 0]
                  if sp is not None else []}
    return out


def cdi_diario(ini, fim):
    import requests
    out, a = {}, ini
    while a <= fim:
        b = min(fim, a + timedelta(days=365 * 9))
        r = requests.get(URL_CDI.format(ini=a.strftime('%d/%m/%Y'), fim=b.strftime('%d/%m/%Y')), timeout=120)
        r.raise_for_status()
        for x in r.json():
            dd, mm, aa = x['data'].split('/')
            out[f'{aa}-{mm}-{dd}'] = float(x['valor']) / 100      # taxa ao dia
        a = b + timedelta(days=1)
    return out


# ---------- fundamentos sem olhar o futuro ----------
def fundamentos_br(b, dia, fator_split):
    trim = sorted(tf.disponivel(b['trim'], dia), key=lambda x: x['end'])
    if len(trim) < 4:
        return None
    u = trim[-4:]
    for x, y in zip(u, u[1:]):
        if not (80 <= (date.fromisoformat(y['end']) - date.fromisoformat(x['end'])).days <= 100):
            return None
    if (date.fromisoformat(dia) - date.fromisoformat(u[-1]['end'])).days > 200:
        return None
    bal = [x for x in sorted(tf.disponivel(b['bal'], dia), key=lambda x: x['end']) if x.get('pl') is not None]
    ac = sorted(tf.disponivel(b['acoes'], dia), key=lambda x: x['end'])
    if not bal or not ac:
        return None
    return {'ni': sum(x['ni'] for x in u), 'pl': bal[-1]['pl'], 'acoes': ac[-1]['v'] * fator_split(ac[-1]['end'])}


def dy_12m(P, t, i):
    """Dividendos dos 12 meses ÷ preço, pela razão ajustado/não ajustado (só muda com proventos)."""
    j = i - 252
    if j < 0:
        return np.nan
    a0, c0, a1, c1 = P.adj[t][j], P.close[t][j], P.adj[t][i], P.close[t][i]
    if not (a0 == a0 and c0 == c0 and a1 == a1 and c1 == c1) or min(a0, c0, a1, c1) <= 0:
        return np.nan
    return max(0.0, 1 - (a0 / c0) / (a1 / c1))


def elegiveis(P, B, empresa, i, excluidos=None):
    dia = P.cal[i]
    melhor = {}
    for t in B:
        if t not in P.adj or P.adj[t][i] != P.adj[t][i] or P.preco_real(t, i) < PRECO_MIN:
            continue
        a = P.adtv(t, i)
        if a == a and a >= LIQ_MIN and (empresa[t] not in melhor or a > melhor[empresa[t]][0]):
            melhor[empresa[t]] = (a, t)
    out = []
    for _, t in melhor.values():
        f = fundamentos_br(B[t], dia, lambda fim, t=t: P.fator(t, fim))
        if not f or f['pl'] <= 0 or f['ni'] <= 0 or f['acoes'] <= 0:
            continue
        mcap = P.close[t][i] * f['acoes']
        if mcap < MCAP_ESCALA:         # composição do capital informada em milhares (correção de 06/11, ver registro)
            mcap *= 1000
            if excluidos is not None:
                excluidos.append((dia, t, 'ações em milhares'))
        pl_ratio = mcap / f['ni']
        if not (1 <= pl_ratio <= 100):
            if excluidos is not None and pl_ratio < 1:
                excluidos.append((dia, t, round(float(pl_ratio), 3)))
            continue
        dy = dy_12m(P, t, i)
        out.append({'t': t, 'valor': f['ni'] / mcap, 'dividendos': 0.0 if dy != dy else dy, 'pl': round(pl_ratio, 1)})
    if not out:
        return out
    for k in ('valor', 'dividendos'):
        ordem = sorted(range(len(out)), key=lambda j: out[j][k])
        for r, j in enumerate(ordem):
            out[j]['p_' + k] = r / max(1, len(out) - 1)
    for x in out:
        x['nota'] = (x['p_valor'] + x['p_dividendos']) / 2
    return out


def cdi_periodo(cdi, cal, i, i2):
    v = 1.0
    for d in cal[i + 1:i2 + 1]:
        v *= 1 + cdi.get(d, 0.0)
    return v - 1


def hipotese(P, B, empresa, cdi, fim=None, min_trimestres=None):
    excl = []
    reb = tf.datas_reb(P.cal, MESES_REB)
    if fim:   # confirmação: só carteiras mantidas até `fim` (a última termina no 1º pregão depois de `fim`)
        corte = next((i for i in range(len(P.cal)) if P.cal[i] >= fim), len(P.cal) - 1)
        reb = [i for i in reb if i < corte] + [corte]
    periodos = []
    for i, i2 in zip(reb, reb[1:]):
        e = elegiveis(P, B, empresa, i, excl)
        if len(e) >= MIN_ELEG:
            periodos.append({'i': i, 'i2': i2, 'e': e})
    if not periodos:
        return None
    topo = lambda n, k='nota': (lambda p: [x['t'] for x in sorted(p['e'], key=lambda x: -x[k])[:n]])
    principal = tf.rodar(P, periodos, topo(N_CART))
    todos = tf.rodar(P, periodos, lambda p: [x['t'] for x in p['e']])
    ind = [P.adj[INDICE][p['i2']] / P.adj[INDICE][p['i']] - 1 for p in periodos]
    cdi_r = [cdi_periodo(cdi, P.cal, p['i'], p['i2']) for p in periodos]
    rng = random.Random(7)
    acaso = [tf.metricas(tf.rodar(P, periodos, lambda p: rng.sample([x['t'] for x in p['e']], N_CART)))['retorno']
             for _ in range(SORTEIOS)]
    reb_s = tf.datas_reb(P.cal, MESES_SEM)
    per_s = [{'i': i, 'i2': i2, 'e': elegiveis(P, B, empresa, i)} for i, i2 in zip(reb_s, reb_s[1:])
             if i >= periodos[0]['i'] and i2 <= periodos[-1]['i2']]
    per_s = [p for p in per_s if len(p['e']) >= MIN_ELEG]
    meio = len(periodos) // 2
    R = {
        'de': P.cal[periodos[0]['i']], 'ate': P.cal[periodos[-1]['i2']], 'trimestres': len(periodos),
        'elegiveisMedio': round(float(np.mean([len(p['e']) for p in periodos]))),
        'principal': tf.metricas(principal), 'indice': tf.metricas(ind), 'cdi': tf.metricas(cdi_r),
        'pesosIguais': tf.metricas(todos),
        'acaso': {'p5': round(float(np.percentile(acaso, 5)), 1), 'mediana': round(float(np.median(acaso)), 1),
                  'p95': round(float(np.percentile(acaso, 95)), 1)},
        'percentilAcaso': round(float(np.mean([x < tf.metricas(principal)['retorno'] for x in acaso])) * 100),
        'metades': [{'de': P.cal[ps[0]['i']], 'ate': P.cal[ps[-1]['i2']], 'carteira': tf.metricas(principal[a:b]),
                     'pesosIguais': tf.metricas(todos[a:b]), 'indice': tf.metricas(ind[a:b]),
                     'cdi': tf.metricas(cdi_r[a:b])}
                    for a, b, ps in ((0, meio, periodos[:meio]), (meio, len(periodos), periodos[meio:]))],
        'robustez': {
            'só valor': tf.metricas(tf.rodar(P, periodos, topo(N_CART, 'valor'))),
            'só dividendos': tf.metricas(tf.rodar(P, periodos, topo(N_CART, 'dividendos'))),
            '10 papéis': tf.metricas(tf.rodar(P, periodos, topo(10))),
            '20 papéis': tf.metricas(tf.rodar(P, periodos, topo(20))),
            'custo × 2': tf.metricas(tf.rodar(P, periodos, topo(N_CART), CUSTO * 2)),
            'semestral': tf.metricas_p(tf.rodar(P, per_s, topo(N_CART)), 2) if per_s else None,
        },
        'porAno': {},
        'excluidosPL': {'quantidade': sum(1 for x in excl if x[2] != 'ações em milhares'),
                        'exemplos': [x for x in excl if x[2] != 'ações em milhares'][:15]},
        'corrigidosMilhares': {'quantidade': sum(1 for x in excl if x[2] == 'ações em milhares'),
                               'papeis': sorted({x[1] for x in excl if x[2] == 'ações em milhares'})},
        'exemplosCarteira': [{'data': P.cal[p['i']], 'carteira': [(x['t'], float(x['pl']), round(float(x['dividendos']) * 100, 1))
                                                                 for x in sorted(p['e'], key=lambda x: -x['nota'])[:N_CART]]}
                             for p in (periodos[0], periodos[len(periodos) // 2], periodos[-1])],
        'carteiraAtual': topo(N_CART)({'e': elegiveis(P, B, empresa, len(P.cal) - 1)}),
    }
    for p, a, b, c in zip(periodos, principal, ind, cdi_r):
        ano = P.cal[p['i2']][:4]
        x = R['porAno'].setdefault(ano, [1.0, 1.0, 1.0])
        x[0] *= 1 + a
        x[1] *= 1 + b
        x[2] *= 1 + c
    R['porAno'] = {k: [round((v - 1) * 100, 1) for v in x] for k, x in R['porAno'].items()}
    c1 = R['principal']['retorno'] > R['acaso']['p95']
    c2 = R['principal']['anual'] > R['indice']['anual'] and R['principal']['quedaMax'] <= 1.5 * R['indice']['quedaMax']
    c3 = all(h['carteira']['retorno'] > h['pesosIguais']['retorno'] for h in R['metades'])
    c4 = R['robustez']['custo × 2']['anual'] > R['indice']['anual']
    c5 = R['principal']['retorno'] > R['cdi']['retorno']
    R['criterios'] = {'acima do p95 do acaso': c1, 'vence o BOVA11 com queda até 1,5×': c2,
                      'vence os pesos iguais nas duas metades': c3, 'com custo × 2 vence o BOVA11': c4,
                      'acima do CDI': c5}
    R['aprovada'] = all(R['criterios'].values())
    if min_trimestres is not None:
        R['trimestresMinimo'] = min_trimestres
        R['inconclusivo'] = len(periodos) < min_trimestres
        if R['inconclusivo']:
            R['aprovada'] = False
    return R


def markdown(R):
    lin = lambda nome, m: (f"| {nome} | {m['retorno']}% | {m['anual']}% | {m['quedaMax']}% | {m['sharpe']} |"
                           if m else f'| {nome} | – | – | – | – |')
    L = [f"## Hipótese C-BR: lucro/preço e dividendos, Brasil, {R['de']} a {R['ate']} "
         f"({R['trimestres']} trimestres, ~{R['elegiveisMedio']} elegíveis)", '',
         '| Carteira | Retorno | Ao ano | Queda máx. | Sharpe |', '| --- | --- | --- | --- | --- |',
         lin(f'lucro/preço + dividendos ({N_CART} papéis)', R['principal']), lin('BOVA11', R['indice']),
         lin('CDI', R['cdi']), lin('pesos iguais, todos os elegíveis', R['pesosIguais']),
         f"| acaso ({SORTEIOS} carteiras) | p5 {R['acaso']['p5']}% · mediana {R['acaso']['mediana']}% · "
         f"p95 {R['acaso']['p95']}% | | | |",
         *[lin('robustez: ' + k, m) for k, m in R['robustez'].items()], '',
         f"Percentil da carteira entre as sorteadas: {R['percentilAcaso']}", '',
         'Metades: ' + ' · '.join(f"{h['de']} a {h['ate']}: carteira {h['carteira']['retorno']}%, pesos iguais "
                                  f"{h['pesosIguais']['retorno']}%, BOVA11 {h['indice']['retorno']}%, CDI "
                                  f"{h['cdi']['retorno']}%" for h in R['metades']), '',
         '| Ano | Carteira | BOVA11 | CDI |', '| --- | --- | --- | --- |',
         *[f'| {a} | {v[0]}% | {v[1]}% | {v[2]}% |' for a, v in sorted(R['porAno'].items())], '',
         f"Excluídos por P/L < 1 (erro de escala): {R['excluidosPL']['quantidade']}; exemplos {R['excluidosPL']['exemplos']}",
         f"Ações informadas em milhares, corrigidas: {R['corrigidosMilhares']['quantidade']} datas, papéis "
         f"{R['corrigidosMilhares']['papeis']}",
         '', 'Carteiras de exemplo (papel, P/L, dividendos 12m %):',
         *[f"- {x['data']}: {x['carteira']}" for x in R['exemplosCarteira']],
         f"- hoje: {R['carteiraAtual']}", '']
    for k, v in R['criterios'].items():
        L.append(f'- {"OK" if v else "FALHOU"}: {k}')
    v = 'INCONCLUSIVO' if R.get('inconclusivo') else 'APROVADA' if R['aprovada'] else 'REPROVADA'
    if R.get('trimestresMinimo'):
        L.append(f"- {'OK' if not R['inconclusivo'] else 'FALHOU'}: pelo menos {R['trimestresMinimo']} trimestres "
                 f"({R['trimestres']})")
    L += ['', f"**Veredito: {v}**", '']
    return '\n'.join(L)


def diagnostico(P, B, empresa):
    """Quantos papéis passam em cada etapa no fim de junho de cada ano (para entender a cobertura dos dados)."""
    for i in tf.datas_reb(P.cal, (6,)):
        dia = P.cal[i]
        n = {'preço': 0, 'liquidez': 0, 'trimestres': 0, 'ações': 0, 'lucro>0': 0}
        for t, b in B.items():
            if t not in P.adj or P.adj[t][i] != P.adj[t][i]:
                continue
            n['preço'] += 1
            a = P.adtv(t, i)
            if not (a == a and a >= LIQ_MIN):
                continue
            n['liquidez'] += 1
            if len(tf.disponivel(b['trim'], dia)) >= 4:
                n['trimestres'] += 1
            if tf.disponivel(b['acoes'], dia):
                n['ações'] += 1
            f = fundamentos_br(b, dia, lambda fim, t=t: P.fator(t, fim))
            if f and f['ni'] > 0:
                n['lucro>0'] += 1
        print(f'  {dia}: {n}', flush=True)


def main(argv=None):
    warnings.filterwarnings('ignore')
    ap = argparse.ArgumentParser()
    ap.add_argument('--saida', default='fundamentos_br.json')
    ap.add_argument('--confirmacao', action='store_true', help='2012–2020 com as ações do FRE')
    a = ap.parse_args(argv)
    tick = universo()
    B, mapa = balancos(tick, fre=a.confirmacao)
    print(f'{len(B)} de {len(tick)} códigos com CNPJ na CVM; sem: {sorted(set(tick) - set(B))}', flush=True)
    bruto = precos_yahoo(sorted(B) + [INDICE])
    if INDICE not in bruto:
        print('BOVA11 sem preço no Yahoo: abortando')
        return 1
    cal = bruto[INDICE]['dates']
    P = tf.Precos(bruto, cal)
    B = {t: b for t, b in B.items() if t in P.adj}
    print(f'{len(B)} papéis com balanços e preços; calendário {cal[0]} a {cal[-1]}', flush=True)
    for t in ('PETR4', 'VALE3', 'ITUB4'):     # conferência à mão do valor de mercado e do P/L de hoje
        if t in B:
            f = fundamentos_br(B[t], cal[-1], lambda fim, t=t: P.fator(t, fim))
            if f:
                mc = P.close[t][-1] * f['acoes']
                mc = mc * 1000 if mc < MCAP_ESCALA else mc
                print(f"  {t}: ações {f['acoes']:.0f}, valor de mercado R$ {mc / 1e9:.1f} bi, lucro 12m "
                      f"R$ {f['ni'] / 1e9:.1f} bi, P/L {mc / f['ni']:.1f}, dividendos 12m "
                      f"{dy_12m(P, t, len(cal) - 1) * 100:.1f}%", flush=True)
    diagnostico(P, B, mapa)
    for t in ('PETR4', 'VALE3'):
        if t in B:
            print(f"  {t}: trimestres {[x['end'] for x in B[t]['trim']][:6]}..., ações {[x['end'] for x in B[t]['acoes']][:6]}...")
    cdi = cdi_diario(date.fromisoformat(cal[0]), date.fromisoformat(cal[-1]))
    R = hipotese(P, B, mapa, cdi, fim='2020-06-30', min_trimestres=24) if a.confirmacao else hipotese(P, B, mapa, cdi)
    if not R:
        print('nenhuma data com elegíveis suficientes')
        return 1
    R['registro'] = ('docs/hipotese-fundamentos-brasil-confirmacao.md' if a.confirmacao
                     else 'docs/hipotese-fundamentos-brasil.md')
    json.dump(R, open(a.saida, 'w'), indent=1, ensure_ascii=False,
              default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    texto = markdown(R)
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write(texto + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
