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

echo "### 5. Endereços que o site da tabela usa (lidos do código da página)"
T=$(mktemp -d)
curl -s -m 30 -A "$UA" "$B/tabelas/table/LendingOpenPosition/$d/$d" -o "$T/index.html"
echo "   página: $(wc -c < "$T/index.html") bytes"
grep -oiE '<script[^>]*>' "$T/index.html" | head -10
grep -oE "[^\"' =>]+\.js" "$T/index.html" | sort -u | while read -r js; do
  case "$js" in http*) u="$js" ;; /*) u="$B$js" ;; *) u="$B/tabelas/$js" ;; esac
  echo "-- $u"
  curl -s -m 30 -A "$UA" "$u" -o "$T/a.js"
  if ! grep -q 'function' "$T/a.js" 2>/dev/null; then u="$B/$js"; echo "   (tentando $u)"; curl -s -m 30 -A "$UA" "$u" -o "$T/a.js"; fi
  echo "   $(wc -c < "$T/a.js") bytes"
  grep -oE '"[^"]{0,60}(table|Table|api|download|Lending|requestname)[^"]{0,80}"' "$T/a.js" | sort -u | head -40
  grep -oE '.{0,120}(\.get|fetch)\(.{0,160}' "$T/a.js" | head -15
done
rm -rf "$T"
echo "fim"
