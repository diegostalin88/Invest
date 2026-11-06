# Hipótese O6: trava de alta com put filtrada pelo prêmio de volatilidade (VRP), ordem estruturada, B3

Registrado em **06/11/2026, antes de rodar qualquer número**. Proposta trazida pelo Diego a partir de uma análise de
outra IA. As regras, os critérios e a auditoria abaixo não mudam depois de ver o resultado. Estudo só de leitura.

## O que muda em relação à O1 e à O3

- **Filtro:** no lugar do IV Rank, o **VRP = IV no dinheiro de 30 dias − volatilidade realizada de 21 pregões**
  (anualizada). Só entra com **VRP ≥ +4 pontos percentuais**.
- **Execução por ordem estruturada a preço líquido:** no fechamento do sinal, o crédito pedido é o meio das ofertas
  das duas pernas. No pregão seguinte, a ordem executa as duas pernas juntas se, naquele dia, a put vendida negociou
  a um preço e a comprada a outro cuja diferença alcança o crédito pedido (máxima da vendida − mínima da comprada ≥
  crédito). Sem negócio em alguma perna, não executa. Não há perna solta. Não existe histórico público das ordens
  estruturadas da B3; esta é a aproximação possível com dados diários, e é a favor da estratégia (supõe que a ordem
  pegaria o melhor preço do dia nas duas pernas).
- **Sem stop e sem alvo:** liquida no vencimento pelo valor intrínseco.

## Regras

- **Estrutura:** trava de alta com put. Vendida com delta mais perto de 0,25, comprada com largura perto de 5% do
  preço. Vencimento entre 42 e 63 dias corridos (cerca de 30 a 45 pregões), o mais perto de 52.
- **Versões:** **BOVA11** (proposta original) e **6 papéis** (PETR4, VALE3, BOVA11, ITUB4, BBAS3, PRIO3).
- Uma posição por papel. Perda máxima de 1% do capital por operação; o resto rende CDI. Custo de R$ 0,005 por opção
  por perna na entrada e no vencimento.
- O strike das pernas acompanha o ajuste que a B3 faz nos proventos.

Dentro da amostra 2019 a 2022; **fora da amostra 01/2023 a 10/2026, de onde sai o veredito.**

## Critério de aprovação (fora da amostra, todos, para cada versão)

1. Retorno acima do CDI. 2. Fator de lucro ≥ 1,2. 3. Pelo menos 20 operações no BOVA11 (um papel só, com
vencimentos de ~2 meses, não chega a 50) e 50 nos 6 papéis. 4. Queda máxima ≤ 15%. 5. Sem o melhor papel, acima do
CDI (só na versão de 6 papéis). 6. Com o filtro de VRP, resultado por operação melhor que sem filtro.

Comparações informativas: VRP ≥ 5; IV Rank ≥ 50 no lugar do VRP; entrada pelas ofertas (sem ordem estruturada).

## Auditoria adversarial (`auditoria_o1.py --hipotese o6`)

Reprodução; ordem 2 e 3 pregões depois; custo × 4; placebo de 100 sorteios (dias sorteados, sem VRP); resultado por
ano e pior mês; operações sorteadas; limite otimista (toda ordem executa no meio). O resultado resiste se, com a
ordem 2 pregões depois e com custo × 4, o P&L por risco continuar positivo, o original ficar no percentil 95 ou acima
do placebo, e pelo menos 3 dos 4 anos tiverem P&L positivo.

## Resultado

(preenchido depois da execução)
