# Auditoria adversarial da hipótese O3

Escrita em 05/11/2026, **antes de ver o resultado do backtest da O3** (`hipotese-vencimento.md`), com os testes da
O1 e da O2 adaptados à nova execução. O objetivo é tentar derrubar o resultado.

Script: `opcoes/auditoria_o1.py --hipotese o3`. Período: fora da amostra (01/2023 a 10/2026). Versões: crédito e
débito.

## Testes

1. **Reprodução:** a mesma simulação duas vezes tem que dar o mesmo número.
2. **Execução atrasada:** ordem enviada 2 e 3 pregões depois do sinal (com o limite calculado no fechamento da
   véspera do envio).
3. **Custo × 4.**
4. **Placebo:** 100 simulações com entradas em dias sorteados, na mesma frequência, sem IV Rank. Crédito: a
   estrutura segue a mesma escolha da versão simples (ADX e MME200), como no placebo da O1. Débito: direção pela
   MME200, sem ADX, como no placebo da O2.
5. **Resultado por ano** e **pior mês.**
6. **Conferência à mão:** operações sorteadas, com data, preço à vista e P&L.
7. **Execução estrita:** a perna só conta como executada se o negócio foi **estritamente melhor** que o limite
   (máxima > limite na vendida, mínima < limite na comprada). Mede quanto o resultado depende de supor que a ordem
   seria atendida no preço exato, sem fila.
8. **Taxa de execução e risco de perna:** quantas ordens foram executadas por inteiro, e em quantas só parte das
   pernas teria saído (o caso em que, na vida real, fica-se com uma perna solta). Informativo.
9. **Limite otimista:** toda ordem executada no meio, sem exigir negócio no dia. Informativo.

## Critério (para cada versão aprovada no backtest)

O resultado **resiste à auditoria** se todos valerem:

- reproduz o mesmo número;
- com a ordem enviada 2 pregões depois, continua acima do CDI e com P&L/risco positivo;
- com custo × 4, o P&L/risco continua positivo;
- com a execução estrita, o P&L/risco continua positivo;
- no placebo, o original fica no percentil 95 ou acima (P&L/risco);
- pelo menos 3 dos 4 anos fora da amostra (2023 a 2026) com P&L positivo;
- em no máximo 10% das ordens só parte das pernas foi executada.

Para uma versão reprovada no backtest, a auditoria serve para confirmar que a reprovação é real (testes 1, 5 e 6).

## Resultado

(preenchido depois da execução)
