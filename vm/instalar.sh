#!/usr/bin/env bash
# Instala o Invest numa VM Ubuntu (Oracle Cloud), no lugar do GitHub Actions + GitHub Pages.
#
# O que faz:
#   1. memória extra (swap), fuso UTC, programas (nginx, git, Python 3.13 via uv, Node 22, Chromium)
#   2. copia o código para /srv/invest/codigo e pergunta o e-mail de contato exigido pela SEC
#   3. nginx servindo o app em http://IP-DA-VM/ (e os estudos em /estudos/)
#   4. abre a porta 80 no firewall interno da VM
#   5. agenda a coleta seg–sex 22:30 UTC (19:30 em Brasília)
#   6. desliga o antigo runner do GitHub (a conta está suspensa; ele só ficaria tentando conectar)
#
# Uso (dentro da pasta do código descompactado):  bash vm/instalar.sh
# Pode rodar de novo sem problema (ex.: depois de atualizar o código).
set -euo pipefail

BASE=/srv/invest
EU="$(id -un)"
ORIGEM="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$(id -u)" = "0" ]; then echo "Rode como usuário comum (ex.: ubuntu), não como root."; exit 1; fi

echo "== 1/7 Memória extra (swap de 4 GB) e fuso UTC =="
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo timedatectl set-timezone UTC || true
echo "   $(nproc) processador(es), $(free -h | awk '/Mem:/{print $2}') de RAM, $(df -h / | awk 'NR==2{print $4}') livres no disco"

echo "== 2/7 Programas do sistema =="
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx git curl tar xz-utils ca-certificates iptables-persistent >/dev/null

sudo mkdir -p "$BASE" && sudo chown "$EU:$EU" "$BASE"
mkdir -p "$BASE"/{sites,estudos,logs,cache/balancos,cache/diario,ferramentas}

echo "== 3/7 Código =="
if [ "$ORIGEM" != "$BASE/codigo" ]; then
  rm -rf "$BASE/codigo.novo" && cp -r "$ORIGEM" "$BASE/codigo.novo"
  rm -rf "$BASE/codigo" && mv "$BASE/codigo.novo" "$BASE/codigo"
fi
chmod +x "$BASE"/codigo/vm/*.sh

if [ ! -f "$BASE/config.env" ]; then
  echo
  echo "A SEC (bolsa americana) exige um e-mail de contato em cada pedido de dados."
  read -r -p "Digite seu e-mail: " EMAIL < /dev/tty
  printf 'SEC_USER_AGENT="InvestDiego %s"\n' "$EMAIL" > "$BASE/config.env"
fi

echo "== 4/7 Python 3.13 e bibliotecas (pode levar alguns minutos) =="
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
[ -x "$BASE/venv/bin/python" ] || "$UV" venv -q -p 3.13 "$BASE/venv"
"$UV" pip install -q -p "$BASE/venv/bin/python" -r "$BASE/codigo/coleta/requirements.txt"

echo "== 5/7 Node 22 e navegador invisível (para o relatório) =="
case "$(uname -m)" in x86_64) NARQ=x64 ;; aarch64|arm64) NARQ=arm64 ;; *) echo "Arquitetura não suportada"; exit 1 ;; esac
if [ ! -x "$BASE/ferramentas/node/bin/node" ]; then
  NV=$(curl -fsSL https://nodejs.org/dist/index.json | "$BASE/venv/bin/python" -c "import json,sys;print(next(v['version'] for v in json.load(sys.stdin) if v['version'].startswith('v22.')))")
  curl -fsSL "https://nodejs.org/dist/$NV/node-$NV-linux-$NARQ.tar.xz" | tar -xJ -C "$BASE/ferramentas"
  mv "$BASE/ferramentas/node-$NV-linux-$NARQ" "$BASE/ferramentas/node"
fi
export PATH="$BASE/ferramentas/node/bin:$PATH"
# Fica em /srv/invest/node_modules: o require('playwright') de codigo/coleta/*.js acha subindo as pastas
[ -f "$BASE/package.json" ] || echo '{"private":true}' > "$BASE/package.json"
( cd "$BASE" && npm install -s --no-audit --no-fund playwright@1.48.2 >/dev/null )
( cd "$BASE" && sudo env PATH="$PATH" ./node_modules/.bin/playwright install-deps chromium >/dev/null )
( cd "$BASE" && ./node_modules/.bin/playwright install chromium >/dev/null )

echo "== 6/7 Site (nginx) e firewall =="
sudo tee /etc/nginx/sites-available/invest >/dev/null <<NGX
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root $BASE/www;
    index index.html;
    charset utf-8;
    gzip on;
    gzip_types application/json text/css application/javascript text/markdown text/plain;
    location /data/ { add_header Cache-Control "no-cache"; }
    location = /sw.js { add_header Cache-Control "no-cache"; }
    location ^~ /estudos/ { alias $BASE/estudos/; autoindex on; types { text/plain md; application/json json; } charset utf-8; }
    location ~ \.md\$ { default_type "text/plain; charset=utf-8"; }
}
NGX
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sfn /etc/nginx/sites-available/invest /etc/nginx/sites-enabled/invest
# nginx (usuário www-data) precisa ler /srv/invest
sudo chmod o+rx "$BASE"
if [ ! -e "$BASE/www" ]; then   # página provisória até a primeira coleta
  mkdir -p "$BASE/sites/inicial" && cp -r "$BASE/codigo/app/." "$BASE/sites/inicial/"
  ln -sfn "$BASE/sites/inicial" "$BASE/www"
fi
sudo nginx -t -q && sudo systemctl enable -q --now nginx && sudo systemctl reload nginx
# As imagens Ubuntu da Oracle bloqueiam tudo menos SSH no firewall interno
if ! sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null; then
  sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
  sudo netfilter-persistent save >/dev/null 2>&1 || true
fi

echo "== 7/7 Agendamento e limpeza do runner antigo =="
if [ -x "$HOME/coletor-brasil/svc.sh" ]; then
  ( cd "$HOME/coletor-brasil" && sudo ./svc.sh stop >/dev/null 2>&1; sudo ./svc.sh uninstall >/dev/null 2>&1 ) || true
  echo "   runner antigo do GitHub desligado"
fi
( { crontab -l 2>/dev/null | grep -v '/srv/invest/codigo/vm/' || true; } ; cat <<CRON
# Invest: coleta seg–sex 22:30 UTC (19:30 Brasília), como o GitHub Actions fazia
30 22 * * 1-5 $BASE/codigo/vm/coletar.sh >> $BASE/logs/coleta.log 2>&1
CRON
) | crontab -

IP=$(curl -s -4 --max-time 10 https://ifconfig.me || echo "IP-DA-VM")
echo
echo "Pronto. App (provisório, sem dados ainda): http://$IP/"
echo "Próximo passo: rodar a primeira coleta em modo teste:"
echo "   /srv/invest/codigo/vm/coletar.sh 100"
