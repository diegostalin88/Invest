"""
fetch_all.py
------------
Coleta única e automática do projeto Invest. Substitui o fetch_data4.py (preços) e o
fetch_fundamentals.py (fundamentos + radar de 8-K + sinais extras), que continuam em legado/ para
referência. A lógica de cada etapa foi reaproveitada desses dois scripts.

Etapas:
  1. Universo: listas Nasdaq + "other listed" (NYSE/AMEX/ARCA) do nasdaqtrader.com, sem ETFs,
     sem emissores com problema financeiro sinalizado e sem classes com '$'.
  2. Preços: OHLCV ajustado (auto_adjust=True) via yfinance, em lotes com retry/backoff.
  3. Pré-filtro de preços: >= MIN_PREGOES pregões e volume financeiro médio de 20 dias
     >= MIN_ADTV_PRECOS. Séries duplicadas (erro do provedor) são removidas.
  4. Pool de fundamentos: tickers com volume financeiro médio de 20 dias >= MIN_ADTV_FUNDAMENTOS.
  5. Cache incremental: parte do fundamentos.json já publicado no GitHub Pages; só re-busca no
     Yahoo o que estiver vencido (DIAS_VALIDADE_FUNDAMENTOS) ou for novo. O radar de 8-K roda
     para o pool inteiro todo dia. Falha na busca mantém o valor do cache.
  6. Tamanho: arredonda preços, divide em arquivos de até ~TAMANHO_MAX_ARQUIVO_MB e, se o total
     passar de LIMITE_TOTAL_MB, reduz o histórico para ANOS_HISTORICO_REDUZIDO anos.
  7. Manifesto data/manifest.json.
  8. Portão de qualidade: sai com código != 0 (o job falha e nada é publicado) se os dados
     parecerem quebrados.

USO:
    python coleta/fetch_all.py --saida site/data

Variáveis de ambiente:
    SEC_USER_AGENT   obrigatório no GitHub Actions. Ex.: "InvestDiego seu-email@exemplo.com"
    TICKER_LIMIT     opcional. Processa só os N primeiros tickers do universo (modo teste).
    SITE_URL         opcional. URL base dos dados publicados (padrão: URL_DADOS_PUBLICADOS).

AVISO: ferramenta de apoio à análise, não é recomendação de investimento. Fontes gratuitas podem
vir incompletas, defasadas ou (raramente) erradas.
"""

import argparse
import gzip
import hashlib
import json
import os
import random
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from io import StringIO

import pandas as pd
import requests

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:  # pragma: no cover - o requirements.txt instala
    yf = None
    HAS_YFINANCE = False


# -----------------------------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------------------------
MIN_ADTV_PRECOS = 2_000_000        # US$ — volume financeiro médio 20d mínimo para entrar nos preços
MIN_ADTV_FUNDAMENTOS = 10_000_000  # US$ — idem, para entrar no pool de fundamentos
MIN_PREGOES = 250                  # mínimo de candles de histórico
DIAS_VALIDADE_FUNDAMENTOS = 7      # depois disso o fundamento é re-buscado no Yahoo
ANOS_HISTORICO = 5                 # histórico normal
ANOS_HISTORICO_REDUZIDO = 3        # usado se o total passar de LIMITE_TOTAL_MB
LIMITE_TOTAL_MB = 80               # tamanho total (bruto, sem gzip) acima do qual o histórico é reduzido
TAMANHO_MAX_ARQUIVO_MB = 20        # tamanho máximo de cada data/precos_NNN.json
ORCAMENTO_MINUTOS_FUNDAMENTOS = 90 # tempo máximo gasto re-buscando fundamentos no Yahoo por execução
MAX_FALHAS_SEGUIDAS_YAHOO = 25     # se o Yahoo falhar tantas vezes seguidas, para (provável bloqueio)
SEC_MAX_REQ_POR_SEG = 8            # a SEC pede no máximo 10/s; ficamos abaixo
CHUNK_SIZE = 40                    # tickers por lote no download de preços
QUEDA_MAXIMA_TICKERS = 0.30        # portão: bloqueia se cair mais que isso vs. execução anterior
MAX_DIAS_ULTIMO_PREGAO = 5         # portão: bloqueia se o último pregão for mais antigo que isso
VERSAO_MANIFESTO = 2
FORMATO_PRECOS = "colunar-v1"

URL_DADOS_PUBLICADOS = "https://diegostalin88.github.io/Invest/data/"
NASDAQ_LISTING_URL = "http://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTING_URL = "http://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

EXCLUDE_ETFS = True
EXCLUDE_FINANCIAL_STATUS_ISSUES = True

SLEEP_BETWEEN_TICKERS = (0.6, 1.4)  # educado com o Yahoo na busca de fundamentos
MIN_FIELDS_TO_TRUST_YFINANCE = 3     # de 6 campos-chave; abaixo disso, tenta o fallback da SEC também

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "").strip()


def log(msg=""):
    print(msg, flush=True)


# -----------------------------------------------------------------------------------------------
# 1) UNIVERSO (reaproveitado do fetch_data4.py)
# -----------------------------------------------------------------------------------------------
def normalize_for_yfinance(symbol):
    """yfinance espera hífen em vez de ponto para classes de ação (ex: BRK.B -> BRK-B)."""
    return symbol.strip().replace('.', '-')


def parse_nasdaq_listed(text):
    df = pd.read_csv(StringIO(text), sep='|')
    df = df[:-1]  # última linha = estatísticas do arquivo
    df = df.dropna(subset=['Symbol'])
    df['Symbol'] = df['Symbol'].astype(str)
    if 'Test Issue' in df.columns:
        df = df[df['Test Issue'] != 'Y']
    if EXCLUDE_ETFS and 'ETF' in df.columns:
        n = len(df)
        df = df[df['ETF'] != 'Y']
        log(f"  Removidos {n - len(df)} ETFs/fundos da lista Nasdaq.")
    if EXCLUDE_FINANCIAL_STATUS_ISSUES and 'Financial Status' in df.columns:
        n = len(df)
        df = df[df['Financial Status'] == 'N']  # N = Normal
        log(f"  Removidos {n - len(df)} emissores com problema financeiro/regulatório sinalizado.")
    df = df[~df['Symbol'].str.contains(r'\$')]
    return [normalize_for_yfinance(s) for s in df['Symbol'].tolist()]


def parse_other_listed(text):
    df = pd.read_csv(StringIO(text), sep='|')
    df = df[:-1]
    df = df.dropna(subset=['ACT Symbol'])
    df['ACT Symbol'] = df['ACT Symbol'].astype(str)
    if 'Test Issue' in df.columns:
        df = df[df['Test Issue'] != 'Y']
    if EXCLUDE_ETFS and 'ETF' in df.columns:
        n = len(df)
        df = df[df['ETF'] != 'Y']
        log(f"  Removidos {n - len(df)} ETFs/fundos da lista NYSE/AMEX/ARCA.")
    df = df[~df['ACT Symbol'].str.contains(r'\$')]
    return [normalize_for_yfinance(s) for s in df['ACT Symbol'].tolist()]


def baixar_universo():
    log("Baixando a lista de tickers da Nasdaq...")
    resp = requests.get(NASDAQ_LISTING_URL, timeout=30)
    resp.raise_for_status()
    tickers_nasdaq = parse_nasdaq_listed(resp.text)
    log(f"  {len(tickers_nasdaq)} tickers válidos da Nasdaq.")

    log("Baixando a lista de tickers de outras bolsas (NYSE/AMEX/ARCA)...")
    tickers_other = []
    try:
        resp = requests.get(OTHER_LISTING_URL, timeout=30)
        resp.raise_for_status()
        tickers_other = parse_other_listed(resp.text)
        log(f"  {len(tickers_other)} tickers válidos de outras bolsas.")
    except Exception as e:
        log(f"AVISO: falha ao obter tickers de outras bolsas ({e}). Prosseguindo apenas com Nasdaq.")

    universo = list(dict.fromkeys(tickers_nasdaq + tickers_other))
    log(f"Universo combinado: {len(universo)} tickers únicos.")
    return universo


# -----------------------------------------------------------------------------------------------
# 2) PREÇOS (reaproveitado do fetch_data4.py)
# -----------------------------------------------------------------------------------------------
def create_chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def download_with_retry(chunk, anos, max_retries=3):
    """Baixa um lote com backoff exponencial. O yfinance às vezes devolve vazio em vez de levantar
    exceção quando é limitado, então vazio também conta como falha."""
    for attempt in range(max_retries):
        try:
            dados = yf.download(
                chunk,
                period=f"{anos}y",
                group_by='ticker',
                progress=False,
                auto_adjust=True,  # CRÍTICO: ajusta splits e dividendos
                threads=True,
            )
            if dados is not None and not dados.empty:
                return dados
            raise RuntimeError("resposta vazia")
        except Exception as e:
            wait_time = (2 ** attempt) + random.uniform(1, 3)
            log(f"  [Aviso] Falha no download (tentativa {attempt + 1}/{max_retries}): {e}. Aguardando {wait_time:.1f}s...")
            time.sleep(wait_time)
    return None


REQUIRED_COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']


def _frame_do_ticker(dados_lote, ticker):
    """Extrai o DataFrame de um ticker, lidando com as variações de formato do yfinance
    (MultiIndex com ticker no nível 0 ou 1, ou colunas simples quando o lote tem 1 ticker)."""
    cols = dados_lote.columns
    if isinstance(cols, pd.MultiIndex):
        if ticker in cols.get_level_values(0):
            return dados_lote[ticker].copy()
        if cols.nlevels > 1 and ticker in cols.get_level_values(1):
            return dados_lote.xs(ticker, axis=1, level=1).copy()
        return None
    return dados_lote.copy()


def extrair_series(dados_lote, chunk):
    """Converte o DataFrame do yfinance em {ticker: {dates, open, high, low, close, volume}}
    (preços ainda sem arredondamento)."""
    saida = {}
    if dados_lote is None or dados_lote.empty:
        return saida
    for ticker in chunk:
        bruto = _frame_do_ticker(dados_lote, ticker)
        if bruto is None or bruto.empty:
            continue
        if not all(c in bruto.columns for c in REQUIRED_COLUMNS):
            continue
        bruto = bruto[REQUIRED_COLUMNS].apply(pd.to_numeric, errors='coerce')
        limpos = bruto.dropna()
        limpos = limpos[limpos['Volume'] > 0]
        if limpos.empty:
            continue
        idx = pd.to_datetime(limpos.index)
        saida[ticker] = {
            'dates': idx.strftime('%Y-%m-%d').tolist(),
            'open': limpos['Open'].astype(float).tolist(),
            'high': limpos['High'].astype(float).tolist(),
            'low': limpos['Low'].astype(float).tolist(),
            'close': limpos['Close'].astype(float).tolist(),
            'volume': limpos['Volume'].astype('int64').tolist(),
        }
    return saida


def baixar_precos(tickers, anos):
    todos = {}
    chunks = list(create_chunks(tickers, CHUNK_SIZE))
    log(f"Baixando preços de {len(tickers)} tickers em {len(chunks)} lotes de ~{CHUNK_SIZE}...")
    lotes_falhos = 0
    for i, chunk in enumerate(chunks):
        dados_lote = download_with_retry(chunk, anos)
        if dados_lote is None:
            lotes_falhos += 1
            log(f"  [Erro] Lote {i + 1}/{len(chunks)} falhou após retentativas. Pulando.")
        else:
            series = extrair_series(dados_lote, chunk)
            todos.update(series)
            log(f"  Lote {i + 1}/{len(chunks)}: {len(series)}/{len(chunk)} tickers com dados (total {len(todos)}).")
        if i < len(chunks) - 1:
            time.sleep(random.uniform(2.5, 5.0))  # pausa anti-ban entre lotes
    return todos, lotes_falhos


def remover_duplicatas(todos):
    """Remove ativos com séries matematicamente idênticas (lixo do provedor). Devolve os removidos."""
    hashes, removidos = {}, []
    for ticker in list(todos.keys()):
        data = todos[ticker]
        h = hashlib.md5((str(data['close']) + str(data['volume'])).encode()).hexdigest()
        if h in hashes:
            log(f"  Histórico de '{hashes[h]}' duplicado em '{ticker}'. Removendo '{ticker}'.")
            removidos.append(ticker)
            del todos[ticker]
        else:
            hashes[h] = ticker
    return removidos


# -----------------------------------------------------------------------------------------------
# 3) PRÉ-FILTROS E TAMANHO
# -----------------------------------------------------------------------------------------------
def adtv20(serie):
    """Volume financeiro médio dos últimos 20 pregões (close * volume), mesmo cálculo do Screener."""
    close, vol = serie['close'][-20:], serie['volume'][-20:]
    if len(close) < 20:
        return 0.0
    return sum(c * v for c, v in zip(close, vol)) / 20.0


def aplicar_prefiltro_precos(todos, min_adtv=None, min_pregoes=None):
    min_adtv = MIN_ADTV_PRECOS if min_adtv is None else min_adtv
    min_pregoes = MIN_PREGOES if min_pregoes is None else min_pregoes
    return {t: s for t, s in todos.items() if len(s['close']) >= min_pregoes and adtv20(s) >= min_adtv}


def selecionar_pool_fundamentos(precos, min_adtv=None):
    min_adtv = MIN_ADTV_FUNDAMENTOS if min_adtv is None else min_adtv
    pool = [(t, adtv20(s)) for t, s in precos.items()]
    pool = [p for p in pool if p[1] >= min_adtv]
    pool.sort(key=lambda p: -p[1])  # mais líquidos primeiro (prioridade se o orçamento de tempo acabar)
    return [t for t, _ in pool]


def arredondar_preco(x):
    return round(float(x), 2) if abs(x) >= 1 else round(float(x), 4)


def arredondar_serie(serie):
    return {
        'dates': list(serie['dates']),
        'open': [arredondar_preco(x) for x in serie['open']],
        'high': [arredondar_preco(x) for x in serie['high']],
        'low': [arredondar_preco(x) for x in serie['low']],
        'close': [arredondar_preco(x) for x in serie['close']],
        'volume': [int(v) for v in serie['volume']],
    }


def cortar_historico(precos, anos, ultimo_pregao):
    """Mantém só os últimos `anos` anos (contados a partir do último pregão)."""
    ultimo = date.fromisoformat(ultimo_pregao)
    try:
        corte = ultimo.replace(year=ultimo.year - anos).isoformat()
    except ValueError:  # 29/fev
        corte = (ultimo - timedelta(days=365 * anos)).isoformat()
    saida = {}
    for t, s in precos.items():
        i0 = next((i for i, d in enumerate(s['dates']) if d > corte), len(s['dates']))
        saida[t] = {k: v[i0:] for k, v in s.items()}
    return saida


def calcular_ultimo_pregao(precos):
    datas = [s['dates'][-1] for s in precos.values() if s.get('dates')]
    return max(datas) if datas else None


def _json_compacto(obj):
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False)


def montar_arquivos_precos(precos, max_bytes=None):
    """Divide os preços em arquivos de até ~max_bytes, no formato colunar-v1:

        {"formato": "colunar-v1",
         "datas": [... calendário de todas as datas presentes no arquivo ...],
         "ativos": {"AAPL": {"i0": 3, "open": [...], ...},          # datas = datas[i0 : i0+len]
                    "XYZ":  {"dates": [...], "open": [...], ...}}}   # série com buraco: datas explícitas

    Gravar o calendário uma vez por arquivo (em vez de repetir as datas em cada ativo) corta ~30%
    do tamanho. O app remonta exatamente o mesmo {TICKER: {dates, open, ...}} de antes.
    Devolve [(nome_arquivo, bytes)]."""
    max_bytes = int((TAMANHO_MAX_ARQUIVO_MB * 1024 * 1024) if max_bytes is None else max_bytes)
    calendario = sorted({d for s in precos.values() for d in s['dates']})
    pos = {d: i for i, d in enumerate(calendario)}

    entradas = []
    for t in sorted(precos.keys()):
        s = precos[t]
        i0 = pos[s['dates'][0]]
        contiguo = calendario[i0:i0 + len(s['dates'])] == s['dates']
        item = {'i0': i0} if contiguo else {'dates': s['dates']}
        item.update({k: s[k] for k in ('open', 'high', 'low', 'close', 'volume')})
        entradas.append((t, _json_compacto(t) + ':' + _json_compacto(item)))

    cabecalho = '{"formato":' + _json_compacto(FORMATO_PRECOS) + ',"datas":' + _json_compacto(calendario) + ',"ativos":{'
    rodape = '}}'
    base = len(cabecalho.encode()) + len(rodape)

    arquivos, atual, tam = [], [], base
    for _, trecho in entradas:
        n = len(trecho.encode()) + 1
        if atual and tam + n > max_bytes:
            arquivos.append(atual)
            atual, tam = [], base
        atual.append(trecho)
        tam += n
    if atual or not arquivos:
        arquivos.append(atual)

    return [(f"precos_{i:03d}.json", (cabecalho + ','.join(partes) + rodape).encode('utf-8'))
            for i, partes in enumerate(arquivos)]


def expandir_arquivo_precos(obj):
    """Inverso de montar_arquivos_precos (usado nos testes e por quem quiser ler os dados em Python)."""
    if obj.get('formato') != FORMATO_PRECOS:
        return obj  # formato antigo {TICKER: {...}}
    cal = obj['datas']
    saida = {}
    for t, a in obj['ativos'].items():
        n = len(a['close'])
        dates = a['dates'] if 'dates' in a else cal[a['i0']:a['i0'] + n]
        saida[t] = {'dates': dates, **{k: a[k] for k in ('open', 'high', 'low', 'close', 'volume')}}
    return saida


def mb(n_bytes):
    return n_bytes / (1024 * 1024)


# -----------------------------------------------------------------------------------------------
# 4) SEC EDGAR — cliente com limite de taxa (reaproveitado do fetch_fundamentals.py)
# -----------------------------------------------------------------------------------------------
class LimitadorTaxa:
    """Garante no máximo `por_segundo` chamadas por segundo (thread-safe)."""

    def __init__(self, por_segundo):
        self.intervalo = 1.0 / por_segundo
        self.ultimo = 0.0
        self.lock = threading.Lock()

    def esperar(self):
        with self.lock:
            agora = time.monotonic()
            espera = self.ultimo + self.intervalo - agora
            if espera > 0:
                time.sleep(espera)
            self.ultimo = time.monotonic()


_limitador_sec = LimitadorTaxa(SEC_MAX_REQ_POR_SEG)


def sec_get(url, max_retries=3):
    """GET na SEC com User-Agent da variável de ambiente, limite de taxa e retry em 429/5xx.
    Devolve o Response, ou None se não deu."""
    if not SEC_USER_AGENT:
        return None
    for attempt in range(max_retries):
        _limitador_sec.esperar()
        try:
            resp = requests.get(url, headers={'User-Agent': SEC_USER_AGENT}, timeout=20)
        except Exception as e:
            log(f"    [SEC] erro de rede em {url}: {e}")
            resp = None
        if resp is not None and resp.status_code not in (429, 500, 502, 503, 504):
            return resp
        time.sleep((2 ** attempt) + random.uniform(0.5, 1.5))
    return None


_sec_ticker_map_cache = None


def load_sec_ticker_map():
    """Baixa (uma vez) o mapa ticker -> CIK que a SEC disponibiliza publicamente."""
    global _sec_ticker_map_cache
    if _sec_ticker_map_cache is not None:
        return _sec_ticker_map_cache
    mapping = {}
    try:
        resp = sec_get("https://www.sec.gov/files/company_tickers.json")
        if resp is not None and resp.status_code == 200:
            for _, row in resp.json().items():
                mapping[row['ticker'].upper()] = str(row['cik_str']).zfill(10)
            log(f"  Mapa de tickers da SEC carregado ({len(mapping)} empresas).")
        else:
            log("  AVISO: não consegui baixar o mapa de tickers da SEC. Fallback SEC e radar de 8-K indisponíveis.")
    except Exception as e:
        log(f"  AVISO: erro lendo o mapa de tickers da SEC ({e}).")
    _sec_ticker_map_cache = mapping
    return mapping


def _extract_latest_annual_facts(facts_json, tags, unit='USD'):
    us_gaap = facts_json.get('facts', {}).get('us-gaap', {})
    for tag in tags:
        entry = us_gaap.get(tag)
        if not entry:
            continue
        units = entry.get('units', {}).get(unit)
        if not units:
            continue
        annual = [u for u in units if u.get('form') == '10-K' and u.get('fp') == 'FY' and u.get('val') is not None]
        if not annual:
            continue
        annual.sort(key=lambda u: u.get('end', ''))
        latest = annual[-1]['val']
        prior = annual[-2]['val'] if len(annual) >= 2 else None
        return latest, prior
    return None, None


def fetch_from_sec_edgar(ticker, price, sec_map):
    cik = sec_map.get(ticker)
    if not cik:
        return None
    try:
        resp = sec_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        if resp is None or resp.status_code != 200:
            return None
        facts = resp.json()
    except Exception as e:
        log(f"    [SEC EDGAR] falhou para {ticker}: {e}")
        return None

    revenue, revenue_prior = _extract_latest_annual_facts(
        facts, ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet'])
    net_income, _ = _extract_latest_annual_facts(facts, ['NetIncomeLoss'])
    equity, _ = _extract_latest_annual_facts(facts, ['StockholdersEquity'])
    liabilities, _ = _extract_latest_annual_facts(facts, ['Liabilities'])
    eps, _ = _extract_latest_annual_facts(facts, ['EarningsPerShareDiluted', 'EarningsPerShareBasic'], unit='USD/shares')
    shares, _ = _extract_latest_annual_facts(facts, ['CommonStockSharesOutstanding', 'CommonStockSharesIssued'], unit='shares')

    result = {'pe': None, 'pb': None, 'roe': None, 'debtToEquity': None, 'netMargin': None, 'revenueGrowth': None}
    if price and eps and eps != 0:
        result['pe'] = price / eps
    if equity and net_income is not None:
        result['roe'] = net_income / equity if equity != 0 else None
    if equity and liabilities is not None and equity != 0:
        result['debtToEquity'] = liabilities / equity  # aproximação: passivo total / PL
    if revenue and net_income is not None and revenue != 0:
        result['netMargin'] = net_income / revenue
    if revenue and revenue_prior and revenue_prior != 0:
        result['revenueGrowth'] = (revenue - revenue_prior) / revenue_prior
    if price and equity and shares and shares != 0:
        bvps = equity / shares
        if bvps > 0:
            result['pb'] = price / bvps
    return result


# Radar de eventos corporativos (8-K). Ver legado/fetch_fundamentals.py para a motivação (caso MKTX).
CRITICAL_8K_ITEMS = {
    '1.03': 'Falência ou recuperação judicial',
    '3.01': 'Risco de ser deslistado da bolsa',
    '4.02': 'Não-confiabilidade de demonstrações financeiras anteriores (restatement)',
}
WATCH_8K_ITEMS = {
    '1.01': 'Entrada em acordo material relevante (pode ser fusão/aquisição, entre outras coisas)',
    '2.01': 'Conclusão de aquisição ou venda de ativos relevantes',
}
CORPORATE_EVENTS_LOOKBACK_DAYS = 180


def fetch_corporate_events(ticker, cik, hoje=None):
    """Devolve {'nivel': 'critico'|'atencao'|None, 'eventos': [...], 'ok': bool}.
    'ok' = False quando a consulta à SEC falhou (aí quem chama mantém o valor do cache)."""
    if not cik:
        return {'nivel': None, 'eventos': [], 'ok': True}
    try:
        resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
        if resp is None or resp.status_code != 200:
            return {'nivel': None, 'eventos': [], 'ok': False}
        data = resp.json()
    except Exception as e:
        log(f"    [SEC EDGAR/8-K] falhou para {ticker}: {e}")
        return {'nivel': None, 'eventos': [], 'ok': False}

    recent = data.get('filings', {}).get('recent', {})
    forms = recent.get('form', [])
    dates = recent.get('filingDate', [])
    items_list = recent.get('items', [])
    accessions = recent.get('accessionNumber', [])
    primary_docs = recent.get('primaryDocument', [])
    cik_int = str(int(cik))
    hoje = hoje or datetime.now(timezone.utc).date()
    cutoff = (hoje - timedelta(days=CORPORATE_EVENTS_LOOKBACK_DAYS)).isoformat()

    eventos, nivel = [], None
    for i, form in enumerate(forms):
        if form != '8-K':
            continue
        filing_date = dates[i] if i < len(dates) else None
        if not filing_date or filing_date < cutoff:
            continue
        raw_items = (items_list[i] if i < len(items_list) else '') or ''
        item_codes = [x.strip() for x in raw_items.split(',') if x.strip()]
        matched = [(c, CRITICAL_8K_ITEMS[c]) for c in item_codes if c in CRITICAL_8K_ITEMS]
        matched += [(c, WATCH_8K_ITEMS[c]) for c in item_codes if c in WATCH_8K_ITEMS]
        if not matched:
            continue
        accession = accessions[i].replace('-', '') if i < len(accessions) else ''
        doc = primary_docs[i] if i < len(primary_docs) else ''
        url_doc = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}" if accession and doc else None
        for code, desc in matched:
            eventos.append({'data': filing_date, 'item': code, 'descricao': desc, 'url': url_doc})
            if code in CRITICAL_8K_ITEMS:
                nivel = 'critico'
            elif nivel != 'critico':
                nivel = 'atencao'
    eventos.sort(key=lambda e: e['data'], reverse=True)
    # Datas de divulgação de resultado (8-K item 2.02): servem para estimar o próximo balanço
    balancos = sorted({dates[i] for i, form in enumerate(forms)
                       if form in ('8-K', '8-K/A') and i < len(dates) and dates[i]
                       and '2.02' in [x.strip() for x in ((items_list[i] if i < len(items_list) else '') or '').split(',')]})
    return {'nivel': nivel, 'eventos': eventos, 'ok': True, 'balancos': balancos[-12:]}


def estimar_proximo_balanco(balancos, hoje):
    """Estima a data do próximo resultado a partir das divulgações passadas (8-K item 2.02).
    Usa o mesmo trimestre do ano anterior + 364 dias (as empresas repetem o calendário); se não houver,
    soma 91 dias ao último até passar de hoje. Devolve 'AAAA-MM-DD' ou None."""
    if not balancos:
        return None
    datas = sorted(date.fromisoformat(d) for d in balancos)
    ultimo = datas[-1]
    candidatos = [d + timedelta(days=364) for d in datas
                  if hoje <= d + timedelta(days=364) and ultimo + timedelta(days=30) < d + timedelta(days=364) <= ultimo + timedelta(days=130)]
    if candidatos:
        return min(candidatos).isoformat()
    prox = ultimo + timedelta(days=91)
    while prox < hoje:
        prox += timedelta(days=91)
    return prox.isoformat()


# -----------------------------------------------------------------------------------------------
# 5) yfinance — fundamentos e sinais extras (reaproveitado do fetch_fundamentals.py)
# -----------------------------------------------------------------------------------------------
def get_next_earnings_date(yf_ticker_obj):
    try:
        cal = yf_ticker_obj.calendar
        if cal is None:
            return None
        if isinstance(cal, dict):
            dates = cal.get('Earnings Date')
            if dates:
                d = dates[0] if isinstance(dates, (list, tuple)) else dates
                return d.isoformat() if hasattr(d, 'isoformat') else str(d)
        elif hasattr(cal, 'loc') and 'Earnings Date' in getattr(cal, 'index', []):
            d = cal.loc['Earnings Date'][0]
            return d.isoformat() if hasattr(d, 'isoformat') else str(d)
    except Exception:
        pass
    return None


def fetch_from_yfinance(ticker):
    """Campos-chave + sinais extras, ou None se o Yahoo falhou."""
    if not HAS_YFINANCE:
        return None
    try:
        t = yf.Ticker(ticker)
        try:
            info = t.get_info()
        except AttributeError:
            info = t.info
        if not info or not isinstance(info, dict):
            return None
        result = {
            'pe': info.get('trailingPE') or info.get('forwardPE'),
            'pb': info.get('priceToBook'),
            'roe': info.get('returnOnEquity'),
            'debtToEquity': (info.get('debtToEquity') / 100.0) if info.get('debtToEquity') is not None else None,
            'netMargin': info.get('profitMargins'),
            'revenueGrowth': info.get('revenueGrowth'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'marketCap': info.get('marketCap'),
            'longName': info.get('longName') or info.get('shortName'),
            'price': info.get('currentPrice') or info.get('regularMarketPrice'),
            'shortPercentOfFloat': info.get('shortPercentOfFloat'),
            'shortRatio': info.get('shortRatio'),
            'targetMeanPrice': info.get('targetMeanPrice'),
            'recommendationKey': info.get('recommendationKey'),
            'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
            'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
        }
        result['nextEarningsDate'] = get_next_earnings_date(t)
        return result
    except Exception as e:
        log(f"    [yfinance] falhou para {ticker}: {e}")
        return None


KEY_FIELDS = ['pe', 'pb', 'roe', 'debtToEquity', 'netMargin', 'revenueGrowth']


def count_key_fields(d):
    if not d:
        return 0
    return sum(1 for k in KEY_FIELDS if d.get(k) is not None)


def _registro_vazio():
    return {'pe': None, 'pb': None, 'roe': None, 'debtToEquity': None, 'netMargin': None,
            'revenueGrowth': None, 'sector': None, 'industry': None, 'marketCap': None,
            'longName': None, 'price': None}


def buscar_fundamento(ticker, price, sec_map, sufixo_yahoo=''):
    """Mesma lógica do build_fundamentals original, para um ticker. Não inclui o radar de 8-K
    (que roda à parte, para o pool inteiro). Devolve (registro, yahoo_respondeu, sucesso).
    `sufixo_yahoo` = '.SA' para ações da B3 (o ticker guardado fica sem o sufixo)."""
    yf_data = fetch_from_yfinance(ticker + sufixo_yahoo)
    n_fields = count_key_fields(yf_data)
    used = set()
    if yf_data and any(v is not None for v in yf_data.values()):
        used.add('yfinance')
    final = dict(yf_data) if yf_data else _registro_vazio()
    price = price or final.get('price')

    if n_fields < MIN_FIELDS_TO_TRUST_YFINANCE and sec_map:
        sec_data = fetch_from_sec_edgar(ticker, price, sec_map)
        if sec_data:
            used.add('sec_edgar')
            for k, v in sec_data.items():
                if final.get(k) is None and v is not None:
                    final[k] = v

    final['price'] = price
    if 'yfinance' in used and 'sec_edgar' in used:
        final['fonte'] = 'combinado'
    elif 'yfinance' in used:
        final['fonte'] = 'yfinance'
    elif 'sec_edgar' in used:
        final['fonte'] = 'sec_edgar'
    else:
        final['fonte'] = 'indisponivel'
    # Sucesso = o Yahoo trouxe algum dado, ou a SEC trouxe pelo menos um índice. Uma resposta
    # "vazia" não pode sobrescrever um cache bom.
    sucesso = 'yfinance' in used or count_key_fields(final) > 0
    return final, yf_data is not None, sucesso


def _idade_dias(registro, hoje):
    s = (registro or {}).get('atualizadoEm')
    if not s:
        return None
    try:
        return (hoje - date.fromisoformat(str(s)[:10])).days
    except ValueError:
        return None


def precisa_atualizar(ticker, cache, hoje, validade=None):
    validade = DIAS_VALIDADE_FUNDAMENTOS if validade is None else validade
    idade = _idade_dias(cache.get(ticker), hoje)
    return idade is None or idade > validade


def atualizar_fundamentos(pool, cache, price_lookup, hoje, sec_map, orcamento_seg=None,
                          dormir=True, relogio=time.monotonic, sufixo_yahoo='', radar=True):
    """Aplica as regras de cache incremental e devolve (fundamentos, stats).

    - Re-busca no Yahoo só quem é novo no pool ou tem atualizadoEm com mais de
      DIAS_VALIDADE_FUNDAMENTOS dias (novos primeiro, depois os mais velhos), até acabar o orçamento
      de tempo ou o Yahoo falhar MAX_FALHAS_SEGUIDAS_YAHOO vezes seguidas.
    - Se a busca de um ticker falhar, mantém o valor do cache.
    - O radar de 8-K roda para o pool inteiro; se a SEC falhar, mantém o alerta do cache.
    - O preço de referência é atualizado todo dia a partir dos dados de preço."""
    orcamento_seg = ORCAMENTO_MINUTOS_FUNDAMENTOS * 60 if orcamento_seg is None else orcamento_seg
    hoje_iso = hoje.isoformat()
    stats = {'atualizadosHoje': 0, 'falhasMantidasDoCache': 0, 'pendentes': 0,
             'radarFalhas': 0, 'yahooInterrompido': False, 'orcamentoEsgotado': False}

    a_buscar = [t for t in pool if precisa_atualizar(t, cache, hoje)]
    a_buscar.sort(key=lambda t: (t in cache and cache[t].get('atualizadoEm') is not None,
                                 (cache.get(t) or {}).get('atualizadoEm') or ''))
    log(f"Fundamentos: pool de {len(pool)} tickers; {len(a_buscar)} a re-buscar no Yahoo "
        f"({len(pool) - len(a_buscar)} vêm do cache com menos de {DIAS_VALIDADE_FUNDAMENTOS} dias).")

    saida = {t: dict(cache[t]) for t in pool if t in cache}
    inicio = relogio()
    falhas_seguidas = 0
    for n, ticker in enumerate(a_buscar, 1):
        if relogio() - inicio > orcamento_seg:
            stats['orcamentoEsgotado'] = True
            stats['pendentes'] = len(a_buscar) - n + 1
            log(f"  Orçamento de tempo esgotado: {stats['pendentes']} tickers ficam para a próxima execução.")
            break
        if falhas_seguidas >= MAX_FALHAS_SEGUIDAS_YAHOO:
            stats['yahooInterrompido'] = True
            stats['pendentes'] = len(a_buscar) - n + 1
            log(f"  Yahoo falhou {falhas_seguidas} vezes seguidas (provável bloqueio). Parando; "
                f"{stats['pendentes']} tickers ficam com o valor do cache.")
            break
        price = price_lookup.get(ticker)
        registro, yahoo_ok, sucesso = buscar_fundamento(ticker, price, sec_map, sufixo_yahoo)
        falhas_seguidas = 0 if yahoo_ok else falhas_seguidas + 1
        if sucesso:
            registro['atualizadoEm'] = hoje_iso
            antigo = saida.get(ticker, {})
            registro['alertaEvento'] = antigo.get('alertaEvento')
            registro['eventosCorporativos'] = antigo.get('eventosCorporativos', [])
            for chave in ('balancos', 'balancoEstimado'):
                if antigo.get(chave):
                    registro[chave] = antigo[chave]
            saida[ticker] = registro
            stats['atualizadosHoje'] += 1
        elif ticker in saida and saida[ticker].get('atualizadoEm'):
            stats['falhasMantidasDoCache'] += 1
        else:
            # Novo e sem Yahoo: guarda o que a SEC deu (ou vazio), sem data, para tentar de novo amanhã.
            registro['atualizadoEm'] = None
            registro.setdefault('alertaEvento', None)
            registro.setdefault('eventosCorporativos', [])
            saida[ticker] = registro
        if n % 50 == 0:
            log(f"  [{n}/{len(a_buscar)}] fundamentos re-buscados ({stats['atualizadosHoje']} ok).")
        if dormir:
            time.sleep(random.uniform(*SLEEP_BETWEEN_TICKERS))

    # Novos que nem chegaram a ser tentados (orçamento/bloqueio): entram vazios, sem data.
    for t in pool:
        if t not in saida:
            reg = _registro_vazio()
            reg.update({'fonte': 'indisponivel', 'atualizadoEm': None, 'alertaEvento': None, 'eventosCorporativos': []})
            saida[t] = reg

    # Radar de 8-K: pool inteiro, todo dia (só EUA; a B3 não arquiva 8-K na SEC).
    if radar:
        log(f"Radar de 8-K para {len(pool)} tickers...")
    for t in pool:
        if not radar:
            if price_lookup.get(t):
                saida[t]['price'] = price_lookup[t]
            continue
        cik = (sec_map or {}).get(t)
        ev = fetch_corporate_events(t, cik, hoje) if sec_map else {'ok': False}
        if ev.get('ok'):
            saida[t]['alertaEvento'] = ev['nivel']
            saida[t]['eventosCorporativos'] = ev['eventos']
            saida[t]['radarEm'] = hoje_iso
            if ev.get('balancos'):
                saida[t]['balancos'] = ev['balancos']
                saida[t]['balancoEstimado'] = estimar_proximo_balanco(ev['balancos'], hoje)
        else:
            stats['radarFalhas'] += 1
        if price_lookup.get(t):
            saida[t]['price'] = price_lookup[t]

    stats['alertasCriticos'] = sum(1 for r in saida.values() if r.get('alertaEvento') == 'critico')
    stats['comDados'] = sum(1 for r in saida.values() if count_key_fields(r) > 0)
    return saida, stats


# -----------------------------------------------------------------------------------------------
# 6) MANIFESTO E PORTÃO DE QUALIDADE
# -----------------------------------------------------------------------------------------------
def baixar_json_publicado(nome, base_url):
    """Baixa um JSON já publicado no Pages. Devolve None se não existir/der erro."""
    url = base_url.rstrip('/') + '/' + nome
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        log(f"  {url} -> HTTP {resp.status_code} (considerando inexistente).")
    except Exception as e:
        log(f"  Não consegui baixar {url} ({e}). Considerando inexistente.")
    return None


def montar_manifesto(gerado_em, ultimo_pregao, anos, arquivos_precos, stats, avisos=None, tamanhos=None,
                     mercado='us', moeda='USD'):
    return {
        'versao': VERSAO_MANIFESTO,
        'mercado': mercado,
        'moeda': moeda,
        'geradoEm': gerado_em,
        'ultimoPregao': ultimo_pregao,
        'anosHistorico': anos,
        'formatoPrecos': FORMATO_PRECOS,
        'arquivosPrecos': list(arquivos_precos),
        'arquivoFundamentos': 'fundamentos.json',
        'stats': stats,
        'tamanhos': tamanhos or {},
        'avisos': avisos or [],
    }


def portao_qualidade(manifesto, manifesto_anterior, fundamentos, hoje):
    """Devolve a lista de motivos para bloquear a publicação (vazia = pode publicar)."""
    erros = []
    n = manifesto['stats'].get('tickersPrecos', 0)
    if manifesto_anterior:
        n_ant = (manifesto_anterior.get('stats') or {}).get('tickersPrecos') or 0
        if n_ant and n < (1 - QUEDA_MAXIMA_TICKERS) * n_ant:
            erros.append(f"Tickers com preço caíram de {n_ant} para {n} (queda maior que "
                         f"{int(QUEDA_MAXIMA_TICKERS * 100)}%). Possível bloqueio do Yahoo.")
    if n == 0:
        erros.append("Nenhum ticker com preço.")
    up = manifesto.get('ultimoPregao')
    if not up:
        erros.append("Sem data de último pregão.")
    else:
        atraso = (hoje - date.fromisoformat(up)).days
        if atraso > MAX_DIAS_ULTIMO_PREGAO:
            erros.append(f"Último pregão ({up}) tem {atraso} dias corridos (máximo {MAX_DIAS_ULTIMO_PREGAO}).")
    if not any(count_key_fields(r) > 0 for r in (fundamentos or {}).values()):
        erros.append("Nenhum fundamento veio preenchido.")
    return erros


def escrever_resumo(linhas):
    """Escreve no $GITHUB_STEP_SUMMARY (se existir) e no log."""
    texto = "\n".join(linhas) + "\n"
    log("\n" + texto)
    caminho = os.environ.get('GITHUB_STEP_SUMMARY')
    if caminho:
        with open(caminho, 'a', encoding='utf-8') as f:
            f.write(texto)


# -----------------------------------------------------------------------------------------------
# 7) ORQUESTRAÇÃO
# -----------------------------------------------------------------------------------------------
def gerar_saida(precos_brutos, anos_inicial, limite_bytes=None):
    """Arredonda, mede e (se precisar) corta o histórico. Devolve (arquivos, anos, avisos)."""
    limite_bytes = LIMITE_TOTAL_MB * 1024 * 1024 if limite_bytes is None else limite_bytes
    avisos = []
    ultimo = calcular_ultimo_pregao(precos_brutos)
    precos = {t: arredondar_serie(s) for t, s in precos_brutos.items()}
    arquivos = montar_arquivos_precos(precos)
    total = sum(len(b) for _, b in arquivos)
    log(f"Tamanho dos preços com {anos_inicial} anos: {mb(total):.1f} MB em {len(arquivos)} arquivo(s).")
    anos = anos_inicial
    if total > limite_bytes and anos_inicial > ANOS_HISTORICO_REDUZIDO:
        anos = ANOS_HISTORICO_REDUZIDO
        precos = cortar_historico(precos, anos, ultimo)
        arquivos = montar_arquivos_precos(precos)
        novo = sum(len(b) for _, b in arquivos)
        avisos.append(f"Histórico reduzido de {anos_inicial} para {anos} anos: os preços tinham "
                      f"{mb(total):.1f} MB (limite {LIMITE_TOTAL_MB} MB) e agora têm {mb(novo):.1f} MB. "
                      f"Isso afeta o Backtest e o Walk-Forward.")
        log("AVISO: " + avisos[-1])
        total = novo
    if total > limite_bytes:
        avisos.append(f"Mesmo com {anos} anos, os preços somam {mb(total):.1f} MB (acima de {LIMITE_TOTAL_MB} MB). "
                      f"Publicado assim mesmo; o navegador baixa a versão comprimida.")
        log("AVISO: " + avisos[-1])
    return arquivos, anos, avisos


def main(argv=None):
    t0 = time.monotonic()
    ap = argparse.ArgumentParser(description="Coleta preços e fundamentos para o app Invest.")
    ap.add_argument('--saida', default='site/data', help='pasta de saída (padrão: site/data)')
    ap.add_argument('--sem-brasil', action='store_true', help='não coletar o IBOVESPA')
    ap.add_argument('--url-publicado', default=os.environ.get('SITE_URL') or URL_DADOS_PUBLICADOS,
                    help='URL base dos dados já publicados (cache e portão de qualidade)')
    args = ap.parse_args(argv)

    hoje = datetime.now(timezone.utc).date()
    em_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
    if not SEC_USER_AGENT:
        msg = ("SEC_USER_AGENT não definido. Crie a Repository variable SEC_USER_AGENT "
               "(Settings → Secrets and variables → Actions → Variables), ex.: 'InvestDiego seu-email@exemplo.com'.")
        if em_actions:
            escrever_resumo(["## ❌ Coleta não executada", "", msg])
            return 3
        log("AVISO: " + msg + " Rodando sem SEC (sem radar de 8-K e sem fallback de fundamentos).")

    limite = os.environ.get('TICKER_LIMIT', '').strip()
    limite = int(limite) if limite.isdigit() and int(limite) > 0 else None

    log("=== 1/6 Execução anterior (manifesto e fundamentos publicados) ===")
    manifesto_anterior = baixar_json_publicado('manifest.json', args.url_publicado)
    cache = baixar_json_publicado('fundamentos.json', args.url_publicado) or {}
    log(f"  Cache de fundamentos: {len(cache)} tickers.")

    log("=== 2/6 Universo ===")
    universo = baixar_universo()
    if limite:
        universo = universo[:limite]
        log(f"MODO TESTE: TICKER_LIMIT={limite} → processando só {len(universo)} tickers.")

    log("=== 3/6 Preços ===")
    brutos, lotes_falhos = baixar_precos(universo, ANOS_HISTORICO)
    n_baixados = len(brutos)
    duplicados = remover_duplicatas(brutos)
    precos_brutos = aplicar_prefiltro_precos(brutos)
    log(f"Pré-filtro: {len(precos_brutos)} de {len(brutos)} tickers com >= {MIN_PREGOES} pregões e "
        f"ADTV20 >= US$ {MIN_ADTV_PRECOS:,.0f}.")
    del brutos

    log("=== 4/6 Fundamentos, radar de 8-K e sinais extras ===")
    pool = selecionar_pool_fundamentos(precos_brutos)
    price_lookup = {t: arredondar_preco(precos_brutos[t]['close'][-1]) for t in pool}
    sec_map = load_sec_ticker_map() if SEC_USER_AGENT else {}
    fundamentos, fstats = atualizar_fundamentos(pool, cache, price_lookup, hoje, sec_map)

    log("=== 5/6 Gravando arquivos ===")
    arquivos, anos, avisos = gerar_saida(precos_brutos, ANOS_HISTORICO)
    ultimo = calcular_ultimo_pregao(precos_brutos)
    os.makedirs(args.saida, exist_ok=True)
    for nome in os.listdir(args.saida):
        if nome.startswith('precos_') and nome.endswith('.json'):
            os.remove(os.path.join(args.saida, nome))
    for nome, conteudo in arquivos:
        with open(os.path.join(args.saida, nome), 'wb') as f:
            f.write(conteudo)
    fund_bytes = _json_compacto(fundamentos).encode('utf-8')
    with open(os.path.join(args.saida, 'fundamentos.json'), 'wb') as f:
        f.write(fund_bytes)

    bytes_precos = sum(len(b) for _, b in arquivos)
    gz_precos = sum(len(gzip.compress(b, 6)) for _, b in arquivos)
    gz_fund = len(gzip.compress(fund_bytes, 6))
    tamanhos = {'precosBytes': bytes_precos, 'precosGzipBytes': gz_precos,
                'fundamentosBytes': len(fund_bytes), 'fundamentosGzipBytes': gz_fund}
    if fstats['orcamentoEsgotado'] or fstats['yahooInterrompido']:
        avisos.append(f"{fstats['pendentes']} tickers do pool ficaram sem fundamento atualizado "
                      f"({'Yahoo bloqueou' if fstats['yahooInterrompido'] else 'tempo esgotado'}); "
                      f"serão buscados nas próximas execuções.")
    if limite:
        avisos.append(f"Modo teste: só os primeiros {limite} tickers do universo.")

    stats = {
        'tickersPrecos': len(precos_brutos),
        'tickersFundamentos': len(fundamentos),
        'fundamentosComDados': fstats['comDados'],
        'fundamentosAtualizadosHoje': fstats['atualizadosHoje'],
        'alertasCriticos': fstats['alertasCriticos'],
    }
    gerado_em = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    manifesto = montar_manifesto(gerado_em, ultimo, anos, [n for n, _ in arquivos], stats, avisos, tamanhos)
    with open(os.path.join(args.saida, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)

    log("=== 6/6 Portão de qualidade ===")
    erros = portao_qualidade(manifesto, manifesto_anterior, fundamentos, hoje)
    duracao = time.monotonic() - t0
    total_bytes = bytes_precos + len(fund_bytes)

    linhas = [
        "## " + ("❌ Coleta BLOQUEADA pelo portão de qualidade" if erros else "✅ Coleta concluída"),
        "",
        "| Item | Valor |", "|---|---|",
        f"| Último pregão | {ultimo} |",
        f"| Universo{' (modo teste)' if limite else ''} | {len(universo)} tickers |",
        f"| Baixados do Yahoo | {n_baixados} (lotes com falha: {lotes_falhos}; duplicados removidos: {len(duplicados)}) |",
        f"| Tickers com preço (após pré-filtro) | {stats['tickersPrecos']} |",
        f"| Pool de fundamentos | {stats['tickersFundamentos']} (com dados: {stats['fundamentosComDados']}) |",
        f"| Fundamentos atualizados hoje | {stats['fundamentosAtualizadosHoje']} (falhas mantidas do cache: {fstats['falhasMantidasDoCache']}) |",
        f"| Alertas críticos (8-K) | {stats['alertasCriticos']} (falhas no radar: {fstats['radarFalhas']}) |",
        f"| Histórico | {anos} anos |",
        f"| Tamanho total | {mb(total_bytes):.1f} MB (comprimido: {mb(gz_precos + gz_fund):.1f} MB) em {len(arquivos)} arquivo(s) de preço |",
        f"| Tempo de execução | {duracao / 60:.1f} min |",
    ]
    if manifesto_anterior:
        linhas.append(f"| Execução anterior | {(manifesto_anterior.get('stats') or {}).get('tickersPrecos')} tickers, "
                      f"pregão {manifesto_anterior.get('ultimoPregao')} |")
    if avisos:
        linhas += ["", "### ⚠️ Avisos"] + [f"- {a}" for a in avisos]
    if erros:
        linhas += ["", "### Motivos do bloqueio (nada foi publicado; o site anterior continua no ar)"] + [f"- {e}" for e in erros]
    elif not args.sem_brasil and os.environ.get('SEM_BRASIL', '') != '1':
        # Brasil (IBOVESPA): roda depois e nunca bloqueia a publicação americana.
        import brasil
        linhas += brasil.coletar_brasil(os.path.join(args.saida, 'br'), args.url_publicado.rstrip('/') + '/br/', hoje)
    escrever_resumo(linhas)
    return 2 if erros else 0


if __name__ == '__main__':
    sys.exit(main())
