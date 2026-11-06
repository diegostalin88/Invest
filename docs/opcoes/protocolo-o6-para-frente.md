# Protocolo do teste para frente da O6: a ordem estruturada é executada?

Rascunho de 06/11/2026, a ser confirmado pelo Diego antes de começar. Depois de começar, as regras não mudam.

## Pergunta

O backtest da O6 (`hipotese-vrp.md`) só deu lucro supondo que a ordem estruturada a preço líquido seria executada
perto do meio das ofertas, na entrada e na recompra do alvo. Os dados diários da B3 não dizem se isso acontece. Este
teste responde só isso: **com que frequência, e a que preço, essas ordens são executadas de verdade?**

## Onde

Plataforma da XP, com o menor lote possível (100 opções por perna) em conta real, ou em conta simulada se houver.
Sem robô: as ordens são enviadas à mão.

**Sem ordem estruturada (preço único para as duas pernas), a trava é montada em duas etapas, sempre comprando a
proteção primeiro** (decisão do Diego em 06/11/2026). Assim nunca se fica vendido sem proteção: se a segunda etapa
não executar, sobra só uma put comprada barata, que no pior caso vira pó.

## Regras (iguais às da O6, versão 6 papéis)

- **Quando olhar:** todo dia útil, depois das 17h, para PETR4, VALE3, BOVA11, ITUB4, BBAS3 e PRIO3. Uma posição por
  papel.
- **Sinal:** VRP ≥ 4 pontos (IV de 30 dias − volatilidade realizada de 21 pregões). A lista do dia sai do script
  `opcoes/sinais_o6.py` (só leitura), que roda no GitHub Actions ("Opções - O6 para frente: lista do dia") e mostra,
  para cada papel com sinal, as duas opções, as ofertas, o crédito a pedir e o preço da recompra no alvo. Enquanto o
  pull request não for aceito, a lista roda quando acionada à mão; depois, todo dia útil às 20h30.
- **Montagem:** put vendida com delta mais perto de 0,15; comprada com delta mais perto de 0,05; vencimento de 35 a
  56 dias. Crédito pedido = meio das ofertas do fechamento das duas pernas. Só envia se o crédito for ≥ 12% da
  largura.
- **Envio, etapa 1 (proteção):** no dia seguinte, na abertura, compra a put de baixo (delta ~0,05) pela oferta de
  venda. Anota o preço pago.
- **Envio, etapa 2 (venda):** logo depois, ordem limite de venda da put de cima no **meio das ofertas do fechamento
  anterior mais o que a proteção custou acima do meio dela** (para o crédito líquido ficar o mesmo pedido), válida
  só no dia. Não executou, cancela e não persegue o preço; a put comprada fica até o vencimento.
- **Alvo:** com a trava montada, recompra em duas etapas também, na ordem inversa: primeiro a ordem limite de
  recompra da put vendida; só depois de executada, a venda da put comprada. O preço da recompra é o que deixa o custo
  líquido em 25% do crédito, dado o preço de tela da put comprada. Renovada todo dia até o vencimento. Sem stop.

## O que anotar (uma linha por ordem, numa planilha)

Data, papel, as duas opções, crédito pedido, ofertas de compra e venda de cada perna no envio, preço pago na
proteção, se a venda executou (sim ou não), horário e preço da execução. Quando a venda não executa, anota também o
que a put comprada valeu no vencimento (é o custo das tentativas que não deram certo). Para a recompra: data, preço pedido, se executou e a que preço. No
vencimento: valor intrínseco e resultado.

## Duração e critério

- **Duração:** 3 meses ou 40 ordens de entrada enviadas, o que vier depois.
- **A execução se confirma** se:
  1. pelo menos 50% das vendas da etapa 2 forem executadas no preço pedido;
  2. pelo menos 50% das travas montadas tiverem a recompra a 25% executada antes do vencimento;
  3. o custo das proteções que sobraram sozinhas for menor que 25% do crédito recebido nas travas montadas.
- Se confirmar, a O6 ganha um novo registro com o histórico desses 3 meses como fora da amostra. Se não confirmar, a
  linha de travas na B3 se encerra.

## O que este teste não responde

Se a O6 dá lucro. Com 3 meses e poucas operações, o resultado em reais não diz nada. O único objetivo é medir a
execução.
