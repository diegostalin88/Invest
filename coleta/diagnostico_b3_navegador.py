"""Diagnóstico (só leitura): abre a página de tabelas da B3 num navegador sem tela e lista
os endereços que ela chama para buscar os dados. Roda no coletor no Brasil.
Uso: python coleta/diagnostico_b3_navegador.py [AAAA-MM-DD]"""
import datetime as dt
import sys

from playwright.sync_api import sync_playwright


def dia_util_anterior():
    d = dt.date.today() - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else dia_util_anterior()
    paginas = [f'https://arquivos.b3.com.br/tabelas/table/LendingOpenPosition/{d}/{d}',
               'https://arquivos.b3.com.br/tabelas/']
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        for url in paginas:
            print(f'\n### Página {url}')
            pag = nav.new_page()
            vistos = []

            def resposta(r):
                tipo = r.headers.get('content-type', '')
                if any(x in tipo for x in ('image', 'font', 'css')):
                    return
                linha = f'{r.request.method} {r.status} {tipo[:30]} {r.url[:220]}'
                if 'json' in tipo:
                    try:
                        linha += '\n      ' + r.text()[:300].replace('\n', ' ')
                    except Exception as e:  # corpo indisponível
                        linha += f'\n      (sem corpo: {e})'
                vistos.append(linha)

            pag.on('response', resposta)
            try:
                pag.goto(url, wait_until='networkidle', timeout=60000)
                pag.wait_for_timeout(8000)
            except Exception as e:
                print(f'erro ao abrir: {e}')
            for v in vistos:
                print('  ' + v)
            print('  texto visível:', pag.inner_text('body')[:400].replace('\n', ' | '))
            pag.close()
        nav.close()


if __name__ == '__main__':
    main()
