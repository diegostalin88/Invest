# Hipótese O3: ordem limite no meio das ofertas e levar até o vencimento (B3)

Registrado em **05/11/2026, antes de rodar qualquer número**, depois das reprovações da O1
(`hipotese-travas-credito.md`) e da O2 (`hipotese-travas-debito.md`). As regras e os critérios abaixo não mudam
depois de ver o resultado. Estudo só de leitura, separado do app e da estratégia congelada (`docs/congelamento.md`).

## Por que este teste

Nas duas hipóteses anteriores a perda veio, antes de tudo, da diferença entre as ofertas de compra e venda: entrar
pela oferta e sair pela oferta custava de 40% a 190% do prêmio, e o stop curto disparava logo depois da entrada.
Este teste muda só a **execução**, nas mesmas regras de entrada:

1. **Entrada com ordem limite no meio das ofertas**, que só conta como executada se o mercado de fato negociou a
   opção naquele preço ou melhor no dia.
2. **Sem stop e sem alvo:** a trava fica até o vencimento e é liquidada pelo valor intrínseco. Assim não se paga a
   diferença entre as ofertas na saída.

Se nem assim houver resultado, o problema não é a execução, e a linha de travas com dados diários se encerra.

## Versões

Só as versões simples (o gatilho técnico não acrescentou nada na O1 nem na O2, e testar menos versões diminui a
chance de uma passar por sorte).

| Versão | Regras de entrada | Montagem |
| --- | --- | --- |
| Crédito | As da versão simples da O1: ADX(14) < 20 → iron condor (IV Rank ≥ 60); acima da MME200 → trava de alta com put; abaixo → trava de baixa com call (IV Rank ≥ 50) | Vendida com delta mais perto de 0,25 (0,16 no condor), comprada com largura perto de 5% do preço |
| Débito | As da versão simples da O2: ADX(14) ≥ 20; acima da MME200 → trava de alta com call; abaixo → trava de baixa com put; IV Rank ≤ 35 | Comprada no dinheiro, vendida com largura perto de 5% do preço |

Vencimento entre 25 e 50 dias corridos, o mais perto de 35. Uma posição por ativo. Mesmos papéis e períodos da O1:
PETR4, VALE3, BOVA11, ITUB4, BBAS3 e PRIO3 (este a partir de 2022); dentro da amostra 2019 a 2022; **fora da
amostra 01/2023 a 10/2026, de onde sai o veredito.**

## Execução

- **Sinal** no fechamento do pregão D. No mesmo fechamento, escolhem-se as pernas pela cadeia de D, e o **preço
  limite de cada perna é o meio entre as ofertas de D** (tudo conhecido em D, sem olhar para frente).
- **Pregão D+1:** a perna vendida é executada se a opção foi negociada a um preço **maior ou igual** ao limite
  (máxima do dia, PREMAX ≥ limite); a comprada, se foi negociada a um preço **menor ou igual** ao limite (mínima do
  dia, PREMIN ≤ limite). Só entra se **todas** as pernas forem executadas, pelo preço limite. Se alguma não for, a
  ordem é cancelada e não se tenta de novo; o ativo volta a poder dar sinal no fechamento de D+1.
- **Saída:** nenhuma antes do vencimento. No dia do vencimento (ou no primeiro pregão depois dele), a trava vale o
  valor intrínseco pelo fechamento do papel.
- **Custo:** R$ 0,005 por opção por perna na entrada e outro tanto no vencimento (exercício).
- **Tamanho:** perda máxima de 1% do capital por operação (crédito: largura − crédito; débito: o débito pago).
  Capital inicial de R$ 100 mil; o que não está em risco rende CDI.
- **Marcação diária** (só para a curva e a queda máxima): pelo meio das ofertas.

Limitações conhecidas, a favor da estratégia: supõe que a ordem seria atendida sempre que houve negócio no preço
(sem fila), e que as pernas saem juntas, sem risco de executar uma e não a outra. No vencimento, supõe liquidação
pelo intrínseco, sem o custo de comprar ou vender o papel no exercício. A auditoria mede o peso das duas primeiras.

## Comparações

1. CDI acumulado e BOVA11 comprado e mantido.
2. **Mesmas regras sem filtro de IV Rank**, para cada versão (teste da tese do IV Rank).
3. **Informativo:** entrada pelas ofertas (como na O1 e na O2), também até o vencimento. Separa o efeito do stop do
   efeito da ordem limite.

## Critério de aprovação (fora da amostra, todos, para cada versão)

1. Retorno total acima do CDI acumulado.
2. Fator de lucro ≥ 1,2.
3. Pelo menos 50 operações encerradas.
4. Queda máxima da carteira ≤ 15%.
5. Sem o ativo de melhor resultado, o retorno ainda fica acima do CDI.
6. Com filtro de IV Rank, o resultado por operação é melhor que sem filtro (da mesma versão).

Uma versão aprovada vale como indício, a confirmar no teste para frente (paper trading), porque é o terceiro teste
sobre os mesmos dados fora da amostra.

## Resultado

(preenchido depois da execução)
