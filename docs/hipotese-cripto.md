# Hipótese K: estratégias em criptomoedas (registro prévio)

Registrado em 07/11/2026, **antes de ver qualquer resultado**. Regras e parâmetros
abaixo ficam congelados; nada de trocar média, janela ou número de moedas depois
de ver o resultado (seria ajuste ao passado, como nas hipóteses A, B, H e Q-BR).

## Pergunta

Ainda existe estratégia em cripto que valha a pena, depois do custo, contra só
segurar e contra o CDI? E vale ter uma parcela pequena (5%) de cripto na holding?

## Dados

- Binance spot, candles diários de **todos os pares contra USDT**, inclusive os
  **já retirados da corretora** (o arquivo público data.binance.vision guarda o
  histórico das moedas delistadas). Isso reduz o viés de sobrevivência.
- Ficam de fora: stablecoins (USDC, BUSD, TUSD, FDUSD, DAI etc.) e tokens
  alavancados (UP/DOWN/BULL/BEAR).
- Universo de cada semana = as 30 moedas com maior volume financeiro médio
  nos 30 dias anteriores, com pelo menos 90 dias de histórico (só informação
  disponível naquela data).
- Conversão para reais pelo dólar PTAX (BCB série 1). CDI diário (BCB série 12).
  BOVA11 e IVVB11 pelo Yahoo (fechamento ajustado).
- Período: 01/01/2018 até o último mês fechado. Metades: 2018–2021 e 2022–fim.
- Moeda que some da base enquanto está na carteira: sai pelo último preço
  (premissa otimista; o relatório conta quantas vezes aconteceu).

## Execução e custo

- Sinal no fechamento do dia, operação no fechamento seguinte (sem olhar o futuro).
- Custo por lado: 0,15% (taxa 0,10% + 0,05% de deslizamento). Teste de
  robustez com **custo dobrado** (0,30%).
- Dinheiro fora da cripto rende CDI.
- IR não é modelado (vendas acima de R$ 35 mil no mês pagam 15% sobre o ganho;
  estratégias que giram muito perdem a isenção). Isso só piora as ativas.

## Estratégias (parâmetros fixos, clássicos da literatura de tendência)

| Código | Regra | Referência |
|---|---|---|
| R1 | Só segurar BTC | referência principal |
| R2 | Só segurar ETH | referência |
| R3 | Cesta igual das 30 maiores, rebalanceada toda semana | referência do "mercado cripto" |
| T1 | BTC quando fecha acima da média de 200 dias; senão CDI | Faber / Kaufman |
| T2 | ETH acima da média de 200 dias; senão CDI | idem |
| T3 | BTC com retorno de 90 dias > 0; senão CDI | momento de série temporal (Moskowitz) |
| M1 | Toda semana, das 30 maiores compra as 5 de maior retorno em 12 semanas (só as com retorno > 0), peso igual; o resto em CDI | momento relativo |
| M2 | M1 só quando o BTC está acima da média de 200 dias; senão tudo em CDI | momento + filtro de regime |
| P0 | Holding sem cripto: 1/3 BOVA11 + 1/3 IVVB11 + 1/3 CDI, rebalanceada a cada trimestre | carteira base |
| P1 | 95% P0 + 5% BTC, rebalanceada a cada trimestre | parcela pequena |
| P2 | 95% P0 + 5% BTC com a regra T1 (fora da média → CDI) | parcela com filtro |

## Critérios de aprovação (todos precisam passar)

Para T1–T3 e M1–M2, comparando com a referência do próprio ativo
(T1/T3 × R1, T2 × R2, M1/M2 × R3 **e** × R1):

1. Índice de Sharpe (sobre o CDI, em reais) maior que o da referência no
   período inteiro **e** em cada metade.
2. Queda máxima não pior que a da referência.
3. Com custo dobrado, Sharpe acima do percentil 95 do acaso
   (T: 1.000 sorteios deslocando a mesma sequência de entradas e saídas no
   tempo, mantendo tempo exposto e número de trocas; M: 500 sorteios
   escolhendo moedas ao acaso do mesmo universo, mesma quantidade por semana).
4. Retorno final em reais acima do CDI acumulado.

Para P1 e P2 (contra P0):

1. Sharpe maior que o de P0 no inteiro e nas duas metades.
2. Queda máxima no máximo 2 pontos percentuais pior que a de P0.

## O que fazer com o resultado

- Reprovou: fica registrado, não se reabre com outros parâmetros.
- Aprovou: entra só como **teste para frente** (sem dinheiro real), mesmo
  protocolo das regras congeladas (≥100 sinais fechados ou 2 anos).
- Nenhum teste usa a conta da Binance do Diego; só dados públicos.
