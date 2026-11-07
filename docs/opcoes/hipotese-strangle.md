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

**Veredito: as duas versões REPROVADAS.** Execução de 06/11/2026
([run 42144895971](https://github.com/diegostalin88/Invest/actions/runs/42144895971)), com o CDI real.

Fora da amostra (01/2023 a 10/2026), R$ 100 mil. "Opções" é (recebido no vencimento − pago) ÷ pago, somando todos os
strangles:

| Versão / variante | Strangles | Retorno | CDI | Opções | Acerto | Melhor múltiplo | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **BOVA11** | 20 | 59,7% | 59,8% | +2,4% | 35% | 5,3× | 0,9% |
| BOVA11, Bollinger estreito | 26 | 58,4% | 59,8% | −10,5% | 27% | 5,3× | 1,1% |
| BOVA11, 100% dos juros | 20 | 58,6% | 59,8% | −1,0% | 35% | 5,3× | 2,1% |
| BOVA11, compra 2 pregões depois | 20 | 58,9% | 59,8% | −4,6% | 35% | 5,4× | 0,7% |
| BOVA11, custo × 4 | 20 | 59,2% | 59,8% | −1,2% | 35% | 5,1× | 0,9% |
| **6 papéis** | 40 | 60,9% | 59,8% | +9,1% | 35% | 6,3× | 1,9% |
| 6 papéis, Bollinger estreito | 44 | 68,5% | 59,8% | +32,4% | 39% | 7,6× | 2,0% |
| 6 papéis, 100% dos juros | 40 | 62,9% | 59,8% | +10,4% | 35% | 6,3× | 4,8% |
| 6 papéis, compra 2 pregões depois | 38 | 62,7% | 59,8% | +17,2% | 32% | 6,9× | 2,0% |
| 6 papéis, custo × 4 | 40 | 60,1% | 59,8% | +6,0% | 35% | 6,1× | 1,9% |

Critérios:

- **BOVA11:** falha em ficar acima do CDI (59,7% contra 59,8%) e no placebo (percentil 67; mediana do placebo
  −15,5%). Passa no resultado das opções (+2,4%) e no número de strangles (20).
- **6 papéis:** passa em ficar acima do CDI (60,9%), no resultado das opções (+9,1%) e no número (40), mas **falha
  no placebo**: percentil 85 (mediana do placebo −16,5%), abaixo do 95 exigido.

Por ano (opções, fora da amostra): BOVA11 2023 +7%, 2024 −34%, 2025 +64%, 2026 −100% (um strangle só); 6 papéis
2023 +15%, 2024 −47%, 2025 −26%, 2026 +93%. Dentro da amostra (2019 a 2022): BOVA11 +68% e 6 papéis +1%.
Reprodução: sim nas duas.

**Leitura:**

- É a primeira hipótese em que o resultado das opções fica positivo e a carteira empata ou supera levemente o CDI.
  Isso é esperado da construção: o capital nunca sai do CDI, e o que se arrisca por mês é metade dos juros (cerca de
  0,5% do capital). O pior caso é render metade do CDI no mês, e a queda máxima não passa de 2%.
- Mas a vantagem é pequena (6 papéis: +1,1 ponto percentual em quase 4 anos) e depende de poucos acertos grandes
  (melhores strangles pagaram 5 a 7 vezes o custo). Com 35% de acerto, alguns meses de sorte mudam tudo, e os anos
  alternam entre +93% e −47%.
- O filtro de IV Rank < 20 escolhe dias melhores que o acaso, mas não o bastante para afastar a sorte (percentil 85,
  não 95). O Bollinger estreito foi melhor nos 6 papéis (+32%) e pior no BOVA11 (−10,5%): sem consistência.
- Na prática, é uma estratégia de risco muito baixo e retorno igual ao CDI, com um bilhete de loteria barato por mês.
  Não perde dinheiro de verdade, mas também não mostrou vantagem que se distinga do acaso.

Conferência à mão (strangles sorteados):

- BOVA11 BOVAI70 e BOVAU108, compra em 21/08/2023 (à vista 110,79) por 1,24, vencimento 15/09/2023 (114,92), recebe
  0, 400 de cada.
- BOVA11 BOVAK23 e BOVAW29, compra em 13/10/2025 (138,75) por 1,59, vencimento 21/11/2025 (151,95), recebe 5,94
  (3,7×), 500 de cada.
- PETR4 PETRG361 e PETRS254, compra em 02/06/2023 (27,18) por 0,63, vencimento 21/07/2023 (29,68), recebe 1,38,
  900 de cada.
- VALE3 VALEJ810 e VALEV656, compra em 04/09/2023 (69,40) por 2,17, vencimento 20/10/2023 (62,68), recebe 1,35,
  200 de cada.
