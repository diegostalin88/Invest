# Protocolo do placar do agente analista (registro prévio, 12/11/2026)

O agente analista (skill `analista-invest`) dá um parecer por papel: **a favor, neutro ou contra a tese**, com grau de
confiança. Isso é um julgamento que ninguém testou. Pelos princípios dos livros-base (só regra validada fora da amostra
vira sinal), o parecer é **contexto** até este placar mostrar o contrário. Este arquivo foi escrito antes do primeiro parecer.

## O que é registrado em cada parecer

Uma linha por papel citado, no registro "Agente" (planilha no Google Drive do Diego, aba `pareceres`):

| campo | exemplo |
|---|---|
| data do parecer | 2026-11-13 |
| papel e mercado | PETR4 · br |
| tese | a favor / neutro / contra |
| confiança | baixa / média / alta |
| preço de referência | último fechamento do `agente.json` |
| índice de referência | BOVA11 (br) ou SPY (us), fechamento do mesmo dia |
| o que mudaria a opinião | texto curto |
| data do agente.json usado | 2026-11-12 |

Pareceres sobre a carteira inteira ou o mercado (sem papel) são guardados, mas não entram no placar.

## Como é medido

- Em **20, 60 e 120 pregões** após o parecer: retorno do papel menos o retorno do índice de referência no mesmo período
  (excesso de retorno).
- "Acerto": tese **a favor** com excesso > 0, ou tese **contra** com excesso < 0. Neutro não conta para o acerto.

## Critérios (pré-registrados)

O parecer só pode deixar de ter o selo **"não validado"** se, com **pelo menos 60 pareceres a favor ou contra já com 120
pregões**:

1. a diferença de excesso médio entre "a favor" e "contra" for positiva nas janelas de 60 e de 120 pregões;
2. o acerto ficar acima do percentil 95 de teses sorteadas ao acaso (mesmos papéis e datas, teses embaralhadas 10 mil vezes);
3. o resultado se mantiver nas duas metades do período (primeiros e últimos 30 pareceres).

Se falhar, o agente continua só descrevendo: sem tese por papel, apenas cenário, riscos e o que mudaria a leitura.
Não vale trocar o prompt e "recontar" os pareceres antigos: mudança de método recomeça o placar.
