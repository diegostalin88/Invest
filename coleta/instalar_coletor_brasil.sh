#!/usr/bin/env bash
# Instala o "coletor no Brasil": uma máquina no Brasil que roda o runner do GitHub Actions
# com o rótulo "brasil" e baixa o aluguel de ações da B3 (a B3 bloqueia os servidores do GitHub).
#
# Uso (na máquina, como usuário comum com sudo, ex.: "ubuntu" na Oracle Cloud):
#   bash instalar_coletor_brasil.sh SEU_TOKEN
# O token sai em GitHub > repositório > Settings > Actions > Runners > New self-hosted runner
# (linha "./config.sh --url ... --token XXXX"). Ele vale por 1 hora.
set -euo pipefail

TOKEN="${1:-}"
REPO_URL="${REPO_URL:-https://github.com/diegostalin88/Invest}"
PASTA="$HOME/coletor-brasil"

if [ -z "$TOKEN" ]; then
  echo "Falta o token. Uso: bash $0 SEU_TOKEN"; exit 1
fi
if [ "$(id -u)" = "0" ]; then
  echo "Rode como usuário comum (ex.: ubuntu), não como root."; exit 1
fi

echo "== 1/4 Testando se esta máquina consegue falar com a B3 =="
# Usa um arquivo público que sempre existe (cadastro de instrumentos). Fora do Brasil a B3 nem responde.
ok=""
for atras in 1 2 3 4 5 6 7; do
  dia=$(date -d "-$atras day" +%F)
  resp=$(curl -s --max-time 30 -A 'Mozilla/5.0 (InvestApp)' \
    "https://arquivos.b3.com.br/api/download/requestname?fileName=InstrumentsConsolidatedFile&date=$dia" || true)
  if echo "$resp" | grep -q 'token'; then echo "   $dia -> B3 respondeu"; ok="sim"; break; fi
  echo "   $dia -> sem arquivo"
done
if [ -z "$ok" ]; then
  echo "A B3 não respondeu desta máquina. Confira se ela está numa região do Brasil (São Paulo/Vinhedo)."
  echo "Nada foi instalado."; exit 1
fi
echo "   B3 acessível. Seguindo."

echo "== 2/4 Instalando o Python =="
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv curl tar >/dev/null

echo "== 3/4 Baixando o runner do GitHub =="
case "$(uname -m)" in
  x86_64) ARQ=x64 ;;
  aarch64|arm64) ARQ=arm64 ;;
  *) echo "Arquitetura não suportada: $(uname -m)"; exit 1 ;;
esac
VERSAO=$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"].lstrip("v"))')
mkdir -p "$PASTA" && cd "$PASTA"
if [ ! -f ./config.sh ]; then
  curl -sL -o runner.tar.gz \
    "https://github.com/actions/runner/releases/download/v$VERSAO/actions-runner-linux-$ARQ-$VERSAO.tar.gz"
  tar xzf runner.tar.gz && rm runner.tar.gz
fi
sudo ./bin/installdependencies.sh >/dev/null

echo "== 4/4 Registrando no repositório e ligando como serviço =="
./config.sh --url "$REPO_URL" --token "$TOKEN" --labels brasil --name coletor-brasil \
  --unattended --replace
sudo ./svc.sh install "$USER"
sudo ./svc.sh start

echo
echo "Pronto! O coletor está ligado e volta sozinho se a máquina reiniciar."
echo "Agora, no GitHub: Settings > Secrets and variables > Actions > Variables > New variable"
echo "   Nome: COLETOR_BRASIL   Valor: sim"
