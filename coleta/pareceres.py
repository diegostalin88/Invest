"""Pareceres do Consultor financeiro no app (fase 4, 15/11/2026).

A VM baixa a planilha "Consultor — pareceres" do Drive como CSV (rclone, primeira aba) e este script grava
`data/pareceres.json` para o Início (último parecer) e o Laboratório (placar). Lê os preços atuais do agente.json.

Placar simples (o automático em 20/60/120 pregões com teste contra o acaso é a fase 6): para cada parecer com tese
"a favor" ou "contra", o retorno do papel desde o parecer menos o do índice no mesmo intervalo ("excesso"). Tese
"contra" acerta quando o excesso é negativo. Nada disso vale como validação antes de 60 pareceres com 120 pregões
(docs/protocolo-agente.md).

Uso: python coleta/pareceres.py pareceres.csv site/data
"""
import csv
import json
import os
import sys
from datetime import date, datetime, timezone

COLUNAS = ['data', 'papel', 'mercado', 'tese', 'confianca', 'preco_ref', 'indice', 'indice_ref', 'mudaria_opiniao', 'data_agente_json']
MINIMO_PARECERES, MINIMO_PREGOES = 60, 120


def num(x):
    try:
        return float(str(x).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None


def data_iso(x):
    x = (x or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(x[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return None


def tese_norm(t):
    t = (t or '').strip().lower()
    return 'a favor' if 'favor' in t else 'contra' if 'contra' in t else 'neutro' if 'neutr' in t else t


def dias_uteis(de, ate):
    d0, d1 = date.fromisoformat(de), date.fromisoformat(ate)
    return sum(1 for k in range(1, (d1 - d0).days + 1) if date.fromordinal(d0.toordinal() + k).weekday() < 5)


def ler_csv(caminho):
    with open(caminho, encoding='utf-8-sig', newline='') as f:
        linhas = list(csv.DictReader(f))
    out = []
    for l in linhas:
        l = {(k or '').strip().lower(): (v or '').strip() for k, v in l.items()}
        d, papel = data_iso(l.get('data')), (l.get('papel') or '').upper()
        if not d or not papel:
            continue
        out.append({'data': d, 'papel': papel, 'mercado': (l.get('mercado') or '').lower() or None, 'tese': tese_norm(l.get('tese')),
                    'confianca': (l.get('confianca') or '').lower() or None, 'precoRef': num(l.get('preco_ref')),
                    'indice': l.get('indice') or None, 'indiceRef': num(l.get('indice_ref')), 'mudaria': l.get('mudaria_opiniao') or None})
    return out


def montar(pareceres, agente, hoje=None):
    hoje = hoje or datetime.now(timezone.utc).date()
    merc = (agente or {}).get('mercados') or {}
    for p in pareceres:
        m = merc.get(p['mercado'] or ('br' if p['papel'][-1:].isdigit() else 'us')) or {}
        atual = ((m.get('papeis') or {}).get(p['papel']) or {}).get('p')
        ind = (m.get('termometro') or {}).get('ult')
        p['pregoes'] = dias_uteis(p['data'], hoje.isoformat()) if p['data'] <= hoje.isoformat() else 0
        if atual and p['precoRef'] and ind and p['indiceRef']:
            rp, ri = atual / p['precoRef'] - 1, ind / p['indiceRef'] - 1
            p['retorno'], p['retornoIndice'], p['excesso'] = round(rp, 4), round(ri, 4), round(rp - ri, 4)
            if p['tese'] in ('a favor', 'contra'):
                p['acertou'] = (p['excesso'] > 0) if p['tese'] == 'a favor' else (p['excesso'] < 0)
    com_tese = [p for p in pareceres if p['tese'] in ('a favor', 'contra') and 'acertou' in p]
    maduros = [p for p in com_tese if p['pregoes'] >= MINIMO_PREGOES]
    placar = {'pareceres': len(pareceres), 'comTese': len(com_tese), 'maduros120': len(maduros),
              'acertoAteHoje': round(sum(p['acertou'] for p in com_tese) / len(com_tese), 3) if com_tese else None,
              'podeConcluir': len(maduros) >= MINIMO_PARECERES,
              'nota': f'Validação só com {MINIMO_PARECERES} pareceres de {MINIMO_PREGOES} pregões (protocolo-agente.md). Até lá, o acerto é só acompanhamento.'}
    ult = sorted(pareceres, key=lambda p: p['data'])
    data_ult = ult[-1]['data'] if ult else None
    return {'geradoEm': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            'ultimaData': data_ult, 'ultimos': [p for p in ult if p['data'] == data_ult], 'recentes': ult[-30:][::-1], 'placar': placar}


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if len(argv) < 3:
        print(__doc__)
        return 1
    try:
        par = ler_csv(argv[1])
    except (OSError, csv.Error) as e:
        print(f'Sem planilha de pareceres: {e}')
        return 2
    try:
        ag = json.load(open(os.path.join(argv[2], 'agente.json'), encoding='utf-8'))
    except (OSError, ValueError):
        ag = None
    o = montar(par, ag)
    with open(os.path.join(argv[2], 'pareceres.json'), 'w', encoding='utf-8') as f:
        json.dump(o, f, ensure_ascii=False, separators=(',', ':'))
    print(f"pareceres.json: {o['placar']['pareceres']} pareceres, último em {o['ultimaData']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
