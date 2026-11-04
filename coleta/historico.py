"""Histórico diário dos vendidos (aluguel B3 / short interest FINRA) e da recalibração de alvo e prazo.

O vendidos.json e o calibracao.json de cada noite são sobrescritos. Este script guarda uma cópia
de cada um, por data, em historico.json (um por mercado), para que daqui a meses existam:
  - a série de aluguel/vendidos, base para testar o cenário "muitos vendidos sem notícia ruim";
  - os parâmetros de alvo e prazo que valiam em cada mês (o replay da estratégia congelada fica exato).
No Brasil, se houver a cópia bruta do coletor no Brasil, guarda TODOS os papéis da B3, não só os do app.

Como os dados não ficam no git, o histórico anterior vem do Pages ou do cache do Actions (o que tiver
mais datas). Só mede e guarda: não muda o app nem a estratégia congelada.

Uso: python coleta/historico.py site/data https://.../data diario-cache [b3-cache/aluguel_b3.json]
"""
import json
import os
import sys
from datetime import datetime, timezone

from diario_anterior import ler_arquivo, ler_url

NOME = 'historico.json'


def valido(o):
    return isinstance(o, dict) and isinstance(o.get('vendidos'), dict) and isinstance(o.get('calibracao'), dict)


def tamanho(o):
    return len(o['vendidos']) + len(o['calibracao'])


def escolher(*opcoes):
    """Fica com o histórico que tem mais datas (nunca troca um histórico longo por um vazio)."""
    validas = [o for o in opcoes if valido(o)]
    return max(validas, key=tamanho) if validas else {'vendidos': {}, 'calibracao': {}}


def acrescentar(hist, vendidos=None, calib=None):
    """Acrescenta a foto do dia; a chave é a data do próprio dado (não a da coleta), então repetir não duplica."""
    if vendidos and vendidos.get('data') and vendidos.get('ativos'):
        hist['vendidos'][vendidos['data']] = {'fonte': vendidos.get('fonte'), 'ativos': vendidos['ativos']}
    if calib and calib.get('alvo') and calib.get('dias'):
        chave = str(calib.get('calculadoEm') or '')[:10]
        if chave:
            hist['calibracao'][chave] = calib
    hist['atualizadoEm'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    return hist


def main(argv):
    saida, base, cache = argv[1], argv[2].rstrip('/'), argv[3]
    bruto_b3 = ler_arquivo(argv[4]) if len(argv) > 4 else None
    for sub in ('', 'br'):
        pasta = os.path.join(saida, sub)
        if not os.path.isfile(os.path.join(pasta, 'manifest.json')):
            continue
        url = f'{base}/{sub}/{NOME}' if sub else f'{base}/{NOME}'
        hist = escolher(ler_url(url), ler_arquivo(os.path.join(cache, sub, NOME)))
        antes = (len(hist['vendidos']), len(hist['calibracao']))
        vend = ler_arquivo(os.path.join(pasta, 'vendidos.json'))
        if sub == 'br' and isinstance(bruto_b3, dict) and bruto_b3.get('data') and bruto_b3.get('ativos'):
            if not vend or bruto_b3['data'] >= (vend.get('data') or ''):
                vend = bruto_b3  # todos os papéis da B3, não só os 76 do app
        acrescentar(hist, vend, ler_arquivo(os.path.join(pasta, 'calibracao.json')))
        with open(os.path.join(pasta, NOME), 'w', encoding='utf-8') as f:
            json.dump(hist, f, ensure_ascii=False, separators=(',', ':'))
        print(f"{sub.upper() or 'US'} {NOME}: vendidos {antes[0]} → {len(hist['vendidos'])} datas · "
              f"calibração {antes[1]} → {len(hist['calibracao'])} datas")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
