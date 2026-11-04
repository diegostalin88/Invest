#!/usr/bin/env bash
# Diagnóstico (só leitura) do acesso ao aluguel de ações da B3, rodado no coletor no Brasil.
# Uso: bash coleta/diagnostico_b3.sh   (o workflow "Diagnóstico B3" roda isto sozinho)
B=https://arquivos.b3.com.br
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
mostra() { curl -s -m 30 -A "$UA" "$@" -w '\n[HTTP %{http_code}]' | head -c 300 | tr '\n' ' '; echo; }

echo "### 1. Arquivo LendingOpenPositionFile nos últimos 10 dias"
for k in $(seq 1 10); do d=$(date -d "-$k day" +%F); echo -n "$d: "; mostra "$B/api/download/requestname?fileName=LendingOpenPositionFile&date=$d"; done

echo "### 2. Outros nomes de arquivo (data de ontem útil)"
d=$(date -d "-1 day" +%F); [ "$(date -d "$d" +%u)" -ge 6 ] && d=$(date -d "last friday" +%F)
for f in LendingOpenPositionFile LendingOpenPosition SecuritiesLendingFile LendingFile BTBFile OpenPositionFile \
         LendingOpenPositionConsolidatedFile EmprestimoAtivosFile InstrumentsConsolidatedFile; do
  echo -n "$f: "; mostra "$B/api/download/requestname?fileName=$f&date=$d"; done

echo "### 3. Tabela JSON imitando o navegador"
for n in LendingOpenPosition InstrumentsConsolidated; do
  echo -n "$n: "; mostra -H 'Accept: application/json, text/plain, */*' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Dest: empty' \
    -H 'Sec-Fetch-Site: same-origin' -H "Referer: $B/tabelas/table/$n/$d/$d" "$B/tabelas/table/$n/$d/$d/1"; done

echo "### 4. Outras APIs da página"
mostra "$B/apinegocios/"
mostra "$B/api/"

dd=$(date -d "-2 day" +%F)
echo "### 5. Nomes de tabela de aluguel (dia $dd)"
for n in LendingOpenPosition LendingOpenPositions OpenPositionLending SecuritiesLending SecuritiesLendingOpenPosition \
         Lending LendingPosition BTB BTBOpenPosition LendingTrade LendingTrades AssetLending LendingBalance \
         EquitiesLending LendingOpenInterest DerivativesOpenPosition; do
  echo -n "$n: "; curl -s -m 30 -A "$UA" -H 'Accept: application/json' "$B/tabelas/table/$n/$dd/1" | head -c 120; echo; done
echo "### 6. Lista de tabelas"
for c in tables table tabelas menu categories category list api/tables tables/list; do
  echo -n "$c: "; mostra -H 'Accept: application/json' "$B/tabelas/$c"; done
echo "### 7. Endereços no código da página"
T=$(mktemp -d)
for js in main.d7e13d96.chunk.js 2.dbd3c3d4.chunk.js; do
  curl -sL -m 30 -A "$UA" "$B/tabelas/static/js/$js" -o "$T/a.js"; echo "-- $js $(wc -c < "$T/a.js") bytes"
  grep -oE '.{0,80}(table/|tables|Lending|apiUrl|cloudApi|relativeUrl|serverUrl).{0,120}' "$T/a.js" | head -25
done
rm -rf "$T"
echo "fim"
