# Hipótese O4: box de 4 pontas como renda fixa (B3)

Registrado em **05/11/2026, antes de rodar qualquer número**, a pedido do Diego (um colega dele operava estruturas
de opções com "rendimento fixo"). As regras, os critérios e a auditoria abaixo não mudam depois de ver o resultado.
Estudo só de leitura, separado do app e da estratégia congelada.

## Pergunta

Comprar um **box de 4 pontas** na B3, pelas ofertas do fechamento, rende mais que o CDI do mesmo período? O box é
uma trava de alta com calls (compra call K1, vende call K2) somada a uma trava de baixa com puts (compra put K2,
vende put K1), no mesmo vencimento. No vencimento vale sempre K2 − K1, qualquer que seja o preço do papel, então o
rendimento fica travado na entrada.

## Dados

COTAHIST da B3, 2018 a 2026, mesmos papéis da O1 (PETR4, VALE3, BOVA11, ITUB4, BBAS3, PRIO3). Melhores ofertas do
fechamento (PREOFC e PREOFV). CDI diário do Banco Central (série 12). Dentro da amostra 2019 a 2022; **fora da
amostra 01/2023 a 10/2026, de onde sai o veredito.**

## Regras

- **Boxes possíveis:** no mesmo papel e vencimento (entre 20 e 70 dias corridos), dois strikes K1 < K2 com call e
  put negociáveis nos dois (as quatro pernas com oferta de compra e de venda).
- **Preço pago** (por unidade): call K1 na oferta de venda − call K2 na oferta de compra + put K2 na oferta de venda
  − put K1 na oferta de compra + R$ 0,005 × 4 pernas. **Recebido no vencimento:** K2 − K1 − R$ 0,005 × 2
  (exercício das duas pernas no dinheiro).
- **Taxa do box:** (recebido ÷ pago) elevado a 252 ÷ pregões até o vencimento, menos 1. Comparada com o CDI
  efetivamente pago nos mesmos pregões, também ao ano.
- **Carteira:** no segundo pregão de cada mês, para cada papel, compra o box de **maior taxa** disponível naquele
  fechamento (desde que a taxa seja positiva), com até 1/6 do capital por papel, em lotes de 100. Fica até o
  vencimento. O dinheiro fora de box rende CDI. Capital inicial de R$ 100 mil.

## Critério de aprovação (fora da amostra, todos)

1. Retorno da carteira acima do CDI acumulado.
2. Em pelo menos 50% dos boxes comprados, a taxa ficou acima do CDI do mesmo período.
3. Pelo menos 50 boxes comprados.
4. Nenhum box com prejuízo nominal (recebido menor que o pago). Um prejuízo indica erro de dado ou de cálculo,
   porque o box não tem risco de preço.

## Informativo

- Distribuição de **todos** os boxes possíveis (não só os escolhidos): mediana e quartis de taxa − CDI, em pontos
  percentuais ao ano. Escolher o box de maior taxa tende a pegar ofertas velhas ou erradas; a mediana mostra o box
  típico.
- Os mesmos números com preço no meio das ofertas (limite otimista).
- Imposto: o box é tributado como renda fixa (alíquota regressiva, como um CDB), então a comparação com o CDI bruto
  vale para os dois lados.
- Riscos fora do modelo: exercício antecipado da call vendida (as calls de ações na B3 são americanas; o efeito é
  receber antes, mas pode haver custo na entrega do papel) e corretagem real da corretora.

## Auditoria adversarial (mesma execução)

1. **Reprodução:** rodar duas vezes dá o mesmo número.
2. **Compra um pregão depois** de escolher o box (pelas ofertas do pregão seguinte, mesmo box). Se a vantagem some,
   ela vinha de oferta que não estava lá de verdade.
3. **Custo × 4.**
4. **Só boxes com negócio nas 4 pernas no dia** (máxima negociada > 0 em todas). Ofertas sem negócio podem ser
   velhas.
5. **Terceiro melhor box** em vez do melhor: mede quanto o resultado depende do topo da lista.
6. **Resultado por ano**, para ver se vem de um único período.
7. **Conferência à mão:** 5 boxes sorteados com pernas, preços e taxa, para conferir contra as cotações da B3.

O resultado **resiste à auditoria** se, com a compra um pregão depois e com só pernas negociadas, o retorno
continuar acima do CDI, e pelo menos 3 dos 4 anos fora da amostra ficarem acima do CDI.

## Resultado

(preenchido depois da execução)
