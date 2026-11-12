"""Dados do app de carteira (07/11/2026): só o que a carteira usa, em segundos.

Grava `carteira.json` com:
  - ativos: fechamento diário (sem ajuste de proventos, com ajuste de desdobramento) e os desdobramentos,
    para valorizar a carteira pelo preço real de mercado. BOVA11, IVVB11 e BTC (em reais = BTC-USD × PTAX).
    Outros papéis da B3 entram pela variável CARTEIRA_EXTRAS (ex.: "SMAL11 HASH11 ITUB4").
  - papéis dos EUA (conta em dólar): qualquer código do Yahoo (Nasdaq, NYSE, NYSE Arca, Cboe...), sem sufixo.
    Vão com `fechUSD` (dólar) e `fech` (reais, × PTAX do dia). Lista padrão em PADRAO_EUA, mais CARTEIRA_EUA.
  - cdi: série acumulada (começa em 1) do CDI diário (Banco Central, SGS 12).
  - ipca: variação mensal (%) do IPCA (SGS 433), para a rentabilidade real.
  - ptax: dólar PTAX de venda (SGS 1), o último valor; ptaxSerie: a série diária (converte a conta EUA).

Uso: python coleta/carteira_dados.py site/data
"""
import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone

INICIO = '2015-01-01'
PADRAO = [('BOVA11', 'BOVA11.SA', 'BOVA11 (ETF do Ibovespa)', 'acoes_br'),
          ('IVVB11', 'IVVB11.SA', 'IVVB11 (ETF do S&P 500 em reais)', 'acoes_eua'),
          ('BTC', 'BTC-USD', 'Bitcoin (em reais)', 'cripto')]
# Papéis em dólar que o Diego tem ou acompanha (07/11/2026), mais as ações de base dos ETFs alavancados.
PADRAO_EUA = ['SLV', 'IONX', 'FXF', 'PLTR', 'QBTX', 'QPUX', 'QTUM', 'IONQ', 'QBTS']
# ETF alavancado → (ação de base ou None se for cesta, fator). Para o app mostrar o efeito do rebalanceamento diário.
ALAVANCADOS = {'IONX': ('IONQ', 2), 'QBTX': ('QBTS', 2), 'QPUX': (None, 2)}

# Comparação com o setor (pedido do Diego, 07/11/2026). O setor vem do Yahoo (campo "sector").
# EUA: o ETF setorial SPDR daquele setor. Computação quântica tem ETF próprio (QTUM).
SETORES_EUA = {'Technology': ('Tecnologia', 'XLK'), 'Financial Services': ('Financeiro', 'XLF'), 'Healthcare': ('Saúde', 'XLV'),
               'Consumer Cyclical': ('Consumo cíclico', 'XLY'), 'Consumer Defensive': ('Consumo básico', 'XLP'), 'Energy': ('Energia', 'XLE'),
               'Basic Materials': ('Materiais básicos', 'XLB'), 'Industrials': ('Indústria', 'XLI'), 'Utilities': ('Serviços públicos', 'XLU'),
               'Real Estate': ('Imobiliário', 'XLRE'), 'Communication Services': ('Comunicação', 'XLC')}
QUANTICOS = {'IONQ', 'QBTS', 'RGTI', 'QUBT', 'ARQQ', 'IONX', 'QBTX', 'QPUX'}
# B3: não há índice setorial confiável no Yahoo; o setor é uma cesta de empresas grandes do mesmo setor, peso igual.
# Códigos que não baixarem (mudança de código, fechamento de capital) ficam de fora da cesta sem quebrar a coleta.
SETORES_BR = {
    'Consumer Cyclical': ('Varejo e consumo cíclico', ['LREN3', 'MGLU3', 'BHIA3', 'CEAB3', 'AZZA3', 'VIVA3', 'ALPA4', 'GUAR3']),
    'Financial Services': ('Bancos e financeiras', ['ITUB4', 'BBDC4', 'BBAS3', 'SANB11', 'BPAC11', 'B3SA3']),
    'Energy': ('Petróleo e gás', ['PETR4', 'PRIO3', 'RECV3', 'BRAV3', 'UGPA3', 'VBBR3']),
    'Basic Materials': ('Mineração, siderurgia e papel', ['VALE3', 'SUZB3', 'GGBR4', 'CSNA3', 'USIM5', 'KLBN11', 'BRKM5']),
    'Utilities': ('Energia elétrica e saneamento', ['EQTL3', 'SBSP3', 'CMIG4', 'ENGI11', 'TAEE11', 'EGIE3', 'CPFE3']),
    'Industrials': ('Indústria e transporte', ['WEGE3', 'EMBJ3', 'EMBR3', 'RAIL3', 'MOTV3', 'RENT3', 'POMO4']),
    'Consumer Defensive': ('Alimentos, bebidas e consumo básico', ['ABEV3', 'ASAI3', 'CRFB3', 'MBRF3', 'SMTO3', 'NATU3']),
    'Healthcare': ('Saúde', ['RDOR3', 'HAPV3', 'RADL3', 'FLRY3', 'HYPE3', 'ODPV3']),
    'Real Estate': ('Construção e shoppings', ['CYRE3', 'MRVE3', 'EZTC3', 'DIRR3', 'CURY3', 'MULT3', 'ALOS3']),
    'Communication Services': ('Telecomunicações', ['VIVT3', 'TIMS3']),
    'Technology': ('Tecnologia', ['TOTS3', 'LWSA3', 'POSI3', 'INTB3']),
}


def http_json(url, params=None):
    import requests
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def bcb(serie, inicio=INICIO, pedir=http_json):
    """Série SGS do Banco Central como lista [(AAAA-MM-DD, valor)]. A API limita a 10 anos por pedido."""
    ini = date.fromisoformat(inicio)
    hoje = date.today()
    out = {}
    while ini <= hoje:
        fim = min(hoje, date(ini.year + 9, 12, 31))
        dados = pedir(f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados',
                      {'formato': 'json', 'dataInicial': ini.strftime('%d/%m/%Y'), 'dataFinal': fim.strftime('%d/%m/%Y')})
        for x in dados:
            d = datetime.strptime(x['data'], '%d/%m/%Y').strftime('%Y-%m-%d')
            out[d] = float(str(x['valor']).replace(',', '.'))
        ini = fim + timedelta(days=1)
    return sorted(out.items())


def yahoo(simbolo, inicio=INICIO):
    """(datas, fechamentos, desdobramentos). Fechamento sem ajuste de proventos (preço de tela), mas o Yahoo
    já corrige desdobramentos; por isso os desdobramentos vão junto, para o app corrigir as quantidades."""
    import yfinance as yf
    tk = yf.Ticker(simbolo)
    h = tk.history(start=inicio, auto_adjust=False, actions=True)
    if h is None or not len(h):
        return None
    datas = h.index.strftime('%Y-%m-%d').tolist()
    fech = [float(x) for x in h['Close']]
    desd = []
    if 'Stock Splits' in h:
        for d, v in zip(datas, h['Stock Splits']):
            if v and float(v) > 0 and float(v) != 1:
                desd.append([d, float(v)])
    return datas, fech, desd


def limpar(datas, fech):
    pares = [(d, round(c, 6)) for d, c in zip(datas, fech) if c is not None and math.isfinite(c) and c > 0]
    return [d for d, _ in pares], [c for _, c in pares]


def em_reais(datas, usd, ptax):
    """Converte uma série em dólar pela PTAX do mesmo dia (ou a última anterior: fim de semana e feriado)."""
    ptax = sorted(ptax)
    out_d, out_c, j, ult = [], [], 0, None
    for d, c in zip(datas, usd):
        while j < len(ptax) and ptax[j][0] <= d:
            ult = ptax[j][1]
            j += 1
        if ult:
            out_d.append(d)
            out_c.append(c * ult)
    return out_d, out_c


def acumular(linhas):
    """CDI em % ao dia → série acumulada que começa em 1 (o rendimento do dia d entra no fechamento de d)."""
    v, datas, acum = 1.0, [], []
    for d, taxa in linhas:
        v *= 1 + taxa / 100
        datas.append(d)
        acum.append(round(v, 10))
    return datas, acum


def nome_yahoo(simbolo):
    """(nome, tipo, setor) do Yahoo: tipo é EQUITY (ação) ou ETF (serve para o código da declaração); setor em inglês."""
    try:
        import yfinance as yf
        info = yf.Ticker(simbolo).get_info() or {}
        return info.get('longName') or info.get('shortName') or simbolo, info.get('quoteType') or '', info.get('sector') or ''
    except Exception:
        return simbolo, '', ''


def fundamentos_yahoo(simbolo):
    """Dados para a ficha Bazin/Graham (só informação): LPA e VPA dos últimos 12 meses, dívida/patrimônio,
    dividendos pagos por ano (por ação, já ajustados a desdobramentos) e lucro líquido anual."""
    try:
        import yfinance as yf
        tk = yf.Ticker(simbolo)
        info = tk.get_info() or {}
        div = {}
        try:
            for d, v in tk.dividends.items():
                div[str(d.year)] = div.get(str(d.year), 0.0) + float(v)
        except Exception:
            pass
        lucros = []
        try:
            st = tk.income_stmt
            if st is not None and 'Net Income' in st.index:
                for col, v in st.loc['Net Income'].items():
                    if v is not None and math.isfinite(float(v)):
                        lucros.append([str(col.year), float(v)])
        except Exception:
            pass
        num = lambda k: float(info[k]) if isinstance(info.get(k), (int, float)) and math.isfinite(float(info[k])) else None
        out = {'lpa': num('trailingEps'), 'vpa': num('bookValue'), 'dividaPL': num('debtToEquity'),
               'dividendosAno': {a: round(v, 6) for a, v in sorted(div.items())}, 'lucros': sorted(lucros),
               'data': date.today().isoformat()}
        return out if (out['lpa'] is not None or out['vpa'] is not None or div) else None
    except Exception as e:
        print(f'fundamentos {simbolo}: {e}', file=sys.stderr)
        return None


def eh_bdr(codigo):
    import re
    return bool(re.fullmatch(r'[A-Z0-9]{4}3[2-59]', codigo))


def _info(nomear, simbolo):
    r = tuple(nomear(simbolo)) + ('', '', '')
    return r[0], r[1], r[2]


def setor_de(codigo, setor_yahoo, eua):
    """{'nome', 'ref'} (EUA: um ETF) ou {'nome', 'pares'} (B3: cesta) ou None."""
    if eua:
        if codigo in QUANTICOS:
            return {'nome': 'Computação quântica', 'ref': 'QTUM'}
        if setor_yahoo in SETORES_EUA:
            nome, etf = SETORES_EUA[setor_yahoo]
            return {'nome': nome, 'ref': etf}
        return None
    if setor_yahoo in SETORES_BR:
        nome, pares = SETORES_BR[setor_yahoo]
        return {'nome': nome, 'pares': [p for p in pares if p != codigo]}
    return None


def montar(extras=(), eua=(), baixar_yahoo=yahoo, baixar_bcb=bcb, nomear=nome_yahoo, fundamentar=fundamentos_yahoo):
    ptax = baixar_bcb(1)
    ativos, falhas = {}, []
    vistos = {p[0] for p in PADRAO}
    lista = list(PADRAO) + [(t, t + '.SA', t, 'outros') for t in extras if t and t not in vistos]
    vistos |= set(extras)
    lista += [(t, t, None, 'exterior') for t in dict.fromkeys(list(PADRAO_EUA) + list(eua)) if t and t not in vistos]
    setores_yahoo, tipos_yahoo = {}, {}

    def baixar(codigo, simbolo, nome, classe, apoio=False):
        try:
            r = baixar_yahoo(simbolo)
        except Exception as e:  # um ativo que falha não derruba os outros
            print(f'falhou {simbolo}: {e}', file=sys.stderr)
            r = None
        if not r:
            (falhas_apoio if apoio else falhas).append(codigo)
            return
        datas, fech, desd = r
        datas, fech = limpar(datas, fech)
        extra = {'apoio': True} if apoio else {}
        if simbolo.endswith('-USD'):
            datas, fech = em_reais(datas, fech, ptax)
            desd = []
        elif classe == 'exterior':
            d_brl, f_brl = em_reais(datas, fech, ptax)
            usd = dict(zip(datas, fech))
            datas, fech = d_brl, f_brl
            extra.update({'moeda': 'USD', 'fechUSD': [round(usd[d], 4) for d in datas]})
            if codigo in ALAVANCADOS:
                base, fator = ALAVANCADOS[codigo]
                extra['alavancado'] = {'base': base, 'fator': fator}
            if nome is None and not apoio:
                nome, tipo, setor = _info(nomear, simbolo)
                if tipo:
                    extra['tipo'] = tipo
                setores_yahoo[codigo] = setor
                tipos_yahoo[codigo] = tipo
        elif classe == 'outros' and not apoio:
            _, tipos_yahoo[codigo], setores_yahoo[codigo] = _info(nomear, simbolo)
        if len(datas) < 20:
            (falhas_apoio if apoio else falhas).append(codigo)
            return
        ativos[codigo] = {'nome': nome or codigo, 'classe': classe, 'fonte': simbolo, 'datas': datas,
                          'fech': [round(c, 4) for c in fech], 'desdobramentos': desd, **extra}

    falhas_apoio = []
    for item in lista:
        baixar(*item)
    # setor de cada papel e o que for preciso baixar para compará-lo (ETF setorial ou cesta de pares)
    for codigo, a in list(ativos.items()):
        if a.get('apoio') or codigo in {p[0] for p in PADRAO}:
            continue
        eua = a.get('moeda') == 'USD'
        if not eua and eh_bdr(codigo):
            continue   # BDR: empresa de fora; a cesta de pares da B3 não serve de setor
        if eua and a.get('tipo') == 'ETF' and codigo not in QUANTICOS:
            continue   # fundo de prata, de moeda etc.: não tem setor
        st = setor_de(codigo, setores_yahoo.get(codigo, ''), eua)
        if not st:
            continue
        for ref in ([st['ref']] if 'ref' in st else st['pares']):
            if ref not in ativos and ref not in falhas_apoio and ref != codigo:
                baixar(ref, ref if eua else ref + '.SA', ref, 'exterior' if eua else 'outros', apoio=True)
        if 'pares' in st:
            st['pares'] = [p for p in st['pares'] if p in ativos]
            if not st['pares']:
                continue
        elif st['ref'] not in ativos:
            continue
        a['setor'] = st
    # ficha Bazin/Graham: só ações (não ETF, FII nem fundo)
    for codigo, a in ativos.items():
        if a.get('apoio') or tipos_yahoo.get(codigo) != 'EQUITY' or (a.get('moeda') != 'USD' and eh_bdr(codigo)):
            continue
        try:
            f = fundamentar(a['fonte'])
        except Exception as e:
            print(f'fundamentos {codigo}: {e}', file=sys.stderr)
            f = None
        if f:
            if setores_yahoo.get(codigo) == 'Financial Services':
                f['financeira'] = True
            a['fund'] = f
    cdi_d, cdi_v = acumular(baixar_bcb(12))
    ipca = baixar_bcb(433)
    return {
        'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'ativos': ativos,
        'falhas': falhas,
        'falhasApoio': falhas_apoio,
        'cdi': {'datas': cdi_d, 'acum': cdi_v},
        'ipca': {'meses': [d[:7] for d, _ in ipca], 'var': [v for _, v in ipca]},
        'ptax': {'data': ptax[-1][0], 'valor': ptax[-1][1]} if ptax else None,
        'ptaxSerie': {'datas': [d for d, _ in ptax], 'valor': [v for _, v in ptax]},
    }


def main(argv=None, **kw):
    argv = argv if argv is not None else sys.argv
    pasta = argv[1] if len(argv) > 1 else 'site/data'
    extras = os.environ.get('CARTEIRA_EXTRAS', '').upper().replace(',', ' ').split()
    # papéis da B3 da carteira (ações, FIIs, ETFs): um por linha em arquivo editável na VM
    arq_br = os.environ.get('CARTEIRA_EXTRAS_ARQUIVO', '')
    if arq_br and os.path.exists(arq_br):
        extras += [t for t in open(arq_br, encoding='utf-8').read().upper().replace(',', ' ').split() if t not in extras]
    eua = os.environ.get('CARTEIRA_EUA', '').upper().replace(',', ' ').split()
    # lista editável na VM, um código por linha ou separados por espaço (arquivo ao lado da pasta de dados)
    arq = os.environ.get('CARTEIRA_EUA_ARQUIVO', '')
    if arq and os.path.exists(arq):
        eua += open(arq, encoding='utf-8').read().upper().replace(',', ' ').split()
    dados = montar(extras, eua, **kw)
    if not dados['ativos'] or not dados['cdi']['datas']:
        print('Nada baixado (ativos ou CDI vazios); mantém o arquivo anterior.', file=sys.stderr)
        return 1
    os.makedirs(pasta, exist_ok=True)
    tmp = os.path.join(pasta, 'carteira.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(dados, f, separators=(',', ':'), allow_nan=False, ensure_ascii=False)
    os.replace(tmp, os.path.join(pasta, 'carteira.json'))
    principais = {k: a for k, a in dados['ativos'].items() if not a.get('apoio')}
    print('carteira.json: ' + ', '.join(f'{k} ({len(a["datas"])} dias, último {a["datas"][-1]})' + (f' [setor {a["setor"]["nome"]}: {a["setor"].get("ref") or ", ".join(a["setor"]["pares"])}]' if a.get('setor') else '') for k, a in principais.items())
          + f' | {len(dados["ativos"]) - len(principais)} de apoio (setores)' + (f' (não vieram: {", ".join(dados["falhasApoio"])})' if dados['falhasApoio'] else '')
          + f' | CDI até {dados["cdi"]["datas"][-1]} | IPCA até {dados["ipca"]["meses"][-1] if dados["ipca"]["meses"] else "—"}'
          + (f' | falharam: {", ".join(dados["falhas"])}' if dados['falhas'] else ''))
    return 0 if not dados['falhas'] else 2


if __name__ == '__main__':
    sys.exit(main())
