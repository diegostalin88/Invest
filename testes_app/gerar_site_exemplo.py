"""Gera uma pasta site/ de exemplo com dados SINTÉTICOS, no mesmo formato da coleta real
(usa as próprias funções do coleta/fetch_all.py), para testar o app no navegador sem rede.

USO:
    python testes_app/gerar_site_exemplo.py /caminho/site_exemplo
"""
import json
import os
import random
import shutil
import sys
from datetime import date, datetime, timezone

import pandas as pd

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'coleta'))
import fetch_all as fa  # noqa: E402

N_DIAS = 800
N_ALEATORIOS = 60


def passeio(rng, n, preco0, drift, vol_dia, volume_medio):
    close, p = [], preco0
    for _ in range(n):
        p *= 1 + rng.gauss(drift, vol_dia)
        close.append(max(p, 0.5))
    opn = [close[0]] + close[:-1]
    high = [max(o, c) * (1 + abs(rng.gauss(0, vol_dia / 2))) for o, c in zip(opn, close)]
    low = [min(o, c) * (1 - abs(rng.gauss(0, vol_dia / 2))) for o, c in zip(opn, close)]
    volume = [int(volume_medio * rng.uniform(0.7, 1.3)) for _ in range(n)]
    return {'open': opn, 'high': high, 'low': low, 'close': close, 'volume': volume}


def tendencia_com_spike(n, preco0, volume_medio):
    """Alta suave e constante; último candle fecha na máxima com volume 4x a média
    (gera Volume_Spike + ADL ascendente, sem anomalia de volatilidade)."""
    close = [preco0 * (1.0008 ** i) * (1 + 0.004 * ((i % 7) - 3) / 3) for i in range(n)]
    opn = [close[0]] + close[:-1]
    high = [max(o, c) * 1.006 for o, c in zip(opn, close)]
    low = [min(o, c) * 0.994 for o, c in zip(opn, close)]
    volume = [volume_medio] * n
    opn[-1] = close[-2]; close[-1] = close[-2] * 1.01; high[-1] = close[-1]; low[-1] = opn[-1] * 0.998
    volume[-1] = volume_medio * 4
    return {'open': opn, 'high': high, 'low': low, 'close': close, 'volume': volume}


def fundamento(rng, nome, bom=True, critico=False):
    f = {
        'pe': rng.uniform(8, 20) if bom else rng.uniform(30, 80), 'pb': rng.uniform(1, 4),
        'roe': rng.uniform(0.12, 0.3), 'debtToEquity': rng.uniform(0.1, 1.2),
        'netMargin': rng.uniform(0.09, 0.3), 'revenueGrowth': rng.uniform(-0.05, 0.25),
        'sector': 'Technology', 'industry': 'Software', 'marketCap': 5e10, 'longName': nome,
        'price': 100.0, 'shortPercentOfFloat': 0.03, 'shortRatio': 1.5, 'targetMeanPrice': 120.0,
        'recommendationKey': 'buy', 'fiftyTwoWeekHigh': 130.0, 'fiftyTwoWeekLow': 80.0,
        'nextEarningsDate': '2026-11-20', 'fonte': 'yfinance', 'atualizadoEm': date.today().isoformat(),
        'alertaEvento': None, 'eventosCorporativos': [],
    }
    if critico:
        f['alertaEvento'] = 'critico'
        f['eventosCorporativos'] = [{'data': date.today().isoformat(), 'item': '1.03',
                                     'descricao': 'Falência ou recuperação judicial', 'url': None}]
    return f


def main(destino):
    rng = random.Random(42)
    datas = [d.strftime('%Y-%m-%d') for d in pd.bdate_range(end=pd.Timestamp(date.today()), periods=N_DIAS)]
    precos, fundamentos = {}, {}
    for i in range(N_ALEATORIOS):
        t = f'R{i:03d}'
        s = passeio(rng, N_DIAS, rng.uniform(20, 300), 0.0006, 0.018, rng.choice([400_000, 2_000_000, 5_000_000]))
        precos[t] = {'dates': datas, **s}
        fundamentos[t] = fundamento(rng, f'Empresa {t}', bom=rng.random() < 0.6)
    for t, crit in [('CRIT', True), ('BOA1', False), ('BOA2', False)]:
        s = tendencia_com_spike(N_DIAS, 50 if t == 'CRIT' else 40, 3_000_000)
        precos[t] = {'dates': datas, **s}
        fundamentos[t] = fundamento(rng, f'{t} Corp', bom=True, critico=crit)
    # Um ativo com buraco nas datas (exercita o caminho "dates explícitas" do formato colunar)
    s = passeio(rng, N_DIAS - 3, 80, 0.0005, 0.015, 2_000_000)
    precos['GAP'] = {'dates': datas[:100] + datas[103:], **s}

    precos = {t: fa.arredondar_serie(s) for t, s in precos.items()}
    arquivos = fa.montar_arquivos_precos(precos, max_bytes=600_000)
    dados = os.path.join(destino, 'data')
    if os.path.exists(destino):
        shutil.rmtree(destino)
    shutil.copytree(os.path.join(RAIZ, 'app'), destino)
    os.makedirs(dados)
    for nome, b in arquivos:
        with open(os.path.join(dados, nome), 'wb') as f:
            f.write(b)
    fund_b = json.dumps(fundamentos, separators=(',', ':')).encode()
    with open(os.path.join(dados, 'fundamentos.json'), 'wb') as f:
        f.write(fund_b)
    stats = {'tickersPrecos': len(precos), 'tickersFundamentos': len(fundamentos),
             'fundamentosComDados': len(fundamentos), 'fundamentosAtualizadosHoje': 10, 'alertasCriticos': 1}
    tamanhos = {'precosBytes': sum(len(b) for _, b in arquivos), 'fundamentosBytes': len(fund_b)}
    agora = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    m = fa.montar_manifesto(agora, datas[-1], 3, [n for n, _ in arquivos], stats, [], tamanhos)
    with open(os.path.join(dados, 'manifest.json'), 'w') as f:
        json.dump(m, f, indent=2)
    print(f"Site de exemplo em {destino}: {len(precos)} ativos, {len(arquivos)} arquivos de preço.")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, 'site_exemplo'))
