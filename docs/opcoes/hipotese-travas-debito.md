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

(preenchido depois da execução)
