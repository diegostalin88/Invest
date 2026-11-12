#!/usr/bin/env bash
# Coleta os dados e publica o site na própria VM (faz o papel do workflow "Atualizar dados").
#
# Uso:
#   coletar.sh            coleta completa (o agendamento usa este)
#   coletar.sh 100        modo teste: só os 100 primeiros tickers
#   coletar.sh so-app     só republica o app com os dados atuais (depois de atualizar o código)
#
# O site novo é montado numa pasta separada e só entra no ar no fim, se a coleta passar no portão de
# qualidade. Se algo der errado, o site anterior continua no ar. Log: /srv/invest/logs/
set -uo pipefail

BASE="${INVEST_BASE:-/srv/invest}"
COD="$BASE/codigo"
PY="$BASE/venv/bin/python"
export PATH="$BASE/ferramentas/node/bin:$PATH"
export SITE_URL="http://127.0.0.1/data/"     # "execução anterior" = o site que está no ar nesta VM
ANTERIOR="http://127.0.0.1/data"
DIARIO="$BASE/cache/diario"
BAL="$BASE/cache/balancos"
MODO="${1:-completo}"

exec 9>"$BASE/.coleta.lock"
flock -n 9 || { echo "Outra coleta já está rodando."; exit 1; }

set -a; . "$BASE/config.env"; set +a
cd "$COD" || exit 1

hora() { date -u '+%Y-%m-%d %H:%M:%S UTC'; }
passo() { echo; echo "[$(hora)] == $* =="; }
opcional() { "$@" || echo "   (falhou, seguindo sem isso: $*)"; }

NOVO="$BASE/sites/$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$NOVO/data"
echo "[$(hora)] Início ($MODO) -> $NOVO"

if [ "$MODO" = "so-app" ]; then
  passo "Copiando os dados que estão no ar"
  [ -d "$BASE/www/data" ] || { echo "Ainda não há dados publicados. Rode uma coleta primeiro."; rm -rf "$NOVO"; exit 1; }
  cp -r "$BASE/www/data/." "$NOVO/data/"
else
  passo "Testes da coleta (sem rede)"
  "$PY" -m pytest -q coleta/tests || { echo "Testes falharam; nada publicado."; rm -rf "$NOVO"; exit 1; }

  passo "Preços e fundamentos (EUA e IBOVESPA)"
  [[ "$MODO" =~ ^[0-9]+$ ]] && export TICKER_LIMIT="$MODO"
  "$PY" coleta/fetch_all.py --saida "$NOVO/data"
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "Coleta bloqueada (código $rc; veja os motivos acima). O site anterior continua no ar."
    rm -rf "$NOVO"; exit $rc
  fi
fi

passo "Montando o site (app + registros dos testes)"
cp -r app/. "$NOVO/"
cp -r docs "$NOVO/docs"

passo "Índices de referência (SPY e BOVA11)"
opcional "$PY" coleta/indices.py "$NOVO/data"

if [ "$MODO" != "so-app" ]; then
  # Balanços: SEC e CVM uma vez por semana (como o cache semanal do Actions)
  if [ -z "$(find "$BAL/balancos_us.json" -mtime -7 2>/dev/null)" ]; then
    passo "Balanços trimestrais dos EUA (SEC; semanal)"
    ( cd coleta && timeout 40m "$PY" balancos_sec.py "$NOVO/data" "$BAL/novo.json" --limite 1000 | tail -2 ) \
      && mv "$BAL/novo.json" "$BAL/balancos_us.json" || echo "   (falhou; usa os da semana anterior se houver)"
    passo "Balanços trimestrais do Brasil (CVM; semanal)"
    if [ -f "$NOVO/data/br/manifest.json" ]; then
      mkdir -p "$BAL/br" && cp "$NOVO/data/br/manifest.json" "$BAL/br/"
      for f in $("$PY" -c "import json;print(' '.join(json.load(open('$NOVO/data/br/manifest.json'))['arquivosPrecos']))"); do cp "$NOVO/data/br/$f" "$BAL/br/"; done
      opcional timeout 30m "$PY" coleta/balancos_cvm.py "$BAL/br"
      rm -f "$BAL"/br/precos_*.json
    fi
  fi
fi

passo "Histórico de balanços para o app"
[ -f "$BAL/balancos_us.json" ] && opcional "$PY" coleta/balancos_app.py "$BAL/balancos_us.json" "$NOVO/data"
if [ -f "$BAL/br/balancos.json" ] && [ -f "$NOVO/data/br/manifest.json" ]; then
  cp "$BAL/br/balancos.json" "$NOVO/data/br/"
  "$PY" -c "import json;p='$NOVO/data/br/manifest.json';m=json.load(open(p));m['arquivoBalancos']='balancos.json';json.dump(m,open(p,'w'),ensure_ascii=False,indent=2)"
fi

passo "Vendidos (aluguel B3 direto daqui do Brasil e short interest FINRA)"
opcional "$PY" coleta/vendidos.py --saida "$NOVO/data"

passo "Diário de sinais e calibração anteriores"
opcional "$PY" coleta/diario_anterior.py "$NOVO/data" "$ANTERIOR" "$DIARIO"

passo "Relatório automático (navegador invisível)"
opcional timeout 60m node coleta/gerar_relatorio.js "$NOVO"

passo "Histórico diário de vendidos e da recalibração"
opcional "$PY" coleta/historico.py "$NOVO/data" "$ANTERIOR" "$DIARIO"

passo "Cópia de segurança do diário"
mkdir -p "$DIARIO/br"
for f in diario.json calibracao.json historico.json; do
  cp "$NOVO/data/$f" "$DIARIO/" 2>/dev/null || true
  cp "$NOVO/data/br/$f" "$DIARIO/br/" 2>/dev/null || true
done

passo "Publicando"
ln -sfn "$NOVO" "$BASE/www.tmp" && mv -T "$BASE/www.tmp" "$BASE/www"
# guarda só as 3 últimas versões do site (a provisória "inicial" sai assim que houver dados)
ls -1d "$BASE"/sites/*/ | sort | head -n -3 | xargs -r rm -rf
du -sh "$NOVO/data" | sed 's/^/   dados: /'
"$PY" -c "import json;m=json.load(open('$NOVO/data/manifest.json'));print('   último pregão:', m.get('ultimoPregao'), '| tickers:', (m.get('stats') or {}).get('tickersPrecos'))" 2>/dev/null
echo "[$(hora)] Fim. Site no ar."
