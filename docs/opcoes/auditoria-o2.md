# Auditoria adversarial da hipótese O2

Pedida pelo Diego em 05/11/2026 para cada backtest. Escrita **antes de ver o resultado do backtest da O2**, com os mesmos testes da O1 (incluindo os que entraram na O1 depois do primeiro resultado). O objetivo é tentar
derrubar o resultado: achar erro de código, olhar para o futuro sem querer, sorte ou custo subestimado.

Script: `opcoes/auditoria_o1.py --hipotese o2` (mesmo motor de `opcoes/debito.py`, mesmos dados). Período: fora da amostra
(01/2023 a 10/2026).

## Testes

1. **Reprodução:** rodar a mesma simulação duas vezes tem que dar exatamente o mesmo número.
2. **Execução atrasada:** executar 2 e 3 pregões depois do sinal, em vez de 1. Se a vantagem some com um ou dois
   dias de atraso, ela depende de algo frágil (ou de informação que não estaria disponível a tempo).
3. **Custo × 4:** custo por opção quatro vezes maior, além da diferença entre oferta de compra e de venda.
4. **Placebo:** 100 simulações com entradas em dias **sorteados**, na mesma frequência da versão original, sem IV
   Rank e sem gatilho técnico (a direção segue a MME200: acima, trava de alta; abaixo, trava de baixa). Se o original não ficar
   acima de quase todos os sorteios, o filtro não está escolhendo dias melhores que o acaso.
5. **Resultado por ano** e **pior mês**, para ver se tudo vem de um único período.
6. **Conferência à mão:** 5 operações sorteadas, com data, preço à vista, motivo de saída e P&L, para conferir
   contra as cotações da B3.
7. **Saída decidida pelo preço médio.** O stop e o alvo passam a olhar o meio entre as ofertas, e a execução continua na oferta. Mede
   quanto do resultado depende de ofertas largas ou desatualizadas no fechamento. Informativo: não entra no critério.
8. **Limite otimista: tudo no meio das ofertas.** Entrada, saída e marcação pelo
   preço médio entre compra e venda, como se a diferença entre as ofertas não custasse nada. Se nem assim a
   estratégia ganha, a reprovação não é culpa do custo de execução. Informativo.
9. **Peso da diferença entre ofertas:** quanto custa montar e desmontar na hora (ida e volta pelas ofertas),
   dividido pelo débito pago. Informativo.

## Critério (para cada versão aprovada no backtest)

O resultado **resiste à auditoria** se todos valerem:

- reproduz o mesmo número;
- com execução 2 pregões depois, continua acima do CDI e com P&L/risco positivo;
- com custo × 4, o P&L/risco continua positivo;
- no placebo, o original fica no percentil 95 ou acima (P&L/risco);
- pelo menos 3 dos 4 anos fora da amostra (2023 a 2026) com P&L positivo.

Para uma versão **reprovada** no backtest, a auditoria serve para confirmar que a reprovação é real e não um
erro do simulador (testes 1, 5 e 6).

## Resultado

Execução de 05/11/2026 ([run 42122050500](https://github.com/diegostalin88/Invest/actions/runs/42122050500)).
As duas versões foram reprovadas no backtest, então a auditoria serve para confirmar que a reprovação é real.
**Confirma.**

| Teste | Simples | Técnica |
| --- | --- | --- |
| 1. Reproduz o mesmo número | sim | sim |
| Original: P&L ÷ risco / retorno (CDI 59,7%) | −70,0% / −84,4% | −65,0% / −8,4% |
| 2. Execução 2 pregões depois | −70,0% / −78,6% | −60,3% / +0,9% |
| 2. Execução 3 pregões depois | −68,3% / −72,6% | −62,0% / −0,9% |
| 3. Custo × 4 | −71,5% / −86,8% | −66,6% / −9,3% |
| 4. Placebo: P&L ÷ risco mediano; percentil do original | −67,2%; 9 | −65,4%; 51 |
| 5. Anos com P&L positivo (2023 a 2026) | 0 de 4 | 0 de 4 |
| 5. Pior mês | 05/2023, −10,5% | 10/2025, −4,4% |
| 7. Saída decidida pelo preço médio | −61,6%, acerto 13% | −53,9%, acerto 13% |
| 8. Limite otimista, tudo no meio | −0,8%, fator de lucro 0,98, acerto 32% | −11,1%, fator de lucro 0,74, acerto 31% |
| 9. Ida e volta pelas ofertas ÷ débito (mediana; p25 a p75) | 0,53 (0,32 a 0,89) | 0,40 (0,20 a 0,71) |

**Leitura:**

- O simulador é determinístico e o resultado não depende do dia de execução: atrasar 1 ou 2 pregões muda pouco.
- Todos os anos perdem, nas duas versões. Não é um período ruim isolado.
- O filtro (IV Rank baixo com tendência ou rompimento) não escolhe dias melhores que o acaso: a simples fica abaixo
  de 91% dos sorteios e a técnica fica no meio deles.
- A perda vem da diferença entre as ofertas. Na entrada a trava já perde de 20% a 89% do débito se for desmontada,
  e o stop em 50% do débito é atingido em poucos pregões. Sem esse custo (limite otimista) a estratégia fica no zero
  a zero, o que mostra que também não existe vantagem de direção para o custo comer.

Conferência à mão (operações sorteadas, para comparar com as cotações da B3):

- ITUB4 trava de alta com call: entrada 01/06/2023 (à vista 26,70), saída 07/06/2023 pelo stop, P&L −R$ 609, risco R$ 609.
- PRIO3 trava de alta com call: entrada 11/06/2025 (à vista 43,31), saída 12/06/2025 pelo stop, P&L −R$ 135, risco R$ 138.
- VALE3 trava de baixa com put: entrada 18/08/2026 (à vista 71,55), saída 19/08/2026 pelo stop, P&L −R$ 82, risco R$ 120.
- VALE3 trava de baixa com put: entrada 31/03/2023 (à vista 80,29), saída 03/04/2023 pelo stop, P&L −R$ 622, risco R$ 622.
- PETR4 trava de alta com call: entrada 19/10/2023 (à vista 38,34), saída 23/10/2023 pelo stop, P&L −R$ 310, risco R$ 415.
- (técnica) PETR4 trava de baixa com put: entrada 13/10/2025 (à vista 30,23), saída 23/10/2025 pelo stop, P&L −R$ 912, risco R$ 912.
- (técnica) ITUB4 trava de alta com call: entrada 14/12/2023 (à vista 32,87), saída 15/12/2023 pelo stop, P&L −R$ 610, risco R$ 960.

Perdas de 100% do débito em poucos dias (ITUB4 em 06/2023, VALE3 em 03/2023) acontecem quando, na saída, a oferta de
compra da trava some ou fica muito abaixo do valor justo; são as operações que vale conferir primeiro contra a B3.
