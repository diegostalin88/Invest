"""Ações e BDRs da watchlist que não estão no universo (Ibovespa e EUA mais negociados), baixados pelo MESMO caminho
do universo (25/11/2026, achados do Consultor): preços OHLC ajustados por proventos e desdobramentos (yfinance
auto_adjust=True, fetch_all.baixar_precos) e fundamentos do Yahoo (fetch_all.atualizar_fundamentos).

Grava PASTA_MERCADO/br/extras/ e PASTA_MERCADO/extras/ (manifest.json, precos_000.json, fundamentos.json), lidos pelo
vendidos.py (aluguel B3 / FINRA desses papéis) e pelo agente.py (entram em mercados.*.papeis com "extra": true; não
contam em amplitude, listas nem termômetro). Não muda a carteira.json (o motor da carteira usa a série dela).

Uso: python coleta/extras.py PASTA_MERCADO CARTEIRA_JSON     (PASTA_MERCADO = .../antigo/data)
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

try:
    import fetch_all as fa
except ImportError:  # rodando de fora da pasta coleta/
    from coleta import fetch_all as fa

BASE_CARTEIRA = {'BOVA11', 'IVVB11', 'BTC'}
MIN_PREGOES_EXTRA = 60          # papel novo na bolsa também entra (o agente só calcula o que der)
RE_BR = re.compile(r'^[A-Z0-9]{4}\d{1,2}$')


def escolher(carteira, universo_br, universo_us):
    """(br, us): ações BR e BDRs (não …11: ETF, FII e units) e ações dos EUA (tipo EQUITY) da watchlist fora do universo."""
    br, us = [], []
    for t, a in (carteira.get('ativos') or {}).items():
        if t in BASE_CARTEIRA or a.get('apoio'):
            continue
        if a.get('moeda') == 'USD':
            if a.get('tipo') == 'EQUITY' and t not in universo_us:
                us.append(t)
        elif RE_BR.match(t) and not t.endswith('11') and t not in universo_br:
            br.append(t)
    return sorted(br), sorted(us)


def tickers(pasta):
    m = fa_ler(os.path.join(pasta, 'manifest.json')) or {}
    out = set()
    for nome in m.get('arquivosPrecos') or []:
        obj = fa_ler(os.path.join(pasta, nome)) or {}
        out |= set((obj.get('ativos') if obj.get('formato') == 'colunar-v1' else obj) or {})
    return out


def fa_ler(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def coletar(lista, sufixo, saida, mercado, moeda, hoje, baixar=None, fundamentos=None):
    """Baixa e grava; devolve (papéis com preço, papéis sem preço). `baixar`/`fundamentos` existem para os testes."""
    baixar = baixar or fa.baixar_precos
    fundamentos = fundamentos or (lambda pool, precos: fa.atualizar_fundamentos(
        pool, {}, {t: fa.arredondar_preco(precos[t]['close'][-1]) for t in pool}, hoje, {}, sufixo_yahoo=sufixo, radar=False)[0])
    shutil.rmtree(saida, ignore_errors=True)
    if not lista:
        return [], []
    brutos, _ = baixar([t + sufixo for t in lista], fa.ANOS_HISTORICO)
    brutos = {t[:-len(sufixo)] if sufixo and t.endswith(sufixo) else t: s for t, s in brutos.items()}
    fa.remover_duplicatas(brutos)
    precos = fa.aplicar_prefiltro_precos(brutos, min_adtv=0, min_pregoes=MIN_PREGOES_EXTRA)
    if not precos:
        return [], lista
    fund = fundamentos(sorted(precos), precos)
    precos_r = {t: fa.arredondar_serie(s) for t, s in precos.items()}
    arquivos = fa.montar_arquivos_precos(precos_r)
    os.makedirs(saida)
    for nome, conteudo in arquivos:
        with open(os.path.join(saida, nome), 'wb') as f:
            f.write(conteudo)
    with open(os.path.join(saida, 'fundamentos.json'), 'w', encoding='utf-8') as f:
        json.dump(fund, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False, default=str)
    manifesto = {'versao': fa.VERSAO_MANIFESTO, 'mercado': mercado, 'moeda': moeda, 'extra': True,
                 'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
                 'ultimoPregao': fa.calcular_ultimo_pregao(precos), 'formatoPrecos': fa.FORMATO_PRECOS,
                 'arquivosPrecos': [n for n, _ in arquivos], 'arquivoFundamentos': 'fundamentos.json',
                 'papeis': sorted(precos)}
    with open(os.path.join(saida, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)
    return sorted(precos), [t for t in lista if t not in precos]


def main(argv=None, hoje=None, **kw):
    argv = argv if argv is not None else sys.argv
    if len(argv) < 3:
        print(__doc__)
        return 2
    m, cart = argv[1], fa_ler(argv[2]) or {}
    hoje = hoje or datetime.now(timezone.utc).date()
    br, us = escolher(cart, tickers(os.path.join(m, 'br')), tickers(m))
    ok_br, sem_br = coletar(br, '.SA', os.path.join(m, 'br', 'extras'), 'br', 'BRL', hoje, **kw)
    ok_us, sem_us = coletar(us, '', os.path.join(m, 'extras'), 'us', 'USD', hoje, **kw)
    print(f'extras: BR {len(ok_br)} ({", ".join(ok_br)}) · EUA {len(ok_us)} ({", ".join(ok_us)})'
          + (f' · sem preço: {", ".join(sem_br + sem_us)}' if sem_br or sem_us else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
