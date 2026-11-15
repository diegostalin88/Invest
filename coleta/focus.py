"""Boletim Focus do Banco Central (15/11/2026): o que o mercado espera de Selic, IPCA, PIB e câmbio.

Usa a mesma API pública que a biblioteca python-bcb usa por baixo (Olinda / Expectativas), chamada direto, para não
instalar pandas na VM de 1 GB. Grava `focus.json` com a mediana mais recente para o ano corrente e o seguinte, e a
mediana de 4 semanas antes (o que mudou no mês).

É DESCRIÇÃO do que os economistas esperam, não sinal: nenhuma regra do app usa estes números para comprar ou vender.

Uso: python coleta/focus.py site/data
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

URL = 'https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais'
INDICADORES = {'Selic': 'selic', 'IPCA': 'ipca', 'PIB Total': 'pib', 'Câmbio': 'cambio'}
SEMANAS_ANTES = 4


def http_json(url):
    import requests
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def consulta(desde):
    filtro = '(' + ' or '.join(f"Indicador eq '{i}'" for i in INDICADORES) + f") and Data ge '{desde}' and baseCalculo eq 0"
    campos = 'Indicador,Data,DataReferencia,Mediana,numeroRespondentes'
    return (f'{URL}?$format=json&$top=2000&$orderby=Data%20desc&$select={campos}'
            f'&$filter={quote(filtro, safe="")}')


def resumir(linhas, hoje):
    """linhas: registros da API. Devolve {data, anos, <ind>: {ano: mediana}, antes: {data, <ind>: {...}}} ou None."""
    anos = [str(hoje.year), str(hoje.year + 1)]
    linhas = [l for l in linhas if l.get('Indicador') in INDICADORES and str(l.get('DataReferencia')) in anos
              and l.get('Mediana') is not None and l.get('Data')]
    if not linhas:
        return None
    datas = sorted({l['Data'] for l in linhas}, reverse=True)
    ultima = datas[0]
    alvo_antes = (date.fromisoformat(ultima) - timedelta(weeks=SEMANAS_ANTES)).isoformat()
    antes = next((d for d in datas if d <= alvo_antes), None)

    def foto(d):
        o = {}
        for l in linhas:
            if l['Data'] == d:
                o.setdefault(INDICADORES[l['Indicador']], {})[str(l['DataReferencia'])] = round(float(l['Mediana']), 4)
        return o

    out = {'data': ultima, 'anos': anos, **foto(ultima)}
    if antes:
        out['antes'] = {'data': antes, **foto(antes)}
    return out


def main(argv=None, pedir=http_json, hoje=None):
    argv = argv if argv is not None else sys.argv
    if len(argv) < 2:
        print(__doc__)
        return 1
    hoje = hoje or datetime.now(timezone.utc).date()
    desde = (hoje - timedelta(days=60)).isoformat()
    try:
        dados = pedir(consulta(desde))
    except Exception as e:  # rede fora: o agente segue sem Focus
        print(f'Focus indisponível: {e}')
        return 2
    res = resumir(dados.get('value') or [], hoje)
    if not res:
        print('Focus sem dados para o ano corrente.')
        return 2
    res['fonte'] = 'Banco Central, boletim Focus (mediana, base de cálculo 0)'
    os.makedirs(argv[1], exist_ok=True)
    with open(os.path.join(argv[1], 'focus.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, separators=(',', ':'))
    print(f"Focus de {res['data']}: " + ', '.join(f"{k} {v}" for k, v in res.items() if k in INDICADORES.values()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
