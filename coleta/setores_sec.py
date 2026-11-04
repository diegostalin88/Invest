"""Setor de cada papel dos EUA pelo código SIC da SEC (só leitura; para medir limite por setor).

Uso: python coleta/setores_sec.py relatorio.json saida.json   (precisa de SEC_USER_AGENT)
Grava {ticker: {"sic": "3674", "grupo": "36", "descricao": "Semiconductors & Related Devices"}}.
"""
import json
import sys

import fetch_all as fa


def setor_da_empresa(cik, sec_get=None):
    sec_get = sec_get or fa.sec_get
    resp = sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None or resp.status_code != 200:
        return None
    dados = resp.json()
    sic = str(dados.get('sic') or '').strip()
    if not sic:
        return None
    return {'sic': sic, 'grupo': sic[:2], 'descricao': dados.get('sicDescription') or ''}


def main():
    R = json.load(open(sys.argv[1]))
    tickers = sorted({a['t'] for a in R.get('ativos', []) if a.get('regra')})
    mapa = fa.load_sec_ticker_map()
    res = {}
    for t in tickers:
        cik = mapa.get(t.upper().replace('.', '-')) or mapa.get(t.upper())
        s = setor_da_empresa(cik) if cik else None
        if s:
            res[t] = s
    json.dump(res, open(sys.argv[2], 'w'))
    print(f"Setores (SIC da SEC): {len(res)} de {len(tickers)} papéis.")


if __name__ == '__main__':
    main()
