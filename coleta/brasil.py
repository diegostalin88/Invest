"""
brasil.py — coleta do mercado brasileiro (ações do IBOVESPA) para o app Invest.

Chamado pelo fetch_all.py depois da coleta americana. Reaproveita as mesmas funções (download em
lotes, arredondamento, formato colunar, cache incremental de fundamentos, manifesto e portão de
qualidade), com estas diferenças:
  - Universo: carteira teórica do IBOVESPA do dia, lida do site da B3. Se a B3 não responder, usa
    coleta/ibovespa_reserva.txt.
  - Yahoo usa o sufixo ".SA" (PETR4 -> PETR4.SA); nos arquivos o ticker fica sem o sufixo.
  - Sem pré-filtro de liquidez (todas as ações do índice já são líquidas), só o mínimo de pregões.
  - Fundamentos do Yahoo para todas; sem radar de 8-K (a B3 não arquiva na SEC).
  - Valores em R$.
Uma falha aqui NUNCA bloqueia a publicação dos dados americanos: se o Brasil der problema, os
dados brasileiros publicados anteriormente são mantidos (ou o app mostra que estão indisponíveis).
"""
import base64
import gzip
import json
import os
import shutil
from datetime import datetime, timezone

import fetch_all as fa

URL_CARTEIRA_B3 = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/"
ARQUIVO_RESERVA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ibovespa_reserva.txt')
SUFIXO = '.SA'
MIN_ATIVOS_CARTEIRA = 50   # menos que isso = resposta da B3 suspeita -> usa a reserva


def ler_reserva(caminho=ARQUIVO_RESERVA):
    tickers = []
    with open(caminho, encoding='utf-8') as f:
        for linha in f:
            linha = linha.split('#', 1)[0]
            tickers += [t.strip().upper() for t in linha.split() if t.strip()]
    return list(dict.fromkeys(tickers))


def baixar_carteira_ibovespa():
    """Devolve (tickers, fonte). fonte = 'B3' ou 'lista de reserva'."""
    params = {"language": "pt-br", "pageNumber": 1, "pageSize": 200, "index": "IBOV", "segment": "1"}
    url = URL_CARTEIRA_B3 + base64.b64encode(json.dumps(params).encode()).decode()
    try:
        resp = fa.requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (InvestApp)'})
        resp.raise_for_status()
        cods = [str(r.get('cod', '')).strip().upper() for r in (resp.json().get('results') or [])]
        cods = [c for c in dict.fromkeys(cods) if c]
        if len(cods) >= MIN_ATIVOS_CARTEIRA:
            fa.log(f"  Carteira do IBOVESPA lida da B3: {len(cods)} ações.")
            return cods, 'B3'
        fa.log(f"  AVISO: a B3 devolveu só {len(cods)} ações; usando a lista de reserva.")
    except Exception as e:
        fa.log(f"  AVISO: não consegui ler a carteira do IBOVESPA na B3 ({e}); usando a lista de reserva.")
    reserva = ler_reserva()
    fa.log(f"  Lista de reserva: {len(reserva)} ações.")
    return reserva, 'lista de reserva'


def _restaurar_publicado(saida_br, url_br):
    """Copia os dados brasileiros já publicados para saida_br. Devolve True se conseguiu."""
    shutil.rmtree(saida_br, ignore_errors=True)
    manifesto = fa.baixar_json_publicado('manifest.json', url_br)
    if not manifesto:
        return False
    os.makedirs(saida_br, exist_ok=True)
    nomes = list(manifesto.get('arquivosPrecos', [])) + [manifesto.get('arquivoFundamentos', 'fundamentos.json')]
    for nome in nomes:
        obj = fa.baixar_json_publicado(nome, url_br)
        if obj is None:
            shutil.rmtree(saida_br, ignore_errors=True)
            return False
        with open(os.path.join(saida_br, nome), 'w', encoding='utf-8') as f:
            f.write(fa._json_compacto(obj))
    with open(os.path.join(saida_br, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)
    return True


def coletar_brasil(saida_br, url_br, hoje):
    """Roda a coleta brasileira. Devolve as linhas do resumo (markdown)."""
    fa.log("\n=== BRASIL: carteira do IBOVESPA ===")
    try:
        manifesto_anterior = fa.baixar_json_publicado('manifest.json', url_br)
        cache = fa.baixar_json_publicado('fundamentos.json', url_br) or {}
        carteira, fonte = baixar_carteira_ibovespa()

        brutos_sa, lotes_falhos = fa.baixar_precos([t + SUFIXO for t in carteira], fa.ANOS_HISTORICO)
        brutos = {t[:-len(SUFIXO)] if t.endswith(SUFIXO) else t: s for t, s in brutos_sa.items()}
        fa.remover_duplicatas(brutos)
        precos = fa.aplicar_prefiltro_precos(brutos, min_adtv=0)
        fa.log(f"  Preços: {len(precos)} de {len(carteira)} ações com >= {fa.MIN_PREGOES} pregões.")

        pool = sorted(precos)
        price_lookup = {t: fa.arredondar_preco(precos[t]['close'][-1]) for t in pool}
        fundamentos, fstats = fa.atualizar_fundamentos(pool, cache, price_lookup, hoje, {},
                                                       sufixo_yahoo=SUFIXO, radar=False)

        arquivos, anos, avisos = fa.gerar_saida(precos, fa.ANOS_HISTORICO)
        ultimo = fa.calcular_ultimo_pregao(precos)
        if fonte != 'B3':
            avisos.append("Carteira do IBOVESPA veio da lista de reserva (o site da B3 não respondeu); pode estar desatualizada.")
        faltando = [t for t in carteira if t not in precos]
        if faltando:
            avisos.append(f"{len(faltando)} ação(ões) da carteira sem histórico suficiente no Yahoo: {', '.join(faltando[:15])}"
                          + ('…' if len(faltando) > 15 else ''))
        fund_bytes = fa._json_compacto(fundamentos).encode('utf-8')
        stats = {'tickersPrecos': len(precos), 'tickersFundamentos': len(fundamentos),
                 'fundamentosComDados': fstats['comDados'], 'fundamentosAtualizadosHoje': fstats['atualizadosHoje'],
                 'alertasCriticos': 0, 'carteiraIbovespa': len(carteira)}
        tamanhos = {'precosBytes': sum(len(b) for _, b in arquivos), 'fundamentosBytes': len(fund_bytes),
                    'precosGzipBytes': sum(len(gzip.compress(b, 6)) for _, b in arquivos)}
        gerado_em = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        manifesto = fa.montar_manifesto(gerado_em, ultimo, anos, [n for n, _ in arquivos], stats, avisos, tamanhos,
                                        mercado='br', moeda='BRL')
        erros = fa.portao_qualidade(manifesto, manifesto_anterior, fundamentos, hoje)
    except Exception as e:  # nunca derruba a coleta americana
        fa.log(f"ERRO na coleta do Brasil: {e!r}")
        erros, stats, fonte, lotes_falhos = [f"Erro inesperado: {e}"], {}, '?', 0

    if erros:
        mantido = _restaurar_publicado(saida_br, url_br)
        return ["", "## 🇧🇷 Brasil: ⚠️ coleta com problema — "
                + ("mantidos os dados publicados anteriormente" if mantido else "sem dados do Brasil nesta publicação"),
                ""] + [f"- {e}" for e in erros]

    shutil.rmtree(saida_br, ignore_errors=True)
    os.makedirs(saida_br)
    for nome, conteudo in arquivos:
        with open(os.path.join(saida_br, nome), 'wb') as f:
            f.write(conteudo)
    with open(os.path.join(saida_br, 'fundamentos.json'), 'wb') as f:
        f.write(fund_bytes)
    with open(os.path.join(saida_br, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)
    linhas = ["", "## 🇧🇷 Brasil (IBOVESPA): ✅ concluída", "", "| Item | Valor |", "|---|---|",
              f"| Último pregão | {ultimo} |",
              f"| Carteira do índice | {len(carteira)} ações (fonte: {fonte}) |",
              f"| Com preço | {stats['tickersPrecos']} (lotes com falha: {lotes_falhos}) |",
              f"| Fundamentos | {stats['tickersFundamentos']} (com dados: {stats['fundamentosComDados']}; atualizados hoje: {stats['fundamentosAtualizadosHoje']}) |",
              f"| Tamanho | {fa.mb(tamanhos['precosBytes'] + len(fund_bytes)):.1f} MB |"]
    if avisos:
        linhas += [""] + [f"- ⚠️ {a}" for a in avisos]
    return linhas
