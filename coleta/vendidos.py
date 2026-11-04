"""Posições vendidas (base do alerta de "short squeeze").

- EUA: short interest da FINRA (publicado duas vezes por mês), API pública
  https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest
- Brasil: posições em aberto de empréstimo (aluguel) de ações da B3, arquivo diário
  "LendingOpenPositionFile" (https://arquivos.b3.com.br/).

Grava <saida>/vendidos.json e <saida>/br/vendidos.json no formato
    {"fonte": ..., "data": "AAAA-MM-DD", "geradoEm": ..., "ativos": {"TICKER": {"qtd": N, ...}}}
Só entram os tickers que o app tem preço. Qualquer falha só gera aviso: nunca bloqueia a publicação.
O app calcula "dias para zerar" = qtd vendida / volume médio de 20 pregões, com os próprios preços.

Uso: python coleta/vendidos.py --saida site/data [--b3-bruto b3-cache/aluguel_b3.json]
     python coleta/vendidos.py --somente-b3-bruto b3-cache/aluguel_b3.json   (no coletor no Brasil)

A B3 bloqueia o servidor do GitHub (fora do Brasil). Por isso um coletor numa máquina no Brasil
(workflow aluguel-b3.yml) baixa o arquivo bruto, com todos os papéis, e a coleta principal usa essa
cópia se ela tiver até B3_BRUTO_MAX_DIAS dias; senão tenta a B3 direto.
"""
import argparse
import csv
import io
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests

FINRA_URL = 'https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest'
B3_PEDIDO_URL = 'https://arquivos.b3.com.br/api/download/requestname'
B3_DOWNLOAD_URL = 'https://arquivos.b3.com.br/api/download/'
UA = {'User-Agent': 'Mozilla/5.0 (InvestApp)'}


def log(msg):
    print(msg, flush=True)


def tickers_com_preco(pasta):
    """Lê o manifesto e os arquivos de preço já gravados pela coleta e devolve os tickers."""
    try:
        with open(os.path.join(pasta, 'manifest.json'), encoding='utf-8') as f:
            manifesto = json.load(f)
    except (OSError, ValueError):
        return set()
    tickers = set()
    for nome in manifesto.get('arquivosPrecos', []):
        try:
            with open(os.path.join(pasta, nome), encoding='utf-8') as f:
                obj = json.load(f)
        except (OSError, ValueError):
            continue
        tickers.update((obj.get('ativos') or {}) if obj.get('formato') == 'colunar-v1' else obj)
    return tickers


def _numero(txt, inteiro=False):
    """Converte '1.234.567', '1234567', '1234,5' ou 1234 em float. inteiro=True: ponto é sempre milhar."""
    if isinstance(txt, (int, float)):
        return float(txt)
    s = str(txt or '').strip()
    if not s:
        return 0.0
    if inteiro:
        return float(s.split(',')[0].replace('.', '') or 0)
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif s.count('.') > 1:
        s = s.replace('.', '')
    return float(s)


# ---------------- EUA: FINRA ----------------
def _erro_http(resp, onde):
    """raise_for_status com o começo da resposta (a FINRA explica no corpo o que está errado)."""
    if resp.status_code >= 400:
        corpo = (getattr(resp, 'text', '') or '')[:300].replace('\n', ' ')
        raise RuntimeError(f'{onde}: HTTP {resp.status_code} {corpo}'.strip())


def _finra_post(corpo, sessao):
    resp = sessao.post(FINRA_URL, json=corpo, timeout=60,
                       headers={**UA, 'Accept': 'application/json', 'Content-Type': 'application/json'})
    _erro_http(resp, 'FINRA')
    return resp.json() if resp.text.strip() else []


def _finra_ultima_data(sessao, hoje):
    """Data de liquidação mais recente publicada. Tenta ordenar; se a API recusar, testa dia a dia
    (as datas são por volta do dia 15 e do fim de cada mês, e saem uns 8 pregões depois)."""
    try:
        ultimo = _finra_post({'limit': 1, 'sortFields': ['-settlementDate']}, sessao)
        if ultimo and ultimo[0].get('settlementDate'):
            return ultimo[0]['settlementDate']
    except Exception as e:  # noqa: BLE001 - segue para o plano B
        log(f'FINRA: ordenação recusada ({e}); procurando a data dia a dia')
    for k in range(5, 50):
        dia = (hoje - timedelta(days=k)).isoformat()
        linhas = _finra_post({'limit': 1, 'compareFilters': [
            {'compareType': 'EQUAL', 'fieldName': 'settlementDate', 'fieldValue': dia}]}, sessao)
        if linhas:
            return dia
    raise RuntimeError('FINRA não tem nenhuma data de liquidação nos últimos 50 dias')


def baixar_finra(universo, sessao=requests, hoje=None):
    data_liq = _finra_ultima_data(sessao, hoje or date.today())
    ativos, offset, lote = {}, 0, 5000
    while True:
        linhas = _finra_post({'limit': lote, 'offset': offset,
                              'compareFilters': [{'compareType': 'EQUAL', 'fieldName': 'settlementDate',
                                                  'fieldValue': data_liq}]}, sessao)
        for l in linhas:
            t = (l.get('symbolCode') or '').strip().upper()
            if t in universo and l.get('currentShortPositionQuantity'):
                ativos[t] = {'qtd': int(l['currentShortPositionQuantity']),
                             'qtdAnterior': int(l.get('previousShortPositionQuantity') or 0),
                             'variacaoPct': l.get('changePercent'),
                             'diasFinra': l.get('daysToCoverQuantity')}
        if len(linhas) < lote or offset > 200000:
            break
        offset += lote
    return {'fonte': 'FINRA (short interest)', 'data': data_liq, 'ativos': ativos}


# ---------------- Brasil: B3 (aluguel) ----------------
B3_TABELA_URL = 'https://arquivos.b3.com.br/tabelas/table/LendingOpenPosition/{d}/{d}/{p}'
UA_NAVEGADOR = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/130.0 Safari/537.36', 'Accept': '*/*', 'Accept-Language': 'pt-BR,pt;q=0.9'}


def _ler_csv_b3(texto):
    """O arquivo tem uma linha de título antes do cabeçalho; procura o cabeçalho pelo nome da coluna."""
    linhas = texto.splitlines()
    inicio = next((k for k, l in enumerate(linhas) if 'TckrSymb' in l), None)
    if inicio is None:
        raise ValueError('cabeçalho TckrSymb não encontrado no arquivo da B3')
    leitor = csv.DictReader(io.StringIO('\n'.join(linhas[inicio:])), delimiter=';')
    return list(leitor)


def _get_com_nova_tentativa(sessao, url, tentativas=2, **k):
    erro = None
    for _ in range(tentativas):
        try:
            resp = sessao.get(url, headers=UA_NAVEGADOR, timeout=90, **k)
            _erro_http(resp, 'B3')
            return resp
        except Exception as e:  # noqa: BLE001 - 504 da B3 costuma ser passageiro
            erro = e
    raise erro


def _token_b3(obj):
    """A B3 respondia {"token": ...}; desde 2026 responde {"redirectUrl": "~/download?token=..."}."""
    if obj.get('token'):
        return obj['token']
    url = obj.get('redirectUrl') or ''
    return url.split('token=', 1)[1] if 'token=' in url else None


def baixar_b3_arquivo(dia, sessao=requests):
    """Caminho 1: arquivo CSV (pede um token e baixa com ele)."""
    pedido = _get_com_nova_tentativa(sessao, B3_PEDIDO_URL, params={'fileName': 'LendingOpenPositionFile',
                                                                     'date': dia.isoformat()})
    token = _token_b3(pedido.json() or {})
    if not token:
        raise ValueError('B3 não devolveu token')
    # A página da B3 monta o endereço com o token cru (sem codificar); fazemos igual.
    arq = _get_com_nova_tentativa(sessao, B3_DOWNLOAD_URL + '?token=' + token)
    try:
        texto = arq.content.decode('utf-8')
    except UnicodeDecodeError:
        texto = arq.content.decode('latin-1')
    return _ler_csv_b3(texto)


def baixar_b3_tabela(dia, sessao=requests):
    """Caminho 2: a mesma tabela em JSON, paginada (é o que a página de consultas da B3 usa)."""
    linhas, pagina, total = [], 1, 1
    while pagina <= total and pagina <= 200:
        obj = _get_com_nova_tentativa(sessao, B3_TABELA_URL.format(d=dia.isoformat(), p=pagina), tentativas=1).json()
        tab = obj.get('table') or obj
        nomes = [c.get('name') if isinstance(c, dict) else c for c in (tab.get('columns') or [])]
        for v in tab.get('values') or []:
            linhas.append(dict(zip(nomes, v)) if isinstance(v, list) else v)
        total = int(obj.get('pageCount') or tab.get('pageCount') or 1)
        pagina += 1
    if not linhas:
        raise ValueError('tabela da B3 vazia')
    return linhas


def baixar_b3_um_dia(dia, sessao=requests):
    try:
        return baixar_b3_arquivo(dia, sessao)
    except Exception as e1:  # noqa: BLE001
        try:
            return baixar_b3_tabela(dia, sessao)
        except Exception as e2:  # noqa: BLE001
            raise RuntimeError(f'{dia}: arquivo ({e1}); tabela ({e2})') from e2


def baixar_b3(universo, hoje, sessao=requests, dias_atras=5):
    ultimo_erro = None
    for k in range(dias_atras + 1):
        dia = hoje - timedelta(days=k)
        if dia.weekday() >= 5:
            continue
        try:
            linhas = baixar_b3_um_dia(dia, sessao)
        except Exception as e:  # tenta o dia útil anterior
            log(f'Vendidos Brasil: {e}')
            ultimo_erro = e
            continue
        ativos = {}
        for l in linhas:
            t = (l.get('TckrSymb') or '').strip().upper()
            if universo is None or t in universo:
                qtd = _numero(l.get('BalQty'), inteiro=isinstance(l.get('BalQty'), str))
                if qtd > 0:
                    a = ativos.setdefault(t, {'qtd': 0, 'valor': 0.0})
                    a['qtd'] += int(qtd)
                    a['valor'] += _numero(l.get('BalVal'))
        if ativos:
            for a in ativos.values():
                a['valor'] = round(a['valor'], 2)
            return {'fonte': 'B3 (aluguel de ações, posições em aberto)', 'data': dia.isoformat(), 'ativos': ativos}
        ultimo_erro = ValueError(f'arquivo de {dia} sem nenhum papel da carteira')
    raise RuntimeError(f'B3 indisponível nos últimos {dias_atras} dias: {ultimo_erro}')


B3_BRUTO_MAX_DIAS = 5


def ler_b3_bruto(caminho, universo, hoje):
    """Usa a cópia baixada pelo coletor no Brasil, se existir e for recente; devolve None se não servir."""
    try:
        with open(caminho, encoding='utf-8') as f:
            bruto = json.load(f)
        dia = date.fromisoformat(bruto['data'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if (hoje - dia).days > B3_BRUTO_MAX_DIAS:
        log(f'Vendidos Brasil: cópia do coletor no Brasil é de {dia}, velha demais; ignorada.')
        return None
    ativos = {t: a for t, a in (bruto.get('ativos') or {}).items() if t in universo}
    if not ativos:
        return None
    return {'fonte': bruto.get('fonte', 'B3 (aluguel de ações, posições em aberto)') + ' · via coletor no Brasil', 'data': dia.isoformat(), 'ativos': ativos}


def gravar(pasta, dados):
    dados = {**dados, 'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}
    with open(os.path.join(pasta, 'vendidos.json'), 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, separators=(',', ':'))
    registrar_no_manifesto(pasta, 'arquivoVendidos', 'vendidos.json')


def registrar_no_manifesto(pasta, chave, nome):
    """Avisa o app (pelo manifest.json) que o arquivo extra existe, para ele não pedir arquivo inexistente."""
    caminho = os.path.join(pasta, 'manifest.json')
    with open(caminho, encoding='utf-8') as f:
        m = json.load(f)
    m[chave] = nome
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def main(argv=None, hoje=None, sessao=requests):
    ap = argparse.ArgumentParser(description='Coleta posições vendidas (FINRA e B3).')
    ap.add_argument('--saida', default='site/data')
    ap.add_argument('--b3-bruto', default=None, help='cópia da B3 baixada pelo coletor no Brasil (usada se recente)')
    ap.add_argument('--somente-b3-bruto', default=None, help='só baixa a B3 inteira para este arquivo (coletor no Brasil)')
    args = ap.parse_args(argv)
    hoje = hoje or date.today()
    if args.somente_b3_bruto:
        dados = baixar_b3(None, hoje, sessao)
        os.makedirs(os.path.dirname(os.path.abspath(args.somente_b3_bruto)), exist_ok=True)
        with open(args.somente_b3_bruto, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, separators=(',', ':'))
        log(f"B3 bruto: {len(dados['ativos'])} papéis com posição de aluguel em {dados['data']} → {args.somente_b3_bruto}")
        return 0
    def brasil(u):
        if args.b3_bruto:
            d = ler_b3_bruto(args.b3_bruto, u, hoje)
            if d:
                return d
        return baixar_b3(u, hoje, sessao)
    resumo = ['', '## Vendidos (alerta de short squeeze)', '']
    for nome, pasta, func in (('EUA', args.saida, lambda u: baixar_finra(u, sessao, hoje)),
                              ('Brasil', os.path.join(args.saida, 'br'), brasil)):
        universo = tickers_com_preco(pasta)
        if not universo:
            resumo.append(f'- {nome}: sem preços nesta publicação; pulado.')
            continue
        try:
            dados = func(universo)
            gravar(pasta, dados)
            resumo.append(f"- {nome}: ✅ {len(dados['ativos'])} papéis com posição vendida ({dados['fonte']}, {dados['data']}).")
        except Exception as e:  # nunca bloqueia a publicação
            log(f'Vendidos {nome}: falhou: {e!r}')
            resumo.append(f'- {nome}: ⚠️ não consegui baixar ({e}). O app só não mostra o alerta.')
    texto = '\n'.join(resumo)
    log(texto)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(texto + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
