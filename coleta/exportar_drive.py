"""Exporta para uma pasta local (depois copiada ao Google Drive pelo rclone) os dados e os estudos do Invest,
para o Consultor financeiro (Claude no chat) ler direto, além do agente.json.

Uso: python coleta/exportar_drive.py PASTA_DO_SITE DESTINO
  PASTA_DO_SITE: a versão publicada (www), com data/ e antigo/data{,/br}/
  DESTINO: ex. /srv/invest/drive; grava DESTINO/Dados/ (refeita do zero a cada vez) e DESTINO/Biblioteca/ (só acrescenta
  e sobrescreve; não apaga nada, porque há documentos subidos direto no Drive e a pasta operacoes/).

Só descreve. Nada aqui é sinal de compra ou venda (24/11/2026, pedido do Diego).
"""
import csv
import glob
import os
import re
import shutil
import sys
from datetime import datetime, timezone

try:
    from agente import ler_json
except ImportError:  # rodando de fora da pasta coleta/
    from coleta.agente import ler_json

RAIZ_CODIGO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ESTUDOS = os.environ.get('INVEST_ESTUDOS', '/srv/invest/estudos')
COPIAS = ('vendidos.json', 'historico.json', 'fundamentos.json', 'balancos.json', 'relatorio.json', 'diario.json',
          'calibracao.json', 'indice.json')


def nome_arquivo(t):
    return re.sub(r'[^A-Za-z0-9._=^-]', '_', t)


def num(x):
    return '' if x is None else repr(x) if isinstance(x, float) else str(x)


def series_precos(pasta):
    """{T: [(data, abertura, máxima, mínima, fechamento, volume)]} dos precos_*.json (colunar-v1 ou o formato antigo)."""
    saida = {}
    for arq in sorted(glob.glob(os.path.join(pasta, 'precos_*.json'))):
        obj = ler_json(arq) or {}
        cal = obj.get('datas') or []
        ativos = obj.get('ativos') if obj.get('formato') == 'colunar-v1' else obj
        for t, a in (ativos or {}).items():
            if not isinstance(a, dict) or not a.get('close'):
                continue
            n = len(a['close'])
            datas = a.get('dates') or cal[a.get('i0', 0):a.get('i0', 0) + n]
            col = lambda k: a.get(k) if a.get(k) and len(a[k]) == n else [None] * n  # noqa: E731
            saida[t] = list(zip(datas, col('open'), col('high'), col('low'), a['close'], col('volume')))
    return saida


def gravar_csv(caminho, cab, linhas):
    with open(caminho, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cab)
        for ln in linhas:
            w.writerow([num(x) for x in ln])


def exportar_dados(site, dados):
    tmp = dados + '.tmp'
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    resumo, universo = {}, set()
    for mk, pasta in (('BR', os.path.join(site, 'antigo', 'data', 'br')), ('US', os.path.join(site, 'antigo', 'data'))):
        sp = series_precos(pasta)
        sp_ext = {t: v for t, v in series_precos(os.path.join(pasta, 'extras')).items() if t not in sp}  # 25/11/2026
        sp.update(sp_ext)
        if sp:
            os.makedirs(os.path.join(tmp, 'precos', mk))
        for t, linhas in sp.items():
            gravar_csv(os.path.join(tmp, 'precos', mk, nome_arquivo(t) + '.csv'),
                       ['data', 'abertura', 'maxima', 'minima', 'fechamento', 'volume'], linhas)
        universo |= set(sp)
        datas = [ln[-1][0] for ln in sp.values() if ln]
        resumo[mk] = (len(sp) - len(sp_ext), len(sp_ext), min((ln[0][0] for ln in sp.values() if ln), default=None), max(datas, default=None))
        for arq in COPIAS:
            o = os.path.join(pasta, arq)
            if os.path.isfile(o):
                shutil.copy2(o, os.path.join(tmp, f'{mk.lower()}_{arq}'))
        for arq in ('fundamentos.json', 'manifest.json'):
            o = os.path.join(pasta, 'extras', arq)
            if os.path.isfile(o):
                shutil.copy2(o, os.path.join(tmp, f'{mk.lower()}_extras_{arq}'))
    cart = ler_json(os.path.join(site, 'data', 'carteira.json')) or {}
    extra, desd = 0, []
    for t, a in (cart.get('ativos') or {}).items():
        for d in a.get('desdobramentos') or []:
            if isinstance(d, list) and len(d) >= 2:
                desd.append([t, d[0], d[1]])
        if t in universo or not a.get('datas') or not a.get('fech'):
            continue
        os.makedirs(os.path.join(tmp, 'carteira_precos'), exist_ok=True)
        usd = a.get('fechUSD') if a.get('fechUSD') and len(a['fechUSD']) == len(a['datas']) else None
        cab = ['data', 'fechamento'] + (['fechamento_usd'] if usd else [])
        gravar_csv(os.path.join(tmp, 'carteira_precos', nome_arquivo(t) + '.csv'), cab,
                   [[d, f] + ([usd[i]] if usd else []) for i, (d, f) in enumerate(zip(a['datas'], a['fech']))])
        extra += 1
    if desd:
        gravar_csv(os.path.join(tmp, 'carteira_desdobramentos.csv'), ['papel', 'data', 'fator'], desd)
    for arq in ('focus.json', 'pareceres.json', 'agente.json'):
        o = os.path.join(site, 'data', arq)
        if os.path.isfile(o):
            shutil.copy2(o, os.path.join(tmp, arq))
    with open(os.path.join(tmp, 'LEIA-ME.md'), 'w', encoding='utf-8') as f:
        f.write(leia_me(resumo, extra, cart.get('geradoEm')))
    shutil.rmtree(dados, ignore_errors=True)
    os.replace(tmp, dados)
    return resumo, extra


def leia_me(resumo, extra, cart_em):
    agora = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    lin = '\n'.join(f'- **{mk}**: {n} papéis do universo + {ne} extras da watchlist, de {de} a {ate}' for mk, (n, ne, de, ate) in resumo.items())
    return f"""# Dados do Invest (gerado em {agora})

Cópia diária, feita pela VM coletor-brasil depois da coleta (`coleta/exportar_drive.py`). A pasta é refeita do zero
a cada dia: não edite nada aqui. **Só descreve: nenhum arquivo é sinal de compra ou venda.** A estratégia técnica
está congelada desde 04/11/2026 e perdeu para o índice; os indicadores técnicos não foram testados como regra.

Convenções: retornos e distâncias em **fração** (0.05 = 5%), salvo quando o campo diz "Pct" (aí em %); preços na
**moeda do papel** (BR em R$, US em US$); datas em AAAA-MM-DD (dia do pregão).

## precos/BR/<PAPEL>.csv e precos/US/<PAPEL>.csv
Histórico diário de cerca de 5 anos, uma linha por pregão: `data,abertura,maxima,minima,fechamento,volume`
(volume em quantidade de ações). BR = carteira teórica do Ibovespa; US = os mais negociados dos EUA; mais as ações e
BDRs da watchlist fora desses universos ("extras", coletados pelo mesmo caminho). Preços **ajustados por proventos e
desdobramentos** (Yahoo, auto_adjust): retornos calculados com eles já incluem os dividendos reinvestidos.
São as mesmas séries que o app e o agente.json usam.
{lin}

## carteira_precos/<PAPEL>.csv
Ativos da carteira e da lista Acompanhando que não estão em precos/ (BTC, ETFs, FIIs…), só fechamento **sem
proventos** (a série que o motor da carteira usa para custo e proventos): `data,fechamento` em R$ e, para ativos dos
EUA, `fechamento_usd`. {extra} arquivos. Origem: data/carteira.json
(gerado em {cart_em}). `carteira_desdobramentos.csv` (`papel,data,fator`) lista os desdobramentos/grupamentos
conhecidos desses ativos.

## Arquivos JSON (prefixo br_ = Brasil, us_ = EUA)
- `*_vendidos.json`: posição vendida. BR = aluguel de ações da B3 (posições em aberto); US = short interest do
  FINRA (quinzenal). `ativos[T]`: `qtd` (ações alugadas/vendidas), BR `valor` (R$ alugados), US `qtdAnterior`,
  `variacaoPct` (% de mudança desde a leitura anterior) e `diasFinra` (dias de volume para cobrir). No agente.json, "dias" BR = dias de volume médio de 20
  pregões para zerar o aluguel; US = dias para cobrir do FINRA. Em `papeis[T].vendido` do agente.json: BR `qtd`,
  `valor` (R$), `precoMedio` (= valor ÷ qtd), `pctAcoes` (qtd ÷ ações emitidas) e `pctFloat` (qtd ÷ free float, Yahoo);
  US `qtd`, `diasFinra`, `dataFinra`, `pctFloat` (qtd FINRA ÷ float do Yahoo), `shortPctFloat`, `shortRatio`,
  `sharesShort` e `dataShortInterest` (Yahoo). A B3 não publica taxa de aluguel nem quantidade disponível nessa tabela.
- `br_extras_*` / `us_extras_*`: fundamentos e manifesto dos extras da watchlist.
- `*_historico.json`: série diária guardada pela coleta: `vendidos` (por data) e `calibracao` (resultado de cada recalibração).
- `*_fundamentos.json`: por papel: P/L (`pe`), P/VP (`pb`), `roe`, `netMargin`, `revenueGrowth`, `debtToEquity`
  (frações), setor, próxima data de balanço; desde 25/11/2026 também `operatingMargins` (margem operacional),
  `sharesOutstanding`, `floatShares`, `sharesShort` e `dateShortInterest`.
- `*_balancos.json`: balanços trimestrais (campos em `campos`; valores na moeda do papel).
- `*_relatorio.json`: o laboratório da estratégia congelada (regras de 04/11/2026) por papel: `regra`, `perfil`,
  `comparacao` (cada regra com fator de lucro `pfTreino`/`pfTeste` e nº de operações `nTreino`/`nTeste`), `treino` e
  `teste` agregados (`pf` fator de lucro, `n`, `acerto`, retornos médios em fração), `confirmada`, `situacao`,
  `suporte`/`resistencia`; `parametros` traz os parâmetros congelados. Treino = primeiros 60% do histórico do papel
  (onde a regra foi escolhida); teste = os 40% finais, não vistos na escolha.
- `*_diario.json`: teste para frente (desde 06/11/2026): cada sinal anotado no dia, com entrada, saída e retorno.
- `*_calibracao.json`: última recalibração das saídas (alvo em múltiplos de ATR e prazo em pregões), com a `tabela`
  de treino/teste de cada combinação e o `motivo` da escolha.
- `*_indice.json`: séries do índice (US: SPY, ^GSPC, ^IRX; BR: BOVA11, ^BVSP, CDI), `dates`/`close`.
- `focus.json`: boletim Focus do Banco Central (medianas em %; câmbio em R$/US$); `antes` = 4 semanas atrás.
- `pareceres.json`: pareceres do Consultor já registrados (planilha "Consultor — pareceres").
- `agente.json`: o resumo diário (< 200 KB), com a `legenda` de cada campo, inclusive os indicadores técnicos `tec`,
  `alertasDado` (dado para conferir: salto de escala, alta > 150% sem desdobramento, queda ≥ 45% além do índice, ROE >
  100%, P/L sem sentido, lucro não operacional, FINRA velho; os campos afetados por salto ficam vazios em vez de errados),
  `extra` (papel da watchlist fora do universo), `semProventos` e `saude.carteira.encerrados` (papéis que deixaram de
  negociar, com a última data na B3 e o sucessor).
"""


def exportar_biblioteca(bib):
    os.makedirs(bib, exist_ok=True)
    fontes = sorted(glob.glob(os.path.join(RAIZ_CODIGO, 'docs', '*.md'))) + \
        sorted(glob.glob(os.path.join(RAIZ_CODIGO, 'docs', 'opcoes', '*.md')))
    fontes += [os.path.join(ESTUDOS, 'cripto', 'resumo.md'), os.path.join(ESTUDOS, 'cripto', 'resultado.json'),
               os.path.join(ESTUDOS, 'auditoria', 'pedido-auditoria.md')]
    feitos = []
    for o in fontes:
        if not os.path.isfile(o):
            continue
        nome = os.path.basename(o)
        if os.sep + 'opcoes' + os.sep in o:
            nome = 'opcoes-' + nome
        elif o.startswith(ESTUDOS):
            nome = os.path.basename(os.path.dirname(o)) + '-' + nome
        shutil.copy2(o, os.path.join(bib, nome))
        feitos.append(nome)
    return feitos


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if len(argv) < 3:
        print(__doc__)
        return 2
    site, destino = argv[1], argv[2]
    resumo, extra = exportar_dados(site, os.path.join(destino, 'Dados'))
    feitos = exportar_biblioteca(os.path.join(destino, 'Biblioteca'))
    print('Dados: ' + ' · '.join(f'{mk} {n}+{ne} papéis até {ate}' for mk, (n, ne, _, ate) in resumo.items())
          + f' · carteira {extra} · Biblioteca {len(feitos)} arquivos')
    return 0


if __name__ == '__main__':
    sys.exit(main())
