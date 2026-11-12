#!/usr/bin/env bash
# Hipótese K (cripto): roda o teste registrado em docs/hipotese-cripto.md com dados públicos
# (Binance data.binance.vision, Banco Central, Yahoo). Não usa conta nenhuma.
# Resultado em http://IP-DA-VM/estudos/cripto/  (resumo.md e resultado.json). Leva de 30 min a 2 h.
#
# Uso: /srv/invest/codigo/vm/cripto.sh            (em segundo plano: nohup ... &)
set -uo pipefail
BASE="${INVEST_BASE:-/srv/invest}"
SAIDA="$BASE/estudos/cripto"
mkdir -p "$SAIDA" "$BASE/cache/cripto"
cd "$BASE/codigo"
echo "[$(date -u '+%F %T UTC')] Hipótese K (cripto) começando"
"$BASE/venv/bin/python" coleta/testar_cripto.py --saida "$SAIDA" --cache "$BASE/cache/cripto"
rc=$?
echo "[$(date -u '+%F %T UTC')] Fim (código $rc). Resumo:"
cat "$SAIDA/resumo.md" 2>/dev/null
exit $rc
