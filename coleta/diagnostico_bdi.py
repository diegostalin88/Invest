"""Diagnóstico (só leitura) do Boletim Diário da B3 (BDI): lista as tabelas de empréstimo de
ativos e os endereços que o site usa para buscar os dados. Roda no coletor no Brasil."""
import json
import re
import sys
import urllib.request

B = 'https://arquivos.b3.com.br/bdi'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'


def get(url, metodo='GET', corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo,
                                 headers={'User-Agent': UA, 'Accept': 'application/json, text/plain, */*',
                                          'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:  # rede
        return 0, str(e)


def main():
    dia = sys.argv[1] if len(sys.argv) > 1 else json.loads(get(B + '/table/workday?')[1])[:10]
    print('### Dia de referência', dia)
    st, txt = get(B + '/table/classifications')
    arv = json.loads(txt)
    achadas = []

    def anda(nos, caminho):
        for n in nos if isinstance(nos, list) else []:
            nome = caminho + ' > ' + n.get('name', '')
            for chave, t in (n.get('tables') or {}).items():
                rot = f"{t.get('friendlyNamePt')} / {t.get('friendlyNameEn')}"
                if re.search(r'mpr[eé]st|lend|btb|aluguel', (chave + rot), re.I):
                    achadas.append(chave)
                    print(f'TABELA {chave} | {rot} | id={t.get("id")} | {nome}')
            anda(n.get('children') or n.get('classifications') or [], nome)

    anda(arv, '')
    if not achadas:
        print('nenhuma tabela de empréstimo; chaves do primeiro nível:', list(arv[0].keys()))
        print(txt[:3000])

    print('### Endereços no código do site')
    js = get(B + '/static/js/main.e591a35328ff179145c0.js')[1]
    for m in sorted(set(re.findall(r'.{0,120}(?:/table/|serverUrl|relativeUrl).{0,160}', js)))[:40]:
        if 'node_modules' not in m:
            print('  ', m)

    print('### Tentativas de dados')
    for chave in achadas[:3]:
        for url, met, corpo in [
            (f'{B}/table/{chave}/{dia}/{dia}/1/20', 'GET', None),
            (f'{B}/table/{chave}/{dia}/{dia}/1', 'GET', None),
            (f'{B}/table/{chave}/{dia}/1', 'GET', None),
            (f'{B}/table/{chave}/{dia}/{dia}/1/20', 'POST', {}),
            (f'{B}/table/{chave}/{dia}/{dia}/1/20', 'POST', {'Name': chave, 'Date': dia, 'FinalDate': dia,
                                                         'ClientId': '', 'Filters': {}}),
        ]:
            st, txt = get(url, met, corpo)
            print(f'{met} {st} {url}\n      {txt[:400]}')


if __name__ == '__main__':
    main()
