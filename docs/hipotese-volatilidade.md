# Hipótese: controle da exposição pela volatilidade

Registrado em **07/11/2026, antes de escrever o código e antes de ver qualquer número**. As regras e os critérios abaixo não mudam depois do resultado. A versão completa, com o contexto, está no documento "Invest: o que aprendemos e a metodologia nova" (Claude Docs).

## Regra (sem otimização)
1. Volatilidade atual: desvio-padrão dos retornos diários dos últimos 21 pregões, anualizado.
2. Volatilidade-alvo: mediana da volatilidade de 21 pregões desde o início da série até a data, usando só dados passados.
3. Exposição = alvo ÷ atual, limitada a 0–100% (sem alavancagem). O resto fica no caixa.
4. A exposição é recalculada toda sexta no fechamento e aplicada a partir do pregão seguinte. Custo de 0,1% sobre o valor trocado.
5. O caixa rende o T-bill de 3 meses (^IRX) nos EUA e o CDI (BCB, série SGS 12) no Brasil. Se o CDI não baixar, o caixa no Brasil rende zero, e isso fica anotado no resultado.

## Onde
- SPY, desde 1993.
- Ibovespa (^BVSP, índice de preço, sem dividendos), desde 1995.
- Só como informação, porque tem viés de sobrevivência: uma cesta dos 34 papéis voláteis usados em 05/11, com pesos iguais.

## Comparação
(a) Comprar e segurar. (b) Exposição fixa igual à média da regra no período.

## Critérios de aprovação (EUA e Brasil, os dois)
1. O Sharpe é maior que o de comprar e segurar no período inteiro **e** em cada metade.
2. A queda máxima é pelo menos 20% menor que a da exposição fixa de mesma média.
3. Com custo dobrado (0,2%), o critério 1 continua valendo no período inteiro.

## Resultado (07/11/2026, run 42330953904): **REPROVADA**
| Período inteiro | Sharpe segurar | Sharpe regra | Queda regra | Queda exposição fixa de mesma média |
|---|---|---|---|---|
| SPY 1994–2026 | 0,51 | 0,52 | −44% | −48% (83%) |
| Ibovespa 1996–2026 (caixa CDI) | 0,10 | 0,05 | −57% | −61% (93%) |

Critério 1: falhou nos dois (EUA perde na 1ª metade, 0,22 contra 0,26). Critério 2: falhou nos dois. Critério 3: passou nos EUA e falhou no Brasil. A regra só reduz o risco na mesma proporção que uma exposição fixa menor.
