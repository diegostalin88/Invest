#!/usr/bin/env bash
# Coleta enxuta do app de carteira (desde 07/11/2026): BOVA11, IVVB11, BTC, CDI e IPCA, em segundos.
# A coleta pesada antiga (3.481 papéis, balanços, vendidos, relatório) foi desligada a pedido do Diego;
# o script dela ficou em vm/coletar-antigo.sh e o app antigo fica congelado em /antigo/.
#
# Uso:
#   coletar.sh          baixa os dados e publica (o agendamento usa este)
#   coletar.sh so-app   só republica o app com os dados atuais (depois de atualizar o código)
#
# O site novo é montado numa pasta separada e só entra no ar no fim. Se o download falhar, o app vai com os
# dados da versão anterior. Log: /srv/invest/logs/coleta.log
set -uo pipefail

BASE="${INVEST_BASE:-/srv/invest}"
COD="$BASE/codigo"
PY="$BASE/venv/bin/python"
MODO="${1:-completo}"

exec 9>"$BASE/.coleta.lock"
flock -n 9 || { echo "Outra coleta já está rodando."; exit 1; }
[ -f "$BASE/config.env" ] && { set -a; . "$BASE/config.env"; set +a; }
cd "$COD" || exit 1

hora() { date -u '+%Y-%m-%d %H:%M:%S UTC'; }
passo() { echo; echo "[$(hora)] == $* =="; }

NOVO="$BASE/sites/$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$NOVO/data"
echo "[$(hora)] Início ($MODO) -> $NOVO"

passo "App"
cp -r app/. "$NOVO/"

ANTES="$BASE/www/data/carteira.json"
if [ "$MODO" != "so-app" ]; then
  passo "Testes (sem rede)"
  "$PY" -m pytest -q coleta/tests/test_carteira_dados.py || { echo "Testes falharam; nada publicado."; rm -rf "$NOVO"; exit 1; }
  passo "Preços (Yahoo) e CDI, IPCA e PTAX (Banco Central)"
  # papéis extras: um código por linha em $BASE/codigos-br.txt (B3) e $BASE/codigos-eua.txt (EUA), opcionais
  CARTEIRA_EXTRAS_ARQUIVO="$BASE/codigos-br.txt" CARTEIRA_EUA_ARQUIVO="$BASE/codigos-eua.txt" timeout 15m "$PY" coleta/carteira_dados.py "$NOVO/data"
  rc=$?
  [ $rc -eq 2 ] && echo "   (algum ativo extra falhou; os outros foram gravados)"
fi
if [ ! -s "$NOVO/data/carteira.json" ]; then
  if [ -s "$ANTES" ]; then echo "   Usando os dados da versão anterior."; cp "$ANTES" "$NOVO/data/"; else echo "Sem dados para publicar."; rm -rf "$NOVO"; exit 1; fi
fi

passo "App antigo congelado em /antigo/"
[ -d "$BASE/antigo" ] && ln -sfn "$BASE/antigo" "$NOVO/antigo"

passo "Publicando"
ln -sfn "$NOVO" "$BASE/www.tmp" && mv -T "$BASE/www.tmp" "$BASE/www"
# guarda só as 3 últimas versões
ls -1d "$BASE"/sites/*/ | sort | head -n -3 | xargs -r rm -rf
du -sh "$NOVO/data" | sed 's/^/   dados: /'
echo "[$(hora)] Fim. Site no ar."
