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

echo "### 5. Site do Boletim Diário (BDI): endereços no código"
T=$(mktemp -d)
curl -sL -m 30 -A "$UA" "$B/bdi/" -o "$T/i.html"; echo "página: $(wc -c < "$T/i.html") bytes"
grep -oE "[^\"' =>]+\.js" "$T/i.html" | sort -u | while read -r js; do
  case "$js" in http*) u="$js" ;; /*) u="$B$js" ;; *) u="$B/bdi/$js" ;; esac
  curl -sL -m 30 -A "$UA" "$u" -o "$T/a.js"; echo "-- $u $(wc -c < "$T/a.js") bytes"
  grep -oE '.{0,100}(fetch\(|axios|apiUrl|cloudApi|relativeUrl|/api/|download/|Lending|Emprest|Posic).{0,160}' "$T/a.js" | head -30
done
cat "$T"/*.js 2>/dev/null | head -c 0; rm -rf "$T"
curl -sL -m 30 -A "$UA" "$B/bdi/config.js" | head -c 800; echo
echo "fim"
