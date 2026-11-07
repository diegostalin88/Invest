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
