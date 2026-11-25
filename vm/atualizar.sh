#!/usr/bin/env bash
# Troca o código da VM por uma versão nova (pacote .tar.gz) e republica o app com os dados atuais.
# A configuração, os dados, o diário e os caches ficam como estão.
#
# Uso: /srv/invest/codigo/vm/atualizar.sh "LINK-DO-PACOTE"
set -euo pipefail
LINK="${1:?Uso: atualizar.sh LINK-DO-PACOTE}"
TMP=$(mktemp -d)
curl -fsSL "$LINK" -o "$TMP/pacote.tar.gz"
mkdir "$TMP/codigo" && tar -xzf "$TMP/pacote.tar.gz" -C "$TMP/codigo"
[ -f "$TMP/codigo/coleta/fetch_all.py" ] || { echo "Pacote não parece ser o Invest."; exit 1; }
bash "$TMP/codigo/vm/instalar.sh"
rm -rf "$TMP"
/srv/invest/codigo/vm/coletar.sh so-app || true
