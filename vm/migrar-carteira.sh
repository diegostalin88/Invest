#!/usr/bin/env bash
# Passagem única (07/11/2026) do app antigo para o app de carteira. Pode repetir sem estragar nada.
#  1. guarda o site que está no ar hoje em /srv/invest/antigo (servido em http://IP/antigo/, sem atualizar)
#  2. guarda uma cópia do código antigo em /srv/invest/backup/
#  3. copia o código novo (pasta passada como argumento) para /srv/invest/codigo
#  4. roda a coleta enxuta e publica. O agendamento (cron 22:30 UTC seg–sex) continua chamando vm/coletar.sh,
#     que agora é a coleta enxuta.
# Uso: bash migrar-carteira.sh /caminho/do/codigo-novo
set -euo pipefail
BASE="${INVEST_BASE:-/srv/invest}"
NOVO_COD="${1:?Uso: migrar-carteira.sh PASTA-DO-CODIGO-NOVO}"
[ -f "$NOVO_COD/app/motor-carteira.js" ] && [ -f "$NOVO_COD/coleta/carteira_dados.py" ] || { echo "Pasta não tem o app de carteira."; exit 1; }
DATA=$(date -u +%Y%m%d-%H%M%S)
mkdir -p "$BASE/backup"

if [ ! -d "$BASE/antigo" ]; then
  ATUAL=$(readlink -f "$BASE/www")
  echo "Guardando o site atual ($ATUAL) em $BASE/antigo"
  cp -a "$ATUAL" "$BASE/antigo.tmp" && rm -f "$BASE/antigo.tmp/antigo" && mv "$BASE/antigo.tmp" "$BASE/antigo"
fi
echo "Backup do código antigo: $BASE/backup/codigo-$DATA.tar.gz"
tar -czf "$BASE/backup/codigo-$DATA.tar.gz" -C "$BASE" codigo

echo "Copiando o código novo"
rsync -a --exclude .git "$NOVO_COD/" "$BASE/codigo/"
chmod +x "$BASE/codigo/vm/"*.sh
"$BASE/venv/bin/python" -c "import pytest, yfinance, requests" 2>/dev/null || "$BASE/venv/bin/python" -m pip install -q pytest yfinance requests

"$BASE/codigo/vm/coletar.sh"
echo
echo "Pronto. App novo: http://$(curl -s -m 5 ifconfig.me 2>/dev/null || echo IP-DA-VM)/  ·  app antigo: /antigo/"
