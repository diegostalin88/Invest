#!/usr/bin/env bash
# Coleta única do Invest na VM (desde 12/11/2026, fase 1 da remodelação). Roda em sequência, nunca em paralelo
# (a VM tem ~1 GB de memória):
#   1. carteira: BOVA11, IVVB11, BTC, extras, CDI, IPCA e PTAX (segundos)          -> /data/carteira.json
#   2. mercado: os EUA mais negociados (lista em cache/universo-eua.txt) + Ibovespa,  -> /antigo/data/
#      fundamentos, índices, balanços (semanal), vendidos, diário e relatório da estratégia congelada
#   3. agente.json: resumo de menos de 100 KB para o agente analista                  -> /data/agente.json
#   4. (opcional) cópia do agente.json para o Google Drive, se RCLONE_DESTINO estiver no config.env
# Se o mercado falhar, a carteira publica do mesmo jeito e /antigo/ continua com os dados anteriores.
#
# Uso:
#   coletar.sh               tudo (o agendamento usa este)
#   coletar.sh so-carteira   só a parte 1 (e o agente com o mercado anterior)
#   coletar.sh so-app        só republica os apps com os dados atuais (depois de atualizar o código)
#   coletar.sh 50            modo teste: mercado só com os 50 primeiros papéis da lista
#
# O site novo é montado numa pasta separada e só entra no ar no fim. Log: /srv/invest/logs/coleta.log
# A versão anterior deste script (só carteira) e a antiga (universo completo) ficam no histórico dos pacotes;
# vm/coletar-antigo.sh continua aqui só como referência.
set -uo pipefail

BASE="${INVEST_BASE:-/srv/invest}"
COD="$BASE/codigo"
PY="$BASE/venv/bin/python"
export PATH="$BASE/ferramentas/node/bin:$PATH"
MODO="${1:-completo}"
N_EUA="${UNIVERSO_N:-500}"
LISTA="$BASE/cache/universo-eua.txt"
DIARIO="$BASE/cache/diario"
BAL="$BASE/cache/balancos"
export SITE_URL="http://127.0.0.1/antigo/data/"   # execução anterior do mercado = o que está no ar
ANTERIOR="http://127.0.0.1/antigo/data"

exec 9>"$BASE/.coleta.lock"
flock -n 9 || { echo "Outra coleta já está rodando."; exit 1; }
[ -f "$BASE/config.env" ] && { set -a; . "$BASE/config.env"; set +a; }
cd "$COD" || exit 1

hora() { date -u '+%Y-%m-%d %H:%M:%S UTC'; }
passo() { echo; echo "[$(hora)] == $* =="; }
opcional() { "$@" || echo "   (falhou, seguindo sem isso: $*)"; }

NOVO="$BASE/sites/$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$NOVO/data" "$BASE/cache"
echo "[$(hora)] Início ($MODO) -> $NOVO"

# ---------------------------------------------------------------- apps
passo "Apps (carteira na raiz, app de investimento em /antigo/)"
cp -r app/. "$NOVO/"
cp -r docs "$NOVO/docs"
mkdir -p "$NOVO/antigo"
# arquivos do app antigo como estão no ar hoje (ícones, estudos...), sem os dados; o index vem do código
[ -d "$BASE/antigo" ] && tar -C "$BASE/antigo" --exclude=./data --exclude=./antigo -cf - . | tar -C "$NOVO/antigo" -xf -
[ -f antigo/index.html ] && cp antigo/index.html "$NOVO/antigo/index.html"
cp -r docs "$NOVO/antigo/docs"

# Dados de mercado no ar agora (para reaproveitar se esta coleta não trouxer novos)
NO_AR="$(readlink -f "$BASE/www")/antigo/data"
[ -d "$NO_AR" ] || NO_AR="$BASE/antigo/data"
usar_mercado_anterior() {
  rm -rf "$NOVO/antigo/data"
  if [ -d "$NO_AR" ]; then echo "   Mercado: mantidos os dados anteriores ($NO_AR)."; cp -a "$NO_AR" "$NOVO/antigo/data"; fi
}

# ---------------------------------------------------------------- 1. carteira
ANTES="$BASE/www/data/carteira.json"
if [ "$MODO" != "so-app" ]; then
  passo "Testes (sem rede)"
  "$PY" -m pytest -q coleta/tests || { echo "Testes falharam; nada publicado."; rm -rf "$NOVO"; exit 1; }
  passo "Carteira: preços (Yahoo) e CDI, IPCA e PTAX (Banco Central)"
  # papéis extras: um código por linha em $BASE/codigos-br.txt (B3) e $BASE/codigos-eua.txt (EUA), opcionais
  CARTEIRA_EXTRAS_ARQUIVO="$BASE/codigos-br.txt" CARTEIRA_EUA_ARQUIVO="$BASE/codigos-eua.txt" timeout 15m "$PY" coleta/carteira_dados.py "$NOVO/data"
  rc=$?
  [ $rc -eq 2 ] && echo "   (algum ativo extra falhou; os outros foram gravados)"
fi
if [ ! -s "$NOVO/data/carteira.json" ]; then
  if [ -s "$ANTES" ]; then echo "   Usando os dados da carteira da versão anterior."; cp "$ANTES" "$NOVO/data/"; else echo "Sem dados da carteira para publicar."; rm -rf "$NOVO"; exit 1; fi
fi

# ---------------------------------------------------------------- 2. mercado
if [ "$MODO" = "completo" ] || [[ "$MODO" =~ ^[0-9]+$ ]]; then
  passo "Mercado: universo dos mais negociados ($N_EUA nos EUA + Ibovespa)"
  RENOVAR=""
  MARCA="$BASE/cache/universo-renovado-$(date -u +%Y-%m)"
  [ -f "$MARCA" ] || RENOVAR="--renovar"
  if "$PY" coleta/universo_liquido.py montar "$LISTA" "$BASE/cache/universo-hoje.txt" --dados "$NO_AR" --n "$N_EUA" $RENOVAR; then
    export UNIVERSO_ARQUIVO="$BASE/cache/universo-hoje.txt"
    [ -n "$RENOVAR" ] && touch "$MARCA"
  else
    echo "   Sem lista dos mais negociados: mercado pulado hoje (não baixa o universo completo)."
    MERCADO_OK=0
  fi
  [[ "$MODO" =~ ^[0-9]+$ ]] && export TICKER_LIMIT="$MODO"

  if [ "${MERCADO_OK:-1}" = 1 ]; then
    passo "Mercado: preços e fundamentos (EUA e Ibovespa)"
    timeout 120m "$PY" coleta/fetch_all.py --saida "$NOVO/antigo/data"
    rc=$?
    if [ $rc -ne 0 ]; then echo "   Coleta de mercado bloqueada (código $rc; motivos acima)."; MERCADO_OK=0; fi
  fi

  if [ "${MERCADO_OK:-1}" = 1 ]; then
    M="$NOVO/antigo/data"
    [[ "$MODO" =~ ^[0-9]+$ ]] || opcional "$PY" coleta/universo_liquido.py reordenar "$LISTA" "$M" --n "$N_EUA"
    passo "Índices de referência (SPY e BOVA11)"
    opcional "$PY" coleta/indices.py "$M"

    if [ -z "$(find "$BAL/balancos_us.json" -mtime -7 2>/dev/null)" ]; then
      passo "Balanços trimestrais dos EUA (SEC; semanal)"
      mkdir -p "$BAL"
      ( cd coleta && timeout 40m "$PY" balancos_sec.py "$M" "$BAL/novo.json" --limite 1000 | tail -2 ) \
        && mv "$BAL/novo.json" "$BAL/balancos_us.json" || echo "   (falhou; usa os da semana anterior se houver)"
      passo "Balanços trimestrais do Brasil (CVM; semanal)"
      if [ -f "$M/br/manifest.json" ]; then
        mkdir -p "$BAL/br" && cp "$M/br/manifest.json" "$BAL/br/"
        for f in $("$PY" -c "import json;print(' '.join(json.load(open('$M/br/manifest.json'))['arquivosPrecos']))"); do cp "$M/br/$f" "$BAL/br/"; done
        opcional timeout 30m "$PY" coleta/balancos_cvm.py "$BAL/br"
        rm -f "$BAL"/br/precos_*.json
      fi
    fi
    passo "Histórico de balanços para o app"
    [ -f "$BAL/balancos_us.json" ] && opcional "$PY" coleta/balancos_app.py "$BAL/balancos_us.json" "$M"
    if [ -f "$BAL/br/balancos.json" ] && [ -f "$M/br/manifest.json" ]; then
      cp "$BAL/br/balancos.json" "$M/br/"
      "$PY" -c "import json;p='$M/br/manifest.json';m=json.load(open(p));m['arquivoBalancos']='balancos.json';json.dump(m,open(p,'w'),ensure_ascii=False,indent=2)"
    fi

    passo "Vendidos (aluguel B3 direto daqui do Brasil e short interest FINRA)"
    opcional "$PY" coleta/vendidos.py --saida "$M"

    passo "Diário de sinais e calibração anteriores"
    opcional "$PY" coleta/diario_anterior.py "$M" "$ANTERIOR" "$DIARIO"

    # Diário: todo pregão (o teste para frente da estratégia congelada depende dele; ver docs/congelamento.md)
    passo "Relatório da estratégia congelada (navegador invisível)"
    opcional timeout 60m node coleta/gerar_relatorio.js "$NOVO/antigo"

    passo "Histórico diário de vendidos e da recalibração"
    opcional "$PY" coleta/historico.py "$M" "$ANTERIOR" "$DIARIO"

    passo "Cópia de segurança do diário"
    mkdir -p "$DIARIO/br"
    for f in diario.json calibracao.json historico.json; do
      cp "$M/$f" "$DIARIO/" 2>/dev/null || true
      cp "$M/br/$f" "$DIARIO/br/" 2>/dev/null || true
    done
  else
    usar_mercado_anterior
  fi
else
  usar_mercado_anterior
fi

# ---------------------------------------------------------------- 3. agente
passo "agente.json (resumo para o agente analista)"
opcional "$PY" coleta/agente.py "$NOVO"

# ---------------------------------------------------------------- publicar
passo "Publicando"
ln -sfn "$NOVO" "$BASE/www.tmp" && mv -T "$BASE/www.tmp" "$BASE/www"
# guarda só as 3 últimas versões
ls -1d "$BASE"/sites/*/ | sort | head -n -3 | xargs -r rm -rf
du -sh "$NOVO/data" "$NOVO/antigo/data" 2>/dev/null | sed 's/^/   /'
"$PY" -c "import json;m=json.load(open('$NOVO/antigo/data/manifest.json'));print('   mercado: último pregão', m.get('ultimoPregao'), '| papéis EUA:', (m.get('stats') or {}).get('tickersPrecos'))" 2>/dev/null

# ---------------------------------------------------------------- 4. Drive (opcional)
if [ -n "${RCLONE_DESTINO:-}" ] && command -v rclone >/dev/null && [ -s "$NOVO/data/agente.json" ]; then
  passo "Cópia do agente.json para o Google Drive ($RCLONE_DESTINO)"
  opcional timeout 5m rclone copyto "$NOVO/data/agente.json" "$RCLONE_DESTINO/agente.json"
fi
echo "[$(hora)] Fim. Site no ar."
