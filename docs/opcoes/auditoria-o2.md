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

(preenchido depois da execução)
