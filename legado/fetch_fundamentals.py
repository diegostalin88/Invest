"""
fetch_fundamentals.py
----------------------
Complementa o fetch_data4.py: enquanto aquele script baixa preço/volume para o universo INTEIRO
de ações (milhares de tickers), este busca dados FUNDAMENTALISTAS (P/L, P/VP, ROE, Dívida/Patrimônio,
margem líquida, crescimento de receita) só para a LISTA CURTA de ativos que já sobreviveu ao Screener
técnico do dashboard (Módulo 1 -> botão "Exportar CSV").

Por que só a lista curta? Fontes gratuitas de fundamentos (Yahoo Finance via yfinance, SEC EDGAR) têm
limites de taxa e não têm bulk-download como o yfinance tem para preços. Rodar em milhares de tickers
tomaria horas e provavelmente levaria a bloqueio. Rodando só nas dezenas de ativos que passaram no
filtro técnico, o uso fica leve e 100% gratuito.

Fontes usadas (nesta ordem, por ticker):
  1) yfinance (Ticker.info) — rápido, sem chave de API, mas é raspagem do Yahoo Finance: às vezes
     vem incompleto ou falha (throttling). Fields: trailingPE/forwardPE, priceToBook, returnOnEquity,
     debtToEquity, profitMargins, revenueGrowth, sector, industry, marketCap.
  2) SEC EDGAR (data.sec.gov, API pública e oficial, sem chave) — usado como FALLBACK quando o
     yfinance falha ou vem com menos de 3 dos 6 indicadores-chave preenchidos. Usa os números brutos
     do último 10-K (receita, lucro líquido, patrimônio líquido, passivo total, lucro por ação) e
     calcula os índices manualmente. Só cobre empresas que arquivam na SEC (o que já é um filtro
     saudável contra ADRs obscuros e afins).

Além dos índices financeiros, para TODO ticker (não só no fallback) o script também busca de graça:
  - Radar de eventos corporativos: varre os 8-Ks recentes (~180 dias) da empresa na SEC procurando por
    fusão/aquisição, falência, risco de delisting ou restatement contábil — o tipo de evento que muda
    completamente o sentido de um sinal técnico (foi o caso da MKTX/MarketAxess, que seguiu "parecendo"
    um sinal de compra técnico mesmo já em processo de aquisição pela ICE).
  - Sinais extras do yfinance: próxima data de resultado trimestral, % vendido a descoberto (short
    float), preço-alvo médio e recomendação consensus de analistas, e posição em relação à máxima de
    52 semanas.

USO:
    python fetch_fundamentals.py screener_shortlist_2026-09-03.csv --precos dados_mercado_FINAL.json

    - Primeiro argumento: o CSV exportado pelo botão "Exportar CSV" do Módulo 1 (ou um .txt com um
      ticker por linha, ou uma lista separada por vírgula).
    - --precos (opcional, mas recomendado): o JSON de preços já gerado pelo fetch_data4.py. Usado para
      pegar o último preço de fechamento sem precisar de mais uma chamada de rede — necessário para
      calcular P/L e P/VP quando a fonte é a SEC EDGAR (que só dá números da empresa, não cotação).
      Sem isso, o script tenta obter o preço via yfinance como último recurso.

SAÍDA: fundamentos.json — um dicionário {ticker: {...índices..., fonte, atualizado_em}} para carregar
no Módulo 6 (Fundamentos) do dashboard.

AVISO IMPORTANTE: isto é uma ferramenta de apoio, não uma recomendação de investimento. Os números vêm
de fontes públicas gratuitas e podem estar desatualizados, incompletos ou (raramente) incorretos —
sempre confira no site de Relações com Investidores da empresa antes de decidir algo.
"""

import sys
import os
import re
import csv
import json
import glob
import time
import random
from datetime import datetime, timezone, timedelta

# Texto de uso guardado numa CONSTANTE normal (não no docstring do módulo) de propósito: em alguns
# ambientes Python (ex: rodando com a flag -OO, ou PYTHONOPTIMIZE=2 setado no shell/conda) o
# interpretador APAGA os docstrings e `__doc__` vira None — foi exatamente isso que aconteceu quando
# rodar o script sem argumento só imprimiu "None" em vez das instruções. Usando uma string normal,
# isso nunca depende de flag nenhuma de otimização.
USAGE_TEXT = """
fetch_fundamentals.py — busca P/L, P/VP, ROE, Dívida/Patrimônio, margem líquida e crescimento de
receita para a lista curta de ativos que sobrou do Screener (Módulo 1 do dashboard).

USO:
    python3 fetch_fundamentals.py <shortlist.csv> [--precos <dados_mercado_FINAL.json>]

    <shortlist.csv>  o CSV baixado pelo botão "Exportar CSV" do Módulo 1 (ou um .txt com um
                     ticker por linha, ou uma lista tipo "AAPL,MSFT,NVDA" direto no comando).
                     Pode ser só o nome do arquivo (o script procura na pasta atual, Downloads,
                     Desktop e pasta pessoal) ou o caminho completo.
    --precos         (opcional, mas recomendado) o JSON gerado pelo fetch_data4.py, usado para
                     pegar o preço mais recente sem chamada de rede extra.

EXEMPLO:
    python3 fetch_fundamentals.py screener_shortlist_2026-09-03.csv --precos dados_mercado_FINAL.json

SAÍDA: fundamentos.json na pasta onde você rodou o comando — carregue esse arquivo no Módulo 6
(Fundamentos) do dashboard.
"""

# -----------------------------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------------------------
# A SEC EXIGE um User-Agent identificável (nome do app + e-mail de contato) para liberar acesso à
# API pública. Requisições com User-Agent genérico/vazio podem ser bloqueadas. Preencha com seus dados:
SEC_USER_AGENT = "AnalisadorQuantitativoPessoal contato@example.com"  # <-- troque pelo seu e-mail

SLEEP_BETWEEN_TICKERS = (0.6, 1.4)  # segundos (min, max) — educado com Yahoo e SEC, shortlist é pequena
MIN_FIELDS_TO_TRUST_YFINANCE = 3     # de 6 campos-chave; abaixo disso, tenta o fallback da SEC também

try:
    import requests
except ImportError:
    print("ERRO: biblioteca 'requests' não encontrada. Instale com: pip install requests")
    sys.exit(1)

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    print("AVISO: 'yfinance' não encontrado (pip install yfinance). Vou depender só da SEC EDGAR.")
    HAS_YFINANCE = False


# -----------------------------------------------------------------------------------------------
# 1) LER A LISTA CURTA DE TICKERS
# -----------------------------------------------------------------------------------------------
def find_file_in_common_locations(arg):
    """Tenta localizar `arg` tal como foi passado e, se for um caminho relativo, também em locais
    comuns onde arquivos baixados costumam parar (pasta atual, Downloads, Desktop, pasta pessoal).
    Devolve o caminho resolvido, ou None se não achou em lugar nenhum. Não decide se isso é um erro —
    quem chama decide (ver looks_like_path / parse_ticker_arg / load_price_lookup)."""
    candidates = [arg, os.path.expanduser(arg)]
    if not os.path.isabs(arg):
        home = os.path.expanduser('~')
        candidates += [
            os.path.join(os.getcwd(), arg),
            os.path.join(home, 'Downloads', arg),
            os.path.join(home, 'Desktop', arg),
            os.path.join(home, arg),
        ]
    seen = []
    for c in candidates:
        if c not in seen:
            seen.append(c)
        if os.path.isfile(c):
            return c
    return None


def looks_like_path(arg, extensions):
    return arg.lower().endswith(extensions) or ('/' in arg) or ('\\' in arg)


def _file_not_found_message(arg):
    tried = "\n  - ".join(dict.fromkeys([arg, os.path.expanduser(arg), os.path.join(os.getcwd(), arg)]))
    return (
        f"\nERRO: '{arg}' parece ser um arquivo, mas não encontrei em nenhum destes caminhos (nem em Downloads/Desktop):\n  - {tried}\n\n"
        f"Confirme onde o arquivo foi salvo e use o caminho completo entre aspas, por exemplo:\n"
        f'  python fetch_fundamentals.py "C:\\Users\\SeuNome\\Downloads\\{os.path.basename(arg)}"   (Windows)\n'
        f'  python fetch_fundamentals.py "~/Downloads/{os.path.basename(arg)}"                     (Mac/Linux)\n'
    )


def parse_ticker_arg(arg):
    """Aceita: caminho para CSV do 'Exportar CSV', caminho para .txt (1 ticker por linha),
    ou uma string 'AAPL,MSFT,NVDA' direto na linha de comando.

    Este é um argumento OBRIGATÓRIO: se `arg` claramente parece um caminho de arquivo (extensão
    .csv/.txt ou contém uma barra de diretório) mas não é encontrado em lugar nenhum, o script para
    com um erro claro — em vez de silenciosamente tratar o nome do arquivo como se fosse um ticker
    (esse era o bug original: 'screener_shortlist_2026-09-03.csv' virava um "ticker" de um ativo só,
    porque o arquivo não tinha sido achado no diretório onde o script rodou, e o script seguia
    processando aquele nome de arquivo como se fosse um símbolo de ação, sem avisar nada)."""
    resolved_path = find_file_in_common_locations(arg)
    if not resolved_path and looks_like_path(arg, ('.csv', '.txt')):
        print(_file_not_found_message(arg))
        sys.exit(1)
    if resolved_path:
        print(f"  Lendo tickers de: {os.path.abspath(resolved_path)}")
        tickers = []
        # utf-8-sig: lida de graça com o BOM que o Excel às vezes adiciona ao resalvar um CSV no Windows
        with open(resolved_path, newline='', encoding='utf-8-sig') as f:
            sniff = f.read(2048)
            f.seek(0)
            if ',' in sniff and ('Ticker' in sniff or re.search(r'^[A-Z.\-]{1,10},', sniff)):
                reader = csv.reader(f)
                header = next(reader, None)
                ticker_col = 0
                if header and any(h.strip().lower() == 'ticker' for h in header):
                    ticker_col = [h.strip().lower() for h in header].index('ticker')
                else:
                    f.seek(0); reader = csv.reader(f)  # sem header reconhecível, primeira coluna
                for row in reader:
                    if row and row[ticker_col].strip():
                        tickers.append(row[ticker_col].strip().upper())
            else:
                for line in f:
                    line = line.strip()
                    if line:
                        tickers.append(line.upper())
        if not tickers:
            print(f"AVISO: '{resolved_path}' foi encontrado e lido, mas nenhum ticker foi extraído dele. Confira o conteúdo do arquivo.")
        return sorted(set(tickers))
    # não é arquivo -> trata como lista separada por vírgula
    return sorted(set(t.strip().upper() for t in arg.split(',') if t.strip()))


# -----------------------------------------------------------------------------------------------
# 2) PREÇO MAIS RECENTE (para calcular P/L e P/VP quando a fonte é a SEC, que não dá cotação)
# -----------------------------------------------------------------------------------------------
def load_price_lookup(precos_json_path):
    """Carrega o JSON de preços já gerado pelo fetch_data4.py e devolve {ticker: ultimo_close}."""
    if not precos_json_path:
        return {}
    resolved = find_file_in_common_locations(precos_json_path)  # mesma busca esperta (Downloads, Desktop, etc.)
    if not resolved:
        # --precos é OPCIONAL, então aqui só avisa e segue (não é motivo para abortar o script inteiro)
        print(f"  AVISO: '--precos {precos_json_path}' não encontrado (tentei também em Downloads/Desktop). Seguindo sem preços de referência (vou tentar via yfinance quando precisar).")
        return {}
    precos_json_path = resolved
    print(f"  Lendo preços de: {os.path.abspath(precos_json_path)}")
    try:
        with open(precos_json_path, encoding='utf-8') as f:
            data = json.load(f)
        lookup = {}
        for ticker, series in data.items():
            closes = series.get('close') or []
            if closes:
                lookup[ticker] = closes[-1]
        print(f"  Preços de referência carregados de '{precos_json_path}' para {len(lookup)} tickers.")
        return lookup
    except Exception as e:
        print(f"  AVISO: não consegui ler '{precos_json_path}' ({e}). Vou depender de outras fontes de preço.")
        return {}


def get_price_via_yfinance(ticker):
    if not HAS_YFINANCE:
        return None
    try:
        fi = yf.Ticker(ticker).fast_info
        price = fi.get('lastPrice') or fi.get('last_price')
        return float(price) if price else None
    except Exception:
        return None


# -----------------------------------------------------------------------------------------------
# 3) FONTE PRIMÁRIA: yfinance
# -----------------------------------------------------------------------------------------------
def fetch_from_yfinance(ticker):
    """Retorna um dict com os campos-chave (ou None quando indisponível) e o preço, se conseguir."""
    if not HAS_YFINANCE:
        return None
    try:
        t = yf.Ticker(ticker)
        try:
            info = t.get_info()  # yfinance >= 0.2.x
        except AttributeError:
            info = t.info  # versões antigas
        if not info or not isinstance(info, dict):
            return None

        result = {
            'pe': info.get('trailingPE') or info.get('forwardPE'),
            'pb': info.get('priceToBook'),
            'roe': info.get('returnOnEquity'),  # fração, ex: 0.18 = 18%
            'debtToEquity': (info.get('debtToEquity') / 100.0) if info.get('debtToEquity') is not None else None,  # Yahoo já retorna em %, então x/100 vira "vezes"
            'netMargin': info.get('profitMargins'),  # fração
            'revenueGrowth': info.get('revenueGrowth'),  # fração (YoY, geralmente trimestral)
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'marketCap': info.get('marketCap'),
            'longName': info.get('longName') or info.get('shortName'),
            'price': info.get('currentPrice') or info.get('regularMarketPrice'),
            # Sinais extras pra apoiar a decisão de swing trade (todos de graça, já vêm no mesmo .info):
            'shortPercentOfFloat': info.get('shortPercentOfFloat'),  # fração, ex: 0.08 = 8% do float vendido a descoberto
            'shortRatio': info.get('shortRatio'),  # "days to cover"
            'targetMeanPrice': info.get('targetMeanPrice'),  # preço-alvo médio dos analistas (não é garantia de nada, é só consenso)
            'recommendationKey': info.get('recommendationKey'),  # 'buy', 'hold', 'sell', etc. (consenso, idem)
            'fiftyTwoWeekHigh': info.get('fiftyTwoWeekHigh'),
            'fiftyTwoWeekLow': info.get('fiftyTwoWeekLow'),
        }
        result['nextEarningsDate'] = get_next_earnings_date(t)
        return result
    except Exception as e:
        print(f"    [yfinance] falhou para {ticker}: {e}")
        return None


def get_next_earnings_date(yf_ticker_obj):
    """Tenta achar a próxima data de resultado trimestral. A API do yfinance pra isso mudou de forma
    algumas vezes entre versões, então tenta os dois formatos mais comuns antes de desistir."""
    try:
        cal = yf_ticker_obj.calendar
        if cal is None:
            return None
        # Em versões recentes, `calendar` é um dict: {'Earnings Date': [date(...), date(...)], ...}
        if isinstance(cal, dict):
            dates = cal.get('Earnings Date')
            if dates:
                d = dates[0] if isinstance(dates, (list, tuple)) else dates
                return d.isoformat() if hasattr(d, 'isoformat') else str(d)
        # Em versões antigas, `calendar` é um DataFrame com uma linha 'Earnings Date'
        elif hasattr(cal, 'loc') and 'Earnings Date' in getattr(cal, 'index', []):
            d = cal.loc['Earnings Date'][0]
            return d.isoformat() if hasattr(d, 'isoformat') else str(d)
    except Exception:
        pass
    return None


def count_key_fields(d):
    if not d:
        return 0
    keys = ['pe', 'pb', 'roe', 'debtToEquity', 'netMargin', 'revenueGrowth']
    return sum(1 for k in keys if d.get(k) is not None)


# -----------------------------------------------------------------------------------------------
# 4) FONTE DE FALLBACK: SEC EDGAR (dados brutos de 10-K/10-Q, calculamos os índices na mão)
# -----------------------------------------------------------------------------------------------
_sec_ticker_map_cache = None

def load_sec_ticker_map():
    """Baixa (uma vez) o mapa ticker -> CIK que a própria SEC disponibiliza publicamente."""
    global _sec_ticker_map_cache
    if _sec_ticker_map_cache is not None:
        return _sec_ticker_map_cache
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        resp = requests.get(url, headers={'User-Agent': SEC_USER_AGENT}, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
        mapping = {}
        for _, row in raw.items():
            mapping[row['ticker'].upper()] = str(row['cik_str']).zfill(10)
        _sec_ticker_map_cache = mapping
        print(f"  Mapa de tickers da SEC carregado ({len(mapping)} empresas).")
        return mapping
    except Exception as e:
        print(f"  AVISO: não consegui baixar o mapa de tickers da SEC ({e}). Fallback SEC ficará indisponível.")
        _sec_ticker_map_cache = {}
        return {}


def _extract_latest_annual_facts(facts_json, tags, unit='USD'):
    """Dado um dict de 'facts'->'us-gaap' da SEC e uma lista de tags candidatas (em ordem de
    preferência), devolve [(valor_mais_recente, valor_ano_anterior)] usando os pontos de formulário
    10-K (fp='FY'). Para no primeiro tag que tiver dados utilizáveis."""
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
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        resp = requests.get(url, headers={'User-Agent': SEC_USER_AGENT}, timeout=20)
        if resp.status_code != 200:
            return None
        facts = resp.json()
    except Exception as e:
        print(f"    [SEC EDGAR] falhou para {ticker}: {e}")
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
        # Aproximação: Passivo Total / Patrimônio Líquido (mais amplo que só dívida com juros,
        # mas é o que dá pra montar de graça com os dados públicos da SEC sem parsing custoso demais)
        result['debtToEquity'] = liabilities / equity
    if revenue and net_income is not None and revenue != 0:
        result['netMargin'] = net_income / revenue
    if revenue and revenue_prior and revenue_prior != 0:
        result['revenueGrowth'] = (revenue - revenue_prior) / revenue_prior
    if price and equity and shares and shares != 0:
        book_value_per_share = equity / shares
        if book_value_per_share > 0:
            result['pb'] = price / book_value_per_share

    return result


# -----------------------------------------------------------------------------------------------
# 4b) RADAR DE EVENTOS CORPORATIVOS (SEC EDGAR, formulário 8-K)
# -----------------------------------------------------------------------------------------------
# Por que isso importa: um ativo pode continuar "pontuando bem" no Screener técnico mesmo depois de
# anunciar uma fusão/aquisição, pedido de falência, ou risco de ser deslistado — o motor de preço/volume
# não tem como saber disso sozinho. Foi exatamente o que aconteceu com a MKTX (MarketAxess), que seguiu
# disparando sinais técnicos normais mesmo já estando sob acordo de aquisição pela ICE. O formulário 8-K
# é o que empresas de capital aberto nos EUA são OBRIGADAS a arquivar na SEC em até poucos dias úteis
# após um evento relevante, e o índice de "items" de cada 8-K já vem catalogado gratuitamente pela API
# pública data.sec.gov/submissions — não precisa nem abrir o texto do documento pra saber o tipo de evento.
CRITICAL_8K_ITEMS = {
    '1.03': 'Falência ou recuperação judicial',
    '3.01': 'Risco de ser deslistado da bolsa',
    '4.02': 'Não-confiabilidade de demonstrações financeiras anteriores (restatement)',
}
WATCH_8K_ITEMS = {
    '1.01': 'Entrada em acordo material relevante (pode ser fusão/aquisição, entre outras coisas)',
    '2.01': 'Conclusão de aquisição ou venda de ativos relevantes',
}
CORPORATE_EVENTS_LOOKBACK_DAYS = 180  # só considera 8-Ks arquivados nos últimos ~6 meses


def fetch_corporate_events(ticker, cik, sec_map=None):
    """Consulta data.sec.gov/submissions/CIK....json (gratuito, sem chave) e devolve os 8-Ks recentes
    cujo(s) item(ns) batem com CRITICAL_8K_ITEMS ou WATCH_8K_ITEMS. Devolve {'nivel': 'critico'|'atencao'|None,
    'eventos': [...]}."""
    if not cik:
        return {'nivel': None, 'eventos': []}
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        resp = requests.get(url, headers={'User-Agent': SEC_USER_AGENT}, timeout=20)
        if resp.status_code != 200:
            return {'nivel': None, 'eventos': []}
        data = resp.json()
    except Exception as e:
        print(f"    [SEC EDGAR/8-K] falhou para {ticker}: {e}")
        return {'nivel': None, 'eventos': []}

    recent = data.get('filings', {}).get('recent', {})
    forms = recent.get('form', [])
    dates = recent.get('filingDate', [])
    items_list = recent.get('items', [])
    accessions = recent.get('accessionNumber', [])
    primary_docs = recent.get('primaryDocument', [])
    cik_int = str(int(cik))  # a URL do documento usa o CIK sem zeros à esquerda

    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=CORPORATE_EVENTS_LOOKBACK_DAYS)).isoformat()

    eventos = []
    nivel = None
    for i, form in enumerate(forms):
        if form != '8-K':
            continue
        filing_date = dates[i] if i < len(dates) else None
        if not filing_date or filing_date < cutoff:
            continue
        raw_items = (items_list[i] if i < len(items_list) else '') or ''
        item_codes = [x.strip() for x in raw_items.split(',') if x.strip()]
        matched = [(code, CRITICAL_8K_ITEMS[code]) for code in item_codes if code in CRITICAL_8K_ITEMS]
        matched += [(code, WATCH_8K_ITEMS[code]) for code in item_codes if code in WATCH_8K_ITEMS]
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
    return {'nivel': nivel, 'eventos': eventos}


# -----------------------------------------------------------------------------------------------
# 5) ORQUESTRAÇÃO
# -----------------------------------------------------------------------------------------------
def build_fundamentals(tickers, price_lookup):
    sec_map = None  # só baixa o mapa da SEC se algum ticker realmente precisar (lazy)
    out = {}
    stats = {'yfinance': 0, 'sec_edgar': 0, 'combinado': 0, 'indisponivel': 0}

    for idx, ticker in enumerate(tickers, 1):
        print(f"[{idx}/{len(tickers)}] {ticker}...")
        yf_data = fetch_from_yfinance(ticker)
        n_fields = count_key_fields(yf_data)  # só os 6 índices-chave -> decide SE aciona o fallback da SEC
        used_sources = set()
        if yf_data and any(v is not None for v in yf_data.values()):
            used_sources.add('yfinance')  # marca 'yfinance' mesmo que só tenha vindo setor/indústria/nome

        final = dict(yf_data) if yf_data else {
            'pe': None, 'pb': None, 'roe': None, 'debtToEquity': None, 'netMargin': None,
            'revenueGrowth': None, 'sector': None, 'industry': None, 'marketCap': None, 'longName': None, 'price': None,
        }

        price = price_lookup.get(ticker) or final.get('price') or get_price_via_yfinance(ticker)

        # O mapa de tickers->CIK da SEC agora é sempre necessário (não só no fallback de índices),
        # porque o radar de eventos corporativos roda pra TODO ticker, independente de yfinance ter
        # vindo completo ou não — o alerta de fusão/falência/delisting importa igual nos dois casos.
        if sec_map is None:
            sec_map = load_sec_ticker_map()
        cik = sec_map.get(ticker)

        if n_fields < MIN_FIELDS_TO_TRUST_YFINANCE:
            sec_data = fetch_from_sec_edgar(ticker, price, sec_map)
            if sec_data:
                used_sources.add('sec_edgar')
                for key, val in sec_data.items():
                    if final.get(key) is None and val is not None:
                        final[key] = val

        eventos_info = fetch_corporate_events(ticker, cik, sec_map)
        final['alertaEvento'] = eventos_info['nivel']  # None | 'atencao' | 'critico'
        final['eventosCorporativos'] = eventos_info['eventos']
        if eventos_info['nivel'] == 'critico':
            print(f"    ⚠️⚠️  {ticker}: evento corporativo CRÍTICO recente (bancarrota/delisting/restatement) — ver eventosCorporativos")
        elif eventos_info['nivel'] == 'atencao':
            print(f"    ⚠️  {ticker}: evento corporativo recente pra revisar (acordo material/fusão) — ver eventosCorporativos")

        final['price'] = price
        final['atualizadoEm'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if 'yfinance' in used_sources and 'sec_edgar' in used_sources:
            final['fonte'] = 'combinado'; stats['combinado'] += 1
        elif 'yfinance' in used_sources:
            final['fonte'] = 'yfinance'; stats['yfinance'] += 1
        elif 'sec_edgar' in used_sources:
            final['fonte'] = 'sec_edgar'; stats['sec_edgar'] += 1
        else:
            final['fonte'] = 'indisponivel'; stats['indisponivel'] += 1

        out[ticker] = final
        time.sleep(random.uniform(*SLEEP_BETWEEN_TICKERS))

    print("\n--- Resumo das fontes ---")
    for k, v in stats.items():
        print(f"  {k}: {v} ativo(s)")
    return out


def suggest_likely_files():
    """Procura, na pasta atual/Downloads/Desktop, arquivos com cara de shortlist do Screener ou de
    preços do fetch_data4.py, pra sugerir um comando pronto quando o usuário esquece o argumento."""
    search_dirs = [os.getcwd(), os.path.join(os.path.expanduser('~'), 'Downloads'), os.path.join(os.path.expanduser('~'), 'Desktop')]
    shortlist_hits, precos_hits = [], []
    for d in search_dirs:
        shortlist_hits += glob.glob(os.path.join(d, 'screener_shortlist*.csv'))
        precos_hits += glob.glob(os.path.join(d, 'dados_*FINAL*.json')) + glob.glob(os.path.join(d, 'dados_mercado*.json'))
    shortlist_hits = sorted(set(shortlist_hits), key=os.path.getmtime, reverse=True) if shortlist_hits else []
    precos_hits = sorted(set(precos_hits), key=os.path.getmtime, reverse=True) if precos_hits else []
    if shortlist_hits:
        print(f"Encontrei possível shortlist: {shortlist_hits[0]}")
        cmd = f'python3 fetch_fundamentals.py "{shortlist_hits[0]}"'
        if precos_hits:
            print(f"E possível arquivo de preços: {precos_hits[0]}")
            cmd += f' --precos "{precos_hits[0]}"'
        print(f"\nTente rodar:\n  {cmd}\n")
    else:
        print("Não encontrei nenhum 'screener_shortlist*.csv' na pasta atual, Downloads ou Desktop.")
        print("Confirme que você já clicou em 'Exportar CSV' no Módulo 1 do dashboard e sabe onde o arquivo foi salvo.\n")


def main():
    if len(sys.argv) < 2:
        print(USAGE_TEXT)
        suggest_likely_files()
        sys.exit(1)

    ticker_arg = sys.argv[1]
    precos_path = None
    if '--precos' in sys.argv:
        i = sys.argv.index('--precos')
        if i + 1 < len(sys.argv):
            precos_path = sys.argv[i + 1]

    tickers = parse_ticker_arg(ticker_arg)
    if not tickers:
        print(f"ERRO: nenhum ticker encontrado a partir de '{ticker_arg}'.")
        sys.exit(1)
    print(f"--- fetch_fundamentals.py: {len(tickers)} ticker(s) na lista curta ---")

    price_lookup = load_price_lookup(precos_path)

    if SEC_USER_AGENT.endswith('example.com'):
        print(
            "\n[AVISO] SEC_USER_AGENT ainda está com o e-mail de exemplo. A SEC pode bloquear ou "
            "limitar chamadas sem um contato real identificado — edite a constante SEC_USER_AGENT "
            "no topo deste arquivo antes de rodar em volume.\n"
        )

    fundamentals = build_fundamentals(tickers, price_lookup)

    output_path = 'fundamentos.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fundamentals, f, ensure_ascii=False, indent=2)
    print(f"\nSUCESSO! Arquivo salvo em: {os.path.abspath(output_path)}")
    print(f"(Isso é dentro da pasta onde você rodou este comando — rode 'pwd' (Mac/Linux) ou 'cd' sozinho (Windows) pra confirmar.)")
    print(f"Contém {len(fundamentals)} ativos. Carregue esse arquivo no Módulo 6 (Fundamentos) do dashboard.")
    print(
        "\nLEMBRETE: estes números vêm de fontes públicas gratuitas (Yahoo Finance / SEC EDGAR) e podem "
        "estar incompletos, defasados por um trimestre, ou (raramente) errados. Isto é uma ferramenta de "
        "apoio à análise, não uma recomendação de investimento — confira sempre a fonte primária."
    )


if __name__ == '__main__':
    main()
