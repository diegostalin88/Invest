"""Recupera o diário de sinais e a calibração da publicação anterior (os dados não ficam no git).

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


ARQUIVOS = {  # arquivo: (teste de validade, campo de data usado para escolher o mais recente)
    'diario.json': (lambda o: isinstance(o.get('sinais'), list), 'atualizadoEm'),
    'calibracao.json': (lambda o: bool(o.get('alvo')) and bool(o.get('dias')), 'calculadoEm'),
}


def escolher(*opcoes, nome='diario.json'):
    valido, campo = ARQUIVOS[nome]
    validas = [o for o in opcoes if isinstance(o, dict) and valido(o)]
    return max(validas, key=lambda o: o.get(campo) or '') if validas else None


def main(argv):
    saida, base, cache = argv[1], argv[2].rstrip('/'), argv[3]
    for sub in ('', 'br'):
        destino = os.path.join(saida, sub)
        if not os.path.isfile(os.path.join(destino, 'manifest.json')):
            continue
        for arq in ARQUIVOS:
            url = f'{base}/{sub}/{arq}' if sub else f'{base}/{arq}'
            d = escolher(ler_url(url), ler_arquivo(os.path.join(cache, sub, arq)), nome=arq)
            rotulo = f"{sub.upper() or 'US'} {arq}"
            if d is None:
                print(f'{rotulo}: nenhum anterior; começa do zero.')
                continue
            with open(os.path.join(destino, arq), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False)
            print(f'{rotulo}: anterior recuperado.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
