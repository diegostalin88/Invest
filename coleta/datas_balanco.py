"""Datas históricas de divulgação de resultado (balanço) dos papéis dos EUA, pela SEC.

Usa os formulários 8-K com o item 2.02 ("Results of Operations and Financial Condition"), que é como as
empresas americanas comunicam o resultado trimestral. Lê o histórico recente e os arquivos antigos de cada
empresa. Empresas estrangeiras (formulário 6-K) e papéis sem CIK ficam de fora.

Só leitura; serve para medir a proposta de não entrar perto do balanço.
Uso: python coleta/datas_balanco.py relatorio.json saida.json   (precisa de SEC_USER_AGENT)
"""
import json
import sys

import fetch_all as fa


def datas_202(bloco):
    forms, datas, itens = bloco.get('form', []), bloco.get('filingDate', []), bloco.get('items', [])
    saida = []
    for i, form in enumerate(forms):
        if form not in ('8-K', '8-K/A') or i >= len(datas):
            continue
        codigos = [x.strip() for x in ((itens[i] if i < len(itens) else '') or '').split(',')]
        if '2.02' in codigos:
            saida.append(datas[i])
    return saida


def datas_de_balanco(cik, sec_get=None):
    """Lista ordenada (sem repetição) das datas de 8-K item 2.02 da empresa, ou None se a SEC falhou."""
    sec_get = sec_get or fa.sec_get
    resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None or resp.status_code != 200:
        return None
    dados = resp.json()
    filings = dados.get('filings', {})
    datas = datas_202(filings.get('recent', {}))
    for arq in filings.get('files', []) or []:
        nome = arq.get('name')
        if not nome:
            continue
        r = sec_get(f"https://data.sec.gov/submissions/{nome}")
        if r is not None and r.status_code == 200:
            datas += datas_202(r.json())
    return sorted(set(datas))


def main():
    relatorio, saida = sys.argv[1], sys.argv[2]
    R = json.load(open(relatorio))
    tickers = sorted({a['t'] for a in R.get('ativos', []) if a.get('regra') and a.get('confirmada')})
    mapa = fa.load_sec_ticker_map()
    res, sem = {}, []
    for t in tickers:
        cik = mapa.get(t.upper().replace('.', '-')) or mapa.get(t.upper())
        datas = datas_de_balanco(cik) if cik else None
        if datas:
            res[t] = datas
        else:
            sem.append(t)
    json.dump(res, open(saida, 'w'))
    print(f"Datas de balanço: {len(res)} de {len(tickers)} papéis. Sem dado: {', '.join(sem) or 'nenhum'}")


if __name__ == '__main__':
    main()
