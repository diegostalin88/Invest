# Hipótese O7: strangle comprado com metade dos juros do CDI ("capital protegido"), B3

Registrado em **06/11/2026, antes de rodar qualquer número**, a pedido do Diego (proposta de outra IA: deixar o
capital no CDI e usar parte dos juros para comprar opções quando a volatilidade está baixa). As regras, os
critérios e a auditoria abaixo não mudam depois de ver o resultado. Estudo só de leitura.

## Pergunta

Comprar strangles (call e put fora do dinheiro) só quando o IV Rank está baixo dá retorno médio positivo? Com o
capital todo no CDI, a carteira só vence o CDI se as opções compradas renderem mais do que custaram.

## Regras

- **Capital:** R$ 100 mil, todo rendendo CDI.
- **Orçamento:** no primeiro pregão de cada mês, o orçamento do mês é **metade do CDI que a carteira rendeu no mês
  anterior**. O que não for usado no mês volta a ser só caixa (não acumula).
- **Sinal:** no fechamento, papel sem strangle aberto, com **IV Rank < 20** e orçamento do mês ainda não usado.
- **Montagem:** no pregão seguinte, compra pela **melhor oferta de venda** uma call e uma put do mesmo vencimento
  (25 a 50 dias corridos, o mais perto de 35), cada uma com |delta| mais perto de **0,20**. Quantidade: o máximo em
  lotes de 100 que o orçamento paga. Se não couber um lote, não compra. Um strangle por mês na carteira toda.
- **Saída:** nenhuma antes do vencimento; no vencimento, recebe o valor intrínseco. Sem stop.
- **Custo:** R$ 0,005 por opção por perna na compra e no exercício.
- **Versões:** **BOVA11** e **6 papéis** (PETR4, VALE3, BOVA11, ITUB4, BBAS3, PRIO3; no mês, o primeiro papel com
  sinal leva o orçamento).

Dentro da amostra 2019 a 2022; **fora da amostra 01/2023 a 10/2026, de onde sai o veredito.**

## Critério de aprovação (fora da amostra, todos, para cada versão)

1. Retorno total acima do CDI acumulado.
2. Resultado das opções positivo: soma do valor recebido no vencimento maior que a soma pago.
3. Pelo menos 20 strangles.
4. No placebo (100 sorteios: mesmo número de meses com compra, mas dias sorteados, sem IV Rank), o resultado das
   opções do original fica no percentil 95 ou acima.

## Informativo e auditoria (mesma execução)

- Bollinger estreito (largura de 20 pregões abaixo da mediana de 252) no lugar do IV Rank.
- Orçamento de 100% dos juros do mês.
- Compra 2 pregões depois do sinal; custo × 4.
- Resultado por ano; melhor múltiplo (recebido ÷ pago); reprodução; operações sorteadas para conferência.

## Resultado

(preenchido depois da execução)
