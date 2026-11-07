# Hipótese O5: venda de put fora do dinheiro com o caixa no CDI ("wheel"), B3

Registrado em **06/11/2026, antes de rodar qualquer número**. Proposta trazida pelo Diego a partir de uma análise de
outra IA ("Brazilian Wheel"). O Diego autorizou testar a venda de put a seco, que fica fora da regra de "só risco
definido" do estudo: aqui a put é **coberta por caixa** (o valor do exercício fica todo reservado), mas, se exercida,
a carteira fica com a ação e corre o risco dela. As regras, os critérios e a auditoria abaixo não mudam depois de ver
o resultado. Estudo só de leitura.

## Regras

- **Papéis:** PETR4, VALE3, ITUB4 e BBAS3, cada um com 1/4 do capital (R$ 100 mil no total).
- **Caixa:** todo o dinheiro rende CDI, inclusive o que está reservado como garantia da put (a B3 aceita Tesouro
  Selic como margem).
- **Venda da put:** quando o papel não tem opção vendida nem ação em carteira, escolhe no fechamento a put com
  vencimento entre 25 e 50 dias corridos (o mais perto de 35), strike entre **8% e 12% abaixo** do preço e, nessa
  faixa, delta mais perto de **0,14**. Vende no pregão seguinte pela **melhor oferta de compra**. Quantidade: o
  máximo em lotes de 100 que o caixa do papel cobre pelo strike.
- **Vencimento:** se o papel fecha abaixo do strike, a put é exercida e a carteira compra as ações pelo strike. Se
  não, o prêmio fica.
- **Com ações em carteira:** vende call coberta com vencimento entre 25 e 50 dias e o menor strike que seja pelo
  menos o maior entre o preço de custo e 5% acima do preço do dia, pela melhor oferta de compra no pregão seguinte.
  Se exercida, vende as ações pelo strike e volta para a put.
- **Proventos:** a B3 reduz o strike das opções em aberto pelo valor do provento na data ex. O simulador deduz o
  dividendo dessa mudança (mesmo valor em todas as séries) e o credita no caixa enquanto houver ações; desdobramento
  é deduzido da mesma forma (mesma razão em todas as séries).
- **Custo:** R$ 0,005 por opção na venda e no exercício. Corretagem das ações e imposto ficam fora.
- **Sem filtro de fundamentos** nesta versão: o filtro do app (P/L, P/VP, ROE, dívida) precisaria de balanços da época
  (dados da CVM). Os quatro papéis são grandes e lucrativos na maior parte do período.

Dentro da amostra 2019 a 2022; **fora da amostra 01/2023 a 10/2026, de onde sai o veredito.**

## Critério de aprovação (fora da amostra, todos)

1. Retorno total acima do CDI acumulado.
2. Queda máxima da carteira ≤ 20%.
3. Pelo menos 30 puts vendidas.
4. Pelo menos 3 dos 4 anos (2023 a 2026) com retorno acima do CDI do ano.

## Informativo e auditoria (mesma execução)

- **Comprar e manter** os quatro papéis com os proventos deduzidos (referência).
- **Ordem limite no meio** das ofertas (executa se a máxima do dia alcançar o limite).
- **Venda 2 pregões depois** da escolha.
- **Custo × 4.**
- **Put mais perto** (5% a 8% abaixo) e **mais longe** (12% a 16% abaixo).
- **Placebo:** 20 sorteios em que a venda só acontece em 10% dos pregões livres, sorteados.
- **Resultado por ano**, **reprodução** e **operações sorteadas** para conferência à mão.

## Resultado

**Veredito: REPROVADA.** Execução de 06/11/2026
([run 42144083510](https://github.com/diegostalin88/Invest/actions/runs/42144083510)), com o CDI real.

Fora da amostra (01/2023 a 10/2026), R$ 100 mil:

| Variante | Retorno | CDI | Comprar e manter | Queda máx. | Puts | Exercidas | Calls | Prêmio da put ÷ strike (mediana) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Base | 58,8% | 59,8% | 82,4% | 45,9% | 105 | 13 | 60 | 0,2% |
| Ordem limite no meio (informativo) | 68,5% | 59,8% | 82,4% | 47,1% | 72 | 13 | 59 | 0,6% |
| Auditoria: venda 2 pregões depois | 54,5% | 59,8% | 82,4% | 45,9% | 101 | 12 | 58 | 0,2% |
| Auditoria: custo × 4 | 56,0% | 59,8% | 82,4% | 45,9% | 105 | 13 | 60 | 0,2% |
| Put 5% a 8% abaixo (informativo) | 60,8% | 59,8% | 82,4% | 46,1% | 97 | 16 | 67 | 0,4% |
| Put 12% a 16% abaixo (informativo) | 47,2% | 59,8% | 82,4% | 10,0% | 131 | 7 | 13 | 0,1% |

Por ano (base): 2023 20,9% contra CDI 13,0%; 2024 6,8% contra 10,8%; 2025 15,9% contra 14,2%; 2026 6,1% contra
11,8%. Dois de quatro anos acima do CDI.

Critérios: falha em ficar acima do CDI, na queda máxima ≤ 20% (45,9%) e nos 3 de 4 anos acima do CDI; passa no
número de puts (105).

**Leitura:**

- O prêmio de uma put 8% a 12% fora do dinheiro, vendida pela oferta de compra, é muito pequeno: mediana de 0,2% do
  strike por mês. Ele não compensa o que se perde quando a put é exercida.
- Uma vez exercida, a carteira fica com a ação, e a queda máxima passa a ser a da ação (46%), não a de uma renda.
  A estratégia vira "ações compradas com atraso", e perde para simplesmente comprar e manter os quatro papéis
  (82,4%), que tiveram um bom período.
- Só a variante mais longe (12% a 16%) controla a queda (10%), mas aí o prêmio é quase nulo e o retorno (47%) fica
  bem abaixo do CDI.
- O placebo (vender em 10% dos pregões livres, sorteados) dá retorno mediano de 56,2%: o resultado da base é
  praticamente o mesmo do acaso. Reprodução: sim.
- Dentro da amostra (2019 a 2022) a base rendeu 47,2% contra CDI 27,4%, com queda de 36,6%: foi um período de CDI
  baixo, em que qualquer exposição a ações batia o CDI. Fora da amostra, com CDI alto, não bate.

Conferência à mão (operações sorteadas): ITUB4 put strike 24,94 vendida em 18/09/2023 (à vista 27,51) por 0,04,
virou pó; BBAS3 call strike 25,75 vendida em 20/04/2026 (24,28) por 0,33, virou pó; PETR4 put strike 21,93 vendida
em 22/05/2023 (25,62) por 0,17, virou pó.
