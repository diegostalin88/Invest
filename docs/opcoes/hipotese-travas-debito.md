# Hipótese O2: travas de débito direcionais com IV Rank baixo (B3)

Registrado em **05/11/2026, antes de rodar qualquer número**, depois da reprovação da O1
(`docs/opcoes/hipotese-travas-credito.md`). Escolha do Diego. Duas versões do gatilho lado a lado, como na O1.
As regras e os critérios abaixo não mudam depois de ver o resultado.

Estudo só de leitura, separado do app e da estratégia congelada. Mesmos dados, universo, períodos, capital,
custos e forma de execução da O1 (melhor oferta no fechamento do COTAHIST, execução no pregão seguinte ao sinal).

## Pergunta

Comprar direção com risco limitado (trava de alta com call, trava de baixa com put) **quando a opção está barata**
(IV Rank baixo) rende mais que o CDI fora da amostra?

**Expectativa declarada antes de rodar:** baixa. A trava de débito só ganha se a direção estiver certa, e a
auditoria de 04/11/2026 do Invest mostrou que os sinais técnicos não acertam a direção melhor que o acaso. A O1
também mostrou que atravessar as ofertas custa caro. O teste existe para medir isso com preços reais.

## Regras

### Versão simples

| Condição | Estrutura |
| --- | --- |
| ADX(14) ≥ 20 e fechamento acima da MME200 | Trava de alta com call |
| ADX(14) ≥ 20 e fechamento abaixo da MME200 | Trava de baixa com put |

### Versão técnica (estudo do Diego de 05/11/2026)

| Condição | Estrutura |
| --- | --- |
| Fechamento acima da máxima dos 20 pregões anteriores, com volume ≥ 1,5 × a média de 20 | Trava de alta com call |
| Fechamento abaixo da mínima dos 20 pregões anteriores, com volume ≥ 1,5 × a média de 20 | Trava de baixa com put |

A "retomada da VWAP" e o "fluxo do ADL" do estudo não têm como ser calculados com dados diários do COTAHIST;
o rompimento com volume é a parte objetiva que sobra.

### Comum às duas

- **Filtro:** IV Rank ≤ 35 no dia do sinal.
- **Vencimento:** entre 25 e 50 dias corridos, o mais perto de 35.
- **Pernas:** compra a opção com strike mais perto do preço à vista; vende a de strike mais distante cuja largura
  fique mais perto de 5% do preço à vista.
- **Tamanho:** débito pago = 1% do capital por operação. Uma posição por ativo.
- **Saída, a primeira que acontecer, a partir do pregão seguinte à entrada:** a trava vale ≥ 75% da largura
  (ganho); vale ≤ 50% do débito pago (perda); faltam ≤ 7 dias corridos para o vencimento. No vencimento, valor
  intrínseco.
- **Custo:** compra na oferta de venda, vende na de compra, mais R$ 0,005 por opção por perna.

## Comparações e critério

Os mesmos da O1, para cada versão, fora da amostra (01/2023 a 10/2026):

1. Retorno total acima do CDI acumulado.
2. Fator de lucro ≥ 1,2.
3. Pelo menos 50 operações encerradas.
4. Queda máxima da carteira ≤ 15%.
5. Sem o ativo de melhor resultado, o retorno ainda fica acima do CDI.
6. Com filtro de IV Rank, o resultado por operação é melhor que sem filtro (da mesma versão).

Robustez (informativa, só na simples): IV Rank até 25 e até 45; largura 3% e 8%; alvo em 50% da largura; custo × 2.

## Resultado

**Veredito: as duas versões REPROVADAS.** Execução válida de 05/11/2026
([run 42122050500](https://github.com/diegostalin88/Invest/actions/runs/42122050500)), já com o CDI real obrigatório.

Fora da amostra (01/2023 a 10/2026), capital de R$ 100 mil, caixa livre rendendo CDI:

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco por operação | Retorno total | CDI | BOVA11 | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Simples | 399 | 4% | 0,04 | −70% | −84,4% | 59,7% | 60,6% | 84,5% |
| Técnica | 92 | 5% | 0,04 | −65% | −8,4% | 59,7% | 60,6% | 15,4% |

Na simples, 379 das 399 operações saíram pelo stop, a maioria um a três pregões depois da entrada. As duas versões
só passam no critério de número de operações (a técnica passa também no do filtro de IV Rank, mas perdendo menos
por operação que sem filtro não basta). Todas as variantes de robustez perdem entre 62% e 78% do risco por
operação, e dentro da amostra (2019 a 2022) o quadro é o mesmo.

A causa é a mesma da O1: a diferença entre as ofertas. Montar e desmontar na hora custa, na mediana, 53% do débito
pago na simples e 40% na técnica; logo depois da entrada a trava já vale, pela oferta de compra, perto da metade do
que custou, e o stop em 50% do débito dispara. Mesmo no limite otimista (tudo no meio das ofertas) a simples empata
(−0,8% por operação, fator de lucro 0,98) e a técnica perde (−11%). Ou seja, a previsão de direção não traz vantagem
nem sem custo de execução, o que bate com a auditoria do motor do Invest (`docs/congelamento.md`).

Detalhes em `docs/opcoes/auditoria-o2.md`.

### Reexecução com o ajuste de strike por proventos (06/11/2026)

Com a correção do strike das pernas abertas depois de proventos (ver `hipotese-travas-credito.md`), reexecutado
([run 42144083436](https://github.com/diegostalin88/Invest/actions/runs/42144083436)): simples −70,0% por operação,
retorno −84,4%; técnica −65,0%, retorno −8,4%. Os mesmos números. **Veredito mantido.**

### 1ª execução (run 42117270727): descartada

O passo do backtest não conseguiu baixar o CDI e usou a reserva de 10% ao ano, o que mudou o CDI de referência
(43,7% em vez de 59,7%) e o tamanho das posições (393 operações em vez de 399). O veredito era o mesmo. Correção: os
três scripts (`travas.py`, `debito.py`, `auditoria_o1.py`) agora param com erro se o CDI real não baixar.
