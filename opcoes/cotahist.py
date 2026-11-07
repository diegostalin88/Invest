"""Verifica se o histórico público da B3 (COTAHIST) serve para reconstruir a volatilidade implícita (IV).

Estudo só de leitura, separado do app e da estratégia congelada (docs/congelamento.md). Não publica nada.

Para cada pregão e cada ativo do universo, pega a call e a put mais próximas do dinheiro no vencimento mais
perto de 30 dias, inverte Black-Scholes com o CDI do dia e guarda a média das duas IVs. No fim, mede quantos
pregões têm IV, a IV mediana por ano e o IV Rank de 252 pregões.

Uso: python opcoes/cotahist.py --anos 2018-2026 --saida opcoes_resultado
Só usa a biblioteca padrão do Python.
"""
import argparse
import csv
import io
import json
import math
import os
import statistics
import sys
import time
import urllib.request
import zipfile
from datetime import date, timedelta

UNIVERSO = ('PETR4', 'VALE3', 'BOVA11', 'ITUB4', 'BBAS3', 'PRIO3')
URL_ANUAL = 'https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP'
URL_CDI = ('https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json'
           '&dataInicial={ini}&dataFinal={fim}')
USER_AGENT = 'Mozilla/5.0 (Invest estudo de opcoes)'

# Escolha das opções de cada dia (parâmetros do estudo, fixados antes de rodar)
DTE_MIN, DTE_MAX, DTE_ALVO = 20, 60, 30     # dias corridos até o vencimento
NEGOCIOS_MIN = 5                            # negócios no dia, para o último preço valer alguma coisa
PRECO_MIN = 0.03                            # R$; abaixo disso o tick distorce a IV
JANELA_RANK = 252                           # pregões do IV Rank
CDI_RESERVA = 0.10                          # usado só se o Banco Central não responder


# ---------- leitura do arquivo (layout oficial do COTAHIST, posições contadas a partir de 1) ----------

def _preco(campo):
    return int(campo) / 100.0


def ler_linha(linha):
    """Devolve um dicionário com os campos usados, ou None se não for registro de cotação."""
    if linha[0:2] != '01':
        return None
    return {
        'data': linha[2:10],
        'codbdi': linha[10:12],
        'codneg': linha[12:24].strip(),
        'tpmerc': linha[24:27],
        'especi': linha[39:49].strip(),
        'premax': _preco(linha[69:82]),
        'premin': _preco(linha[82:95]),
        'preult': _preco(linha[108:121]),
        'preofc': _preco(linha[121:134]),
        'preofv': _preco(linha[134:147]),
        'totneg': int(linha[147:152]),
        'voltot': _preco(linha[170:188]),
        'preexe': _preco(linha[188:201]),
        'datven': linha[202:210],
        'fatcot': int(linha[210:217]),
    }


def classe(especi):
    """ON, PN, UNT, CI... (o começo da especificação), para separar opção de PETR3 da de PETR4."""
    return especi.split()[0] if especi else ''


def filtrar(linhas, universo=UNIVERSO, ohlc=None):
    """Separa os preços à vista do universo e as opções sobre eles. Devolve (spot, opcoes, ignoradas).
    Se `ohlc` for um dicionário, recebe também (máxima, mínima) do ativo à vista por (data, ativo)."""
    raizes = {t[:4]: t for t in universo}
    spot, classes, opcoes, ignoradas = {}, {}, [], 0
    for r in filter(None, map(ler_linha, linhas)):
        if r['tpmerc'] == '010' and r['codneg'] in universo:
            spot[(r['data'], r['codneg'])] = r['preult'] / max(r['fatcot'], 1)
            if ohlc is not None:
                f = max(r['fatcot'], 1)
                ohlc[(r['data'], r['codneg'])] = (r['premax'] / f, r['premin'] / f, r['voltot'])
            classes[r['codneg']] = classe(r['especi'])
        elif r['tpmerc'] in ('070', '080') and r['codneg'][:4] in raizes:
            r['ativo'] = raizes[r['codneg'][:4]]
            r['tipo'] = 'call' if r['tpmerc'] == '070' else 'put'
            opcoes.append(r)
    filtradas, vistas = [], {}
    for r in opcoes:
        vistas[f"{r['ativo']} {classe(r['especi']) or '?'}"] = vistas.get(f"{r['ativo']} {classe(r['especi']) or '?'}", 0) + 1   # a classe à vista só é conhecida depois de ler o arquivo todo
        c = classes.get(r['ativo'])
        if c and classe(r['especi']) != c:
            ignoradas += 1   # ex.: opção de PETR3 com a mesma raiz PETR
        else:
            filtradas.append(r)
    filtrar.classes_vistas = vistas   # diagnóstico: classes das opções por ativo
    return spot, filtradas, ignoradas


# ---------- Black-Scholes ----------

def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_preco(tipo, s, k, t, r, vol):
    if vol <= 0 or t <= 0:
        return max(0.0, s - k) if tipo == 'call' else max(0.0, k - s)
    d1 = (math.log(s / k) + (r + vol * vol / 2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if tipo == 'call':
        return s * _ncdf(d1) - k * math.exp(-r * t) * _ncdf(d2)
    return k * math.exp(-r * t) * _ncdf(-d2) - s * _ncdf(-d1)


def iv(tipo, preco, s, k, t, r):
    """Volatilidade implícita por bisseção (0,5% a 300% ao ano). None se o preço não tiver IV possível."""
    lo, hi = 0.005, 3.0
    if not (bs_preco(tipo, s, k, t, r, lo) < preco < bs_preco(tipo, s, k, t, r, hi)):
        return None
    for _ in range(80):
        meio = (lo + hi) / 2
        if bs_preco(tipo, s, k, t, r, meio) < preco:
            lo = meio
        else:
            hi = meio
    return (lo + hi) / 2


# ---------- IV diária ----------

def _dia(aaaammdd):
    return date(int(aaaammdd[:4]), int(aaaammdd[4:6]), int(aaaammdd[6:8]))


def iv_diaria(spot, opcoes, cdi):
    """Uma linha por (data, ativo) com IV ATM de ~30 dias. cdi: {AAAAMMDD: taxa anual}."""
    grupos = {}
    for o in opcoes:
        grupos.setdefault((o['data'], o['ativo']), []).append(o)
    linhas = []
    for (d, ativo), lista in sorted(grupos.items()):
        s = spot.get((d, ativo))
        if not s:
            continue
        hoje = _dia(d)
        validas = []
        for o in lista:
            dte = (_dia(o['datven']) - hoje).days
            preco = o['preult'] / max(o['fatcot'], 1)
            if DTE_MIN <= dte <= DTE_MAX and o['totneg'] >= NEGOCIOS_MIN and preco >= PRECO_MIN and o['preexe'] > 0:
                validas.append((dte, o, preco))
        if not validas:
            continue
        dte = min({v[0] for v in validas}, key=lambda x: (abs(x - DTE_ALVO), x))
        r = math.log(1 + cdi.get(d, CDI_RESERVA))
        t = dte / 365.0
        ivs, strikes = [], []
        for tipo in ('call', 'put'):
            doTipo = [v for v in validas if v[0] == dte and v[1]['tipo'] == tipo]
            if not doTipo:
                continue
            _, o, preco = min(doTipo, key=lambda v: abs(v[1]['preexe'] - s))
            x = iv(tipo, preco, s, o['preexe'], t, r)
            if x is not None:
                ivs.append(x)
                strikes.append(o['preexe'])
        if ivs:
            linhas.append({'data': f'{d[:4]}-{d[4:6]}-{d[6:]}', 'ativo': ativo, 'spot': round(s, 2),
                           'dte': dte, 'strike': round(statistics.mean(strikes), 2),
                           'iv': round(statistics.mean(ivs), 4), 'pernas': len(ivs)})
    return linhas


def iv_rank(serie, janela=JANELA_RANK):
    """IV Rank (0 a 100) do último valor contra os últimos `janela` valores. None se faltar histórico."""
    if len(serie) < janela:
        return None
    ultimos = serie[-janela:]
    lo, hi = min(ultimos), max(ultimos)
    return 100.0 * (serie[-1] - lo) / (hi - lo) if hi > lo else 50.0


def resumir(linhas, pregoes):
    """pregoes: {ativo: {ano: nº de pregões com preço à vista}}."""
    out = {}
    for ativo in UNIVERSO:
        serie = [x for x in linhas if x['ativo'] == ativo]
        anos = {}
        for ano, total in sorted(pregoes.get(ativo, {}).items()):
            doAno = [x['iv'] for x in serie if x['data'][:4] == ano]
            anos[ano] = {'pregoes': total, 'comIV': len(doAno),
                         'cobertura': round(len(doAno) / total, 3) if total else 0,
                         'ivMediana': round(statistics.median(doAno), 4) if doAno else None}
        ivs = [x['iv'] for x in serie]
        rank = iv_rank(ivs)
        out[ativo] = {'anos': anos, 'primeiraData': serie[0]['data'] if serie else None,
                      'ultimaData': serie[-1]['data'] if serie else None,
                      'ultimaIV': ivs[-1] if ivs else None,
                      'ivRank': round(rank, 1) if rank is not None else None}
    return out


def markdown(resumo, avisos):
    linhas = ['## Histórico de opções da B3 (COTAHIST): dá para calcular IV?', '']
    linhas += [f'- {a}' for a in avisos] + ['']
    linhas += ['| Ativo | Ano | Pregões | Com IV | Cobertura | IV mediana |', '| --- | --- | --- | --- | --- | --- |']
    for ativo, r in resumo.items():
        for ano, a in r['anos'].items():
            ivm = f"{a['ivMediana'] * 100:.1f}%" if a['ivMediana'] is not None else '–'
            linhas.append(f"| {ativo} | {ano} | {a['pregoes']} | {a['comIV']} | {a['cobertura'] * 100:.0f}% | {ivm} |")
    linhas += ['', '| Ativo | Última data | Última IV | IV Rank (252) |', '| --- | --- | --- | --- |']
    for ativo, r in resumo.items():
        ultima = f"{r['ultimaIV'] * 100:.1f}%" if r['ultimaIV'] is not None else '–'
        rank = f"{r['ivRank']:.0f}" if r['ivRank'] is not None else '–'
        linhas.append(f"| {ativo} | {r['ultimaData'] or '–'} | {ultima} | {rank} |")
    return '\n'.join(linhas) + '\n'


# ---------- rede ----------

def _baixar(url, tentativas=4):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 (rede: tenta de novo e, no fim, devolve o erro)
            if i == tentativas - 1:
                raise
            print(f'  falhou ({e}); tentando de novo', flush=True)
            time.sleep(2 ** (i + 1))


def linhas_do_ano(ano, tentativas=5):
    # a B3 às vezes devolve uma página no lugar do zip quando muitos downloads chegam juntos: espera e tenta de novo
    for i in range(tentativas):
        dados = _baixar(URL_ANUAL.format(ano=ano))
        if zipfile.is_zipfile(io.BytesIO(dados)):
            break
        if i == tentativas - 1:
            raise zipfile.BadZipFile(f'COTAHIST {ano}: a B3 não devolveu um zip ({len(dados)} bytes)')
        print(f'  {ano}: resposta da B3 não é zip; tentando de novo em {30 * 2 ** i}s', flush=True)
        time.sleep(30 * 2 ** i)
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nome = z.namelist()[0]
        with z.open(nome) as f:
            for linha in io.TextIOWrapper(f, encoding='latin-1'):
                yield linha


def baixar_cdi(ini, fim):
    """{AAAAMMDD: taxa anual} a partir do CDI diário (série 12 do SGS), em blocos de até 9 anos."""
    out, a = {}, ini
    while a <= fim:
        b = min(fim, date(a.year + 9, 1, 1) - timedelta(days=1))
        url = URL_CDI.format(ini=a.strftime('%d/%m/%Y'), fim=b.strftime('%d/%m/%Y'))
        for item in json.loads(_baixar(url)):
            dd, mm, aa = item['data'].split('/')
            out[f'{aa}{mm}{dd}'] = (1 + float(item['valor']) / 100) ** 252 - 1
        a = b + timedelta(days=1)
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--anos', default='2018-2026')
    p.add_argument('--saida', default='opcoes_resultado')
    args = p.parse_args(argv)
    a0, a1 = (int(x) for x in args.anos.split('-'))
    os.makedirs(args.saida, exist_ok=True)
    avisos = [f'Universo: {", ".join(UNIVERSO)}. Opção escolhida: vencimento entre {DTE_MIN} e {DTE_MAX} dias '
              f'(o mais perto de {DTE_ALVO}), strike mais perto do preço à vista, ≥ {NEGOCIOS_MIN} negócios no dia.']
    try:
        cdi = baixar_cdi(date(a0, 1, 1), date.today())
        avisos.append(f'CDI do Banco Central: {len(cdi)} dias.')
    except Exception as e:  # noqa: BLE001
        cdi = {}
        avisos.append(f'CDI do Banco Central indisponível ({e}); usado {CDI_RESERVA:.0%} ao ano.')

    linhas, pregoes, ignoradas, registros = [], {}, 0, 0
    for ano in range(a0, a1 + 1):
        t0 = time.time()
        try:
            spot, opcoes, ign = filtrar(linhas_do_ano(ano))
        except Exception as e:  # noqa: BLE001
            avisos.append(f'{ano}: arquivo não baixou ({e}).')
            continue
        ignoradas += ign
        print(f'  classes das opções: {filtrar.classes_vistas}', flush=True)
        registros += len(opcoes)
        for (d, ativo) in spot:
            pregoes.setdefault(ativo, {}).setdefault(d[:4], 0)
            pregoes[ativo][d[:4]] += 1
        doAno = iv_diaria(spot, opcoes, cdi)
        linhas += doAno
        print(f'{ano}: {len(opcoes)} registros de opções, {len(doAno)} pares (dia, ativo) com IV, '
              f'{time.time() - t0:.0f}s', flush=True)
    avisos.append(f'{registros} registros de opções do universo lidos; {ignoradas} ignorados por serem de outra '
                  'classe da mesma raiz (ex.: PETR3).')

    with open(os.path.join(args.saida, 'iv_diaria.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['data', 'ativo', 'spot', 'dte', 'strike', 'iv', 'pernas'])
        w.writeheader()
        w.writerows(linhas)
    resumo = resumir(linhas, pregoes)
    with open(os.path.join(args.saida, 'resumo.json'), 'w') as f:
        json.dump({'avisos': avisos, 'resumo': resumo}, f, indent=2, ensure_ascii=False)
    texto = markdown(resumo, avisos)
    print('RESUMO_INICIO\n' + texto + 'RESUMO_FIM')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(texto)
    return 0 if linhas else 1


if __name__ == '__main__':
    sys.exit(main())
