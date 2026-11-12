# Invest na VM da Oracle (sem GitHub)

Faz na VM o que o GitHub Actions + Pages faziam.

- `bash vm/instalar.sh` instala tudo em /srv/invest (pode repetir).
- `/srv/invest/codigo/vm/coletar.sh 100` coleta em modo teste; sem número = completa; `so-app` = só republica o app.
- Agendado seg–sex 22:30 UTC (19:30 Brasília). Log: `tail -50 /srv/invest/logs/coleta.log`.
- `nohup /srv/invest/codigo/vm/cripto.sh > /srv/invest/logs/cripto.log 2>&1 &` roda a Hipótese K; resultado em http://IP/estudos/cripto/.
- App: http://IP-DA-VM/ (precisa da porta 80 liberada na Oracle: VCN > Security List > Ingress TCP 80).
- O site novo só entra no ar se passar no portão de qualidade; senão o anterior continua.
- Dados, diário e caches ficam em /srv/invest (nunca no código).

## Desde 12/11/2026 (fase 1 da remodelação)

- `vm/coletar.sh` faz tudo em sequência: carteira (raiz do site) → mercado dos mais negociados (`/antigo/`) → `data/agente.json`.
- Lista dos EUA em `/srv/invest/cache/universo-eua.txt` (500 papéis; `UNIVERSO_N` no config.env muda o número).
- `coletar.sh so-carteira` só atualiza a carteira; `so-app` só republica; `coletar.sh 50` testa o mercado com 50 papéis.
- Se o mercado falhar, a carteira publica do mesmo jeito e `/antigo/` fica com os dados anteriores.
- Cópia do agente.json para o Drive: definir `RCLONE_DESTINO=drive:Invest` no config.env depois de configurar o rclone.
