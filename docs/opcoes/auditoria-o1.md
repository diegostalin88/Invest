# Auditoria adversarial da hipótese O1

Pedida pelo Diego em 05/11/2026. Escrita **antes de ver o resultado do backtest da O1**. O objetivo é tentar
derrubar o resultado: achar erro de código, olhar para o futuro sem querer, sorte ou custo subestimado.

Script: `opcoes/auditoria_o1.py` (mesmo motor de `opcoes/travas.py`, mesmos dados). Período: fora da amostra
(01/2023 a 10/2026).

## Testes

1. **Reprodução:** rodar a mesma simulação duas vezes tem que dar exatamente o mesmo número.
2. **Execução atrasada:** executar 2 e 3 pregões depois do sinal, em vez de 1. Se a vantagem some com um ou dois
   dias de atraso, ela depende de algo frágil (ou de informação que não estaria disponível a tempo).
3. **Custo × 4:** custo por opção quatro vezes maior, além da diferença entre oferta de compra e de venda.
4. **Placebo:** 100 simulações com entradas em dias **sorteados**, na mesma frequência da versão original, sem IV
   Rank e sem gatilho técnico (a estrutura segue a versão simples: alta, baixa ou lateral). Se o original não ficar
   acima de quase todos os sorteios, o filtro não está escolhendo dias melhores que o acaso.
5. **Resultado por ano** e **pior mês**, para ver se tudo vem de um único período.
6. **Conferência à mão:** 5 operações sorteadas, com data, preço à vista, motivo de saída e P&L, para conferir
   contra as cotações da B3.

7. **Saída decidida pelo preço médio** (incluído depois da 1ª execução, que teve um erro de simulador; ver o
   registro da O1). O stop e o alvo passam a olhar o meio entre as ofertas, e a execução continua na oferta. Mede
   quanto do resultado depende de ofertas largas ou desatualizadas no fechamento. Informativo: não entra no critério.

8. **Limite otimista: tudo no meio das ofertas** (incluído depois da 2ª execução). Entrada, saída e marcação pelo
   preço médio entre compra e venda, como se a diferença entre as ofertas não custasse nada. Se nem assim a
   estratégia ganha, a reprovação não é culpa do custo de execução. Informativo.
9. **Peso da diferença entre ofertas:** quanto custa montar e desmontar na hora (ida e volta pelas ofertas),
   dividido pelo crédito recebido. Informativo.

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

Execução de 05/11/2026 ([run 42109978654](https://github.com/diegostalin88/Invest/actions/runs/42109978654)),
sobre a 2ª execução do backtest. As duas versões foram reprovadas no backtest, então a auditoria serve para
confirmar que a reprovação é real.

| Teste | Simples | Técnica |
| --- | --- | --- |
| Reproduz o mesmo número | sim | sim |
| P&L ÷ risco original | −22,4% | −20,7% |
| Execução 2 pregões depois | −21,1% | −19,5% |
| Execução 3 pregões depois | −20,2% | −21,9% |
| Custo × 4 | −22,9% | −21,4% |
| Saída decidida pelo preço médio | −24,1% | −24,7% |
| **Tudo no meio das ofertas (limite otimista)** | **+0,5%**, fator de lucro 1,04, acerto 61%, retorno 60,5% (CDI 59,7%) | **+0,3%**, fator de lucro 1,03, acerto 70%, retorno 59,9% |
| Ida e volta pelas ofertas ÷ crédito (mediana) | 1,88 | 1,87 |
| Placebo: percentil do original entre 100 sorteios | 0% | 2% |
| P&L ÷ risco por ano (2024, 2025, 2026) | −16%, −21%, −28% | −17%, −15%, −25% |

**Conclusões**

1. **Não é erro do simulador.** O resultado se reproduz, é parecido em todos os anos e não muda com 1 ou 2 dias
   de atraso. As operações sorteadas para conferência mostram o padrão: entra, e o stop dispara 1 a 4 pregões
   depois, perdendo de 10% a 35% do risco.
2. **A causa é o custo de atravessar as ofertas.** Na mediana, montar e desmontar a trava na hora custa 1,9 vez o
   crédito recebido. Com isso, o stop de 2× o crédito dispara com qualquer oscilação, e o alvo de 50% quase nunca
   chega.
3. **Mesmo sem esse custo, não há vantagem.** No limite otimista (tudo no meio das ofertas, custo de execução
   zero), as travas acertam 61% a 70%, mas o fator de lucro fica em 1,03 a 1,04 e o retorno total empata com o
   CDI. O prêmio de volatilidade, se existe nesses papéis, não sobra depois de pagar o risco.
4. **O filtro de IV Rank escolhe dias piores que o acaso.** Os dias com IV alta são dias de mercado agitado, com
   ofertas mais largas e movimentos que disparam o stop. Entradas em dias sorteados perderam menos.

**Ressalva:** as ofertas do COTAHIST são as que sobram no fechamento, provavelmente mais largas que as do meio
do pregão. Isso explica parte da perda, mas não salva a estratégia: o limite otimista, que ignora esse custo,
também não bate o CDI.
