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

    print('### Dados de posições em aberto (POST vazio)')
    for take in (20, 1000, 5000):
        url = f'{B}/table/BTBLendingOpenPosition/{dia}/{dia}/1/{take}'
        st, txt = get(url, 'POST', {})
        print(f'POST {st} take={take} tamanho={len(txt)}')
        try:
            obj = json.loads(txt)
        except ValueError:
            print('   não é JSON:', txt[:200]); continue
        print('   chaves:', list(obj.keys()))
        tab = obj.get('table') or {}
        print('   table.chaves:', list(tab.keys()))
        for k in ('pageCount', 'totalCount', 'count', 'total'):
            for o in (obj, tab):
                if k in o: print(f'   {k} =', o[k])
        cols = tab.get('columns') or obj.get('columns')
        if cols: print('   colunas:', [c.get('name') if isinstance(c, dict) else c for c in cols])
        vals = obj.get('values') or tab.get('values') or []
        print('   linhas:', len(vals))
        for v in vals[:4]: print('     ', json.dumps(v, ensure_ascii=False)[:300])
        if take == 20:
            for k, v in obj.items():
                if k not in ('table', 'values'): print(f'   {k}:', json.dumps(v, ensure_ascii=False)[:300])


if __name__ == '__main__':
    main()
