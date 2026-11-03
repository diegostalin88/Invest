import yfinance as yf
import pandas as pd
import requests
import json
from io import StringIO
import time
import random
import hashlib
import warnings

# Suprime avisos do Pandas sobre cópias fragmentadas para manter o terminal limpo
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

print("--- Script Iniciado: Gerador de Dados Quantitativo (Parquet & Auto-Adjust) ---")

nasdaq_listing_url = "http://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
other_listing_url = "http://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"  # NYSE, NYSE American, ARCA, BATS, etc.

# O universo bruto da Nasdaq/NYSE inclui ETFs, fundos e emissores com problema financeiro/regulatório
# misturados com ações comuns. O dashboard não tem como diferenciar isso depois (só enxerga preço/volume),
# então filtramos aqui na origem para reduzir "lixo" chegando no screener:
#  - EXCLUDE_ETFS: tira ETFs/fundos (ex: DGRW, SPY, QQQ) — o motor foi desenhado p/ pontuar ações individuais,
#    não cestas diversificadas, e um "score de confluência técnica" alto num ETF não tem o mesmo significado.
#  - EXCLUDE_FINANCIAL_STATUS_ISSUES: tira emissores com bandeira "Deficient/Delinquent/Bankrupt" na Nasdaq.
EXCLUDE_ETFS = True
EXCLUDE_FINANCIAL_STATUS_ISSUES = True

def normalize_for_yfinance(symbol):
    """yfinance espera hífen em vez de ponto para classes de ação (ex: BRK.B -> BRK-B)."""
    return symbol.strip().replace('.', '-')

print("Baixando a lista de tickers da Nasdaq...")
try:
    response = requests.get(nasdaq_listing_url, timeout=30)
    response.raise_for_status()
    data = StringIO(response.text)
    df_tickers = pd.read_csv(data, sep='|')
    df_tickers = df_tickers[:-1] # Remove a última linha que contém estatísticas do arquivo
    df_tickers.dropna(subset=['Symbol'], inplace=True)
    df_tickers['Symbol'] = df_tickers['Symbol'].astype(str)
    if 'Test Issue' in df_tickers.columns:
        df_tickers = df_tickers[df_tickers['Test Issue'] != 'Y']
    if EXCLUDE_ETFS and 'ETF' in df_tickers.columns:
        n_before = len(df_tickers)
        df_tickers = df_tickers[df_tickers['ETF'] != 'Y']
        print(f"  Removidos {n_before - len(df_tickers)} ETFs/fundos da lista Nasdaq (ex: DGRW, QQQ...).")
    if EXCLUDE_FINANCIAL_STATUS_ISSUES and 'Financial Status' in df_tickers.columns:
        n_before = len(df_tickers)
        df_tickers = df_tickers[df_tickers['Financial Status'] == 'N']  # N = Normal; demais = deficiente/delinquente/falido
        print(f"  Removidos {n_before - len(df_tickers)} emissores com problema financeiro/regulatório sinalizado.")

    # Filtra ativos de teste ou classes secundárias (contêm '$')
    df_tickers = df_tickers[~df_tickers['Symbol'].str.contains(r'\$')]
    tickers_nasdaq = [normalize_for_yfinance(s) for s in df_tickers['Symbol'].tolist()]
    print(f"Lista com {len(tickers_nasdaq)} tickers válidos da Nasdaq obtida com sucesso.")
except Exception as e:
    print(f"ERRO ao obter a lista de tickers da Nasdaq: {e}")
    exit()

# IMPORTANTE: a lista acima cobre SOMENTE ativos listados na Nasdaq. Sem isto, ações da NYSE/NYSE American/ARCA
# (ex: JPM, V, XOM, JNJ, BRK.B, PG, KO...) ficam de fora do screener, o que enviesa a seleção de "melhores ações"
# para apenas metade do mercado americano. Baixamos também a lista "otherlisted" e mesclamos.
print("Baixando a lista de tickers de outras bolsas (NYSE/AMEX/ARCA)...")
tickers_other = []
try:
    response = requests.get(other_listing_url, timeout=30)
    response.raise_for_status()
    data = StringIO(response.text)
    df_other = pd.read_csv(data, sep='|')
    df_other = df_other[:-1]
    df_other.dropna(subset=['ACT Symbol'], inplace=True)
    df_other['ACT Symbol'] = df_other['ACT Symbol'].astype(str)
    if 'Test Issue' in df_other.columns:
        df_other = df_other[df_other['Test Issue'] != 'Y']
    if EXCLUDE_ETFS and 'ETF' in df_other.columns:
        n_before = len(df_other)
        df_other = df_other[df_other['ETF'] != 'Y']
        print(f"  Removidos {n_before - len(df_other)} ETFs/fundos da lista NYSE/AMEX/ARCA.")
    df_other = df_other[~df_other['ACT Symbol'].str.contains(r'\$')]
    tickers_other = [normalize_for_yfinance(s) for s in df_other['ACT Symbol'].tolist()]
    print(f"Lista com {len(tickers_other)} tickers válidos de outras bolsas obtida com sucesso.")
except Exception as e:
    print(f"AVISO: falha ao obter tickers de outras bolsas ({e}). Prosseguindo apenas com Nasdaq.")

# Mescla e remove duplicatas mantendo a ordem original
tickers_nasdaq = list(dict.fromkeys(tickers_nasdaq + tickers_other))
print(f"Universo final combinado: {len(tickers_nasdaq)} tickers únicos (Nasdaq + outras bolsas).")

print(
    "\n[AVISO DE VIÉS DE SOBREVIVÊNCIA] Esta lista reflete os ativos listados HOJE. Empresas que faliram, "
    "foram deslistadas ou incorporadas nos últimos anos NÃO aparecem aqui, então qualquer backtest feito em cima "
    "destes dados tende a superestimar o retorno histórico do 'mercado' (só sobrou quem sobreviveu). Não há "
    "solução gratuita simples para isso; trate os resultados de backtest como otimistas, não como garantia.\n"
)

def create_chunks(lst, n):
    """Divide a lista de tickers em lotes (chunks) gerenciáveis."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def download_with_retry(chunk, max_retries=3):
    """Tenta baixar os dados com lógica de backoff exponencial em caso de erro 429."""
    for attempt in range(max_retries):
        try:
            # auto_adjust=True: CRÍTICO! Ajusta preços para splits e dividendos.
            dados = yf.download(
                chunk, 
                period="5y", 
                group_by='ticker', 
                progress=False, 
                auto_adjust=True 
            )
            return dados
        except Exception as e:
            wait_time = (2 ** attempt) + random.uniform(1, 3)
            print(f"  [Aviso] Falha no download (Tentativa {attempt+1}/{max_retries}). Erro: {e}. Aguardando {wait_time:.2f}s...")
            time.sleep(wait_time)
    return None

nome_arquivo_saida = 'dados_mercado_FINAL.json'  # renomeado: agora cobre Nasdaq + NYSE/AMEX/ARCA, não só Nasdaq
todos_os_dados = {} # Dicionário para armazenar os dados no formato exigido pelo frontend
processed_count = 0

# Limitando a um número menor para testes (remova o fatiamento em produção se desejar todos)
# tickers_to_process = tickers_nasdaq[:100]  # Descomente para testar rápido
tickers_to_process = tickers_nasdaq 
total_tickers = len(tickers_to_process)

chunk_size = 40 # Lotes ligeiramente menores para evitar gargalos de timeout
ticker_chunks = list(create_chunks(tickers_to_process, chunk_size))
num_chunks = len(ticker_chunks)

print(f"Preparando extração de {total_tickers} tickers em {num_chunks} lotes de ~{chunk_size}...")

for i, chunk in enumerate(ticker_chunks):
    print(f"\n--- Processando Lote {i+1}/{num_chunks} ({len(chunk)} tickers) ---")
    
    dados_lote = download_with_retry(chunk)
    
    if dados_lote is None or dados_lote.empty:
        print(f"  [Erro] Lote {i+1} falhou completamente após retentativas. Pulando.")
        continue

    # Lida com a diferença estrutural do yfinance quando se pede 1 vs múltiplos tickers
    if len(chunk) == 1:
        ticker = chunk[0]
        dados_acao_bruto = dados_lote.copy()
        tickers_no_lote = [ticker] if not dados_acao_bruto.empty else []
    else:
        tickers_no_lote = chunk

    for ticker in tickers_no_lote:
        processed_count += 1
        
        # Verifica se o ticker retornou dados na estrutura multi-index
        if len(chunk) > 1:
            if ticker not in dados_lote.columns.levels[0]:
                continue
            dados_acao_bruto = dados_lote[ticker].copy()
        
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        # Garante que as colunas existam (yfinance pode variar os retornos)
        if not all(col in dados_acao_bruto.columns for col in required_columns):
            continue

        # Mantém apenas as colunas essenciais e assegura tipagem numérica
        dados_acao_bruto = dados_acao_bruto[required_columns]
        for col in required_columns:
            dados_acao_bruto.loc[:, col] = pd.to_numeric(dados_acao_bruto[col], errors='coerce')

        # Remove NaNs nas colunas críticas e filtra volumes <= 0
        dados_limpos = dados_acao_bruto.dropna()
        dados_limpos = dados_limpos[dados_limpos['Volume'] > 0].copy()

        if dados_limpos.empty:
            continue

        # Adiciona a coluna do Ticker e reseta o index para transformar Data em coluna
        dados_limpos['Ticker'] = ticker
        dados_limpos.reset_index(inplace=True) 
        # Garante que a coluna de data se chame 'Date' e seja datetime
        dados_limpos.rename(columns={'index': 'Date', 'Date': 'Date'}, inplace=True)
        # BUG FIX: Convertendo para datetime pleno (M8[ns]) que é o padrão do Parquet, em vez de object/date.
        dados_limpos['Date'] = pd.to_datetime(dados_limpos['Date'])
        
        # Formatação para a estrutura JSON exigida pelo dashboard
        dados_formatados = {
            'dates': dados_limpos['Date'].dt.strftime('%Y-%m-%d').tolist(),
            'open': [round(x, 4) for x in dados_limpos['Open'].tolist()],
            'high': [round(x, 4) for x in dados_limpos['High'].tolist()],
            'low': [round(x, 4) for x in dados_limpos['Low'].tolist()],
            'close': [round(x, 4) for x in dados_limpos['Close'].tolist()],
            'volume': dados_limpos['Volume'].astype(int).tolist()
        }
        
        todos_os_dados[ticker] = dados_formatados
        print(f"({processed_count}/{total_tickers}) SUCESSO: {ticker} ({len(dados_limpos)} registros)")

    # Rate Limiting: Sleep randômico entre lotes para imitar comportamento humano e evitar ban
    if i < num_chunks - 1:
        sleep_time = random.uniform(2.5, 5.0)
        print(f"--- Pausa de segurança anti-ban: {sleep_time:.2f} segundos ---")
        time.sleep(sleep_time)

if not todos_os_dados:
    print("ERRO CRÍTICO: Nenhum dado foi processado e retornado. Verifique sua conexão e os bloqueios do Yahoo Finance.")
    exit()

print("\n--- Verificando anomalias do provedor (Ativos com históricos idênticos)... ---")
hashes = {}
duplicates = {}
for ticker, data in todos_os_dados.items():
    # Cria um hash representativo para achar lixo da API
    data_str = str(data['close']) + str(data['volume'])
    data_hash = hashlib.md5(data_str.encode()).hexdigest()
    
    if data_hash in hashes:
        original_ticker = hashes[data_hash]
        if original_ticker not in duplicates:
            duplicates[original_ticker] = []
        duplicates[original_ticker].append(ticker)
    else:
        hashes[data_hash] = ticker

if duplicates:
    print("AVISO: Detectados ativos com séries temporais matematicamente idênticas (Possível erro do Yahoo Finance).")
    for original_ticker, duplicate_tickers in duplicates.items():
        print(f"  - Histórico de '{original_ticker}' duplicado em: {', '.join(duplicate_tickers)}. Removendo duplicatas.")
        for dup_ticker in duplicate_tickers:
            if dup_ticker in todos_os_dados:
                del todos_os_dados[dup_ticker]

print(f"\n--- Salvando arquivo final em JSON... ---")
try:
    # Salvando sem espaços em branco extras (separators) para otimizar o carregamento no navegador
    with open(nome_arquivo_saida, 'w') as f:
        json.dump(todos_os_dados, f, separators=(',', ':'))
    
    print(f"SUCESSO ABSOLUTO! Arquivo '{nome_arquivo_saida}' salvo.")
    print(f"Total de Ativos Únicos: {len(todos_os_dados)}")
except Exception as e:
    print(f"ERRO ao salvar o arquivo JSON: {e}")

print("--- Script Concluído ---")
