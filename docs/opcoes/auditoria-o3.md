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

Execução de 05/11/2026 ([run 42131554510](https://github.com/diegostalin88/Invest/actions/runs/42131554510)).
As duas versões foram reprovadas no backtest; a auditoria **confirma** que a reprovação é real.

| Teste | Crédito | Débito |
| --- | --- | --- |
| 1. Reproduz o mesmo número | sim | sim |
| Original: P&L ÷ risco / retorno (CDI 59,8%) | −5,2% / 54,1% | −2,2% / 55,1% |
| 2. Ordem 2 pregões depois | −13,5% / 50,5% | −5,8% / 50,1% |
| 2. Ordem 3 pregões depois | −8,0% / 53,5% | +8,2% / 68,6% |
| 3. Custo × 4 | −8,9% / 51,0% | −7,6% / 46,2% |
| 4. Placebo: P&L ÷ risco mediano; percentil do original | −6,6%; 63 | −3,4%; 55 |
| 5. Anos com P&L positivo | 0 de 3 com operações (2024 a 2026) | 2 de 4 (2024 +12%, 2025 +5%; 2023 −3%, 2026 −23%) |
| 5. Pior mês | 05/2025, −0,8% | 01/2025, −3,1% |
| 7. Execução estrita | −3,2% / 55,7% | −5,0% / 50,4% |
| 8. Ordens executadas / só em parte / sem execução | 66 / 95 / 10 | 118 / 117 / 7 |
| 9. Limite otimista (sempre executa no meio) | −0,4%, fator de lucro 0,98 | +28,2%, fator de lucro 1,53 |
| Ida e volta pelas ofertas ÷ prêmio (mediana) | 0,99 | 0,54 |

**Leitura:**

- O simulador é determinístico e o filtro não escolhe dias melhores que o acaso (percentis 63 e 55 no placebo).
- **Risco de perna:** em mais da metade das ordens, só parte das pernas teria sido executada (95 de 171 no crédito,
  117 de 242 no débito), muito acima do limite de 10% do critério. Na vida real, cada uma dessas vezes deixaria uma
  perna solta (por exemplo, uma opção vendida sem a proteção), que é exatamente o risco que as travas querem evitar.
  O backtest simplesmente cancela essas ordens, o que é a favor da estratégia.
- O débito com toda ordem executada no meio (+28%) mostra que existe algum valor nas travas compradas quando o preço
  de entrada é o justo, mas esse preço não aparece na tela com frequência suficiente: exigindo negócio no dia, ele
  some. Não é um resultado operável com dados diários.
- O ano de 2026 pesa contra o débito (−23% por operação), e 2024 a favor; não há consistência entre anos.

Conferência à mão (operações sorteadas):

- Crédito: VALE3 iron condor, entrada 02/08/2024 (à vista 59,41), vencimento 20/09/2024, P&L +R$ 118, risco R$ 1.074.
- Crédito: BBAS3 trava de baixa com call, 22/09/2025 (21,51) a 17/10/2025, P&L +R$ 150, risco R$ 1.335.
- Crédito: PRIO3 trava de alta com put, 24/03/2026 (67,63) a 17/04/2026, P&L +R$ 267,50, risco R$ 1.227,50.
- Débito: PETR4 trava de alta com call, 19/06/2023 (30,42) a 21/07/2023, P&L −R$ 840, risco R$ 1.035.
- Débito: PETR4 trava de baixa com put, 06/03/2025 (34,26) a 17/04/2025, P&L +R$ 2.071, risco R$ 1.235.
- Débito: BOVA11 trava de alta com call, 12/03/2026 (175,85) a 17/04/2026, P&L +R$ 1.278, risco R$ 1.419.
- Débito: PETR4 trava de baixa com put, 12/01/2026 (30,36) a 20/02/2026, P&L −R$ 1.394, risco R$ 1.394.
