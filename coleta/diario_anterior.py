"""Recupera o diário de sinais da publicação anterior (os dados não ficam no git).

Fontes: o diario.json publicado no Pages e a cópia de segurança do cache do Actions. Fica com o mais
recente (campo atualizadoEm). Sem nenhum dos dois, o diário começa do zero (só um aviso).

Uso: python coleta/diario_anterior.py site/data https://.../data diario-cache
"""
import json
import os
import sys
import urllib.request


def ler_url(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:  # noqa: BLE001 - qualquer falha = sem essa fonte
        print(f'  sem {url}: {e}')
        return None


def ler_arquivo(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def escolher(*opcoes):
    validas = [o for o in opcoes if isinstance(o, dict) and isinstance(o.get('sinais'), list)]
    return max(validas, key=lambda o: o.get('atualizadoEm') or '') if validas else None


def main(argv):
    saida, base, cache = argv[1], argv[2].rstrip('/'), argv[3]
    for sub in ('', 'br'):
        destino = os.path.join(saida, sub)
        if not os.path.isfile(os.path.join(destino, 'manifest.json')):
            continue
        url = f'{base}/{sub}/diario.json' if sub else f'{base}/diario.json'
        d = escolher(ler_url(url), ler_arquivo(os.path.join(cache, sub, 'diario.json')))
        nome = sub.upper() or 'US'
        if d is None:
            print(f'{nome}: nenhum diário anterior; começa hoje.')
            continue
        with open(os.path.join(destino, 'diario.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)
        print(f"{nome}: diário anterior com {len(d['sinais'])} sinais (atualizado em {d.get('atualizadoEm')}).")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
