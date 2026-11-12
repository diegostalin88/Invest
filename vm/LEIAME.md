# Invest na VM da Oracle (sem GitHub)

Faz na VM o que o GitHub Actions + Pages faziam.

- `bash vm/instalar.sh` instala tudo em /srv/invest (pode repetir).
- `/srv/invest/codigo/vm/coletar.sh 100` coleta em modo teste; sem número = completa; `so-app` = só republica o app.
- Agendado seg–sex 22:30 UTC (19:30 Brasília). Log: `tail -50 /srv/invest/logs/coleta.log`.
- `nohup /srv/invest/codigo/vm/cripto.sh > /srv/invest/logs/cripto.log 2>&1 &` roda a Hipótese K; resultado em http://IP/estudos/cripto/.
- App: http://IP-DA-VM/ (precisa da porta 80 liberada na Oracle: VCN > Security List > Ingress TCP 80).
- O site novo só entra no ar se passar no portão de qualidade; senão o anterior continua.
- Dados, diário e caches ficam em /srv/invest (nunca no código).
