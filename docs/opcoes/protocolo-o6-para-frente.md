# Protocolo do teste para frente da O6: a ordem estruturada é executada?

Rascunho de 06/11/2026, a ser confirmado pelo Diego antes de começar. Depois de começar, as regras não mudam.

## Pergunta

O backtest da O6 (`hipotese-vrp.md`) só deu lucro supondo que a ordem estruturada a preço líquido seria executada
perto do meio das ofertas, na entrada e na recompra do alvo. Os dados diários da B3 não dizem se isso acontece. Este
teste responde só isso: **com que frequência, e a que preço, essas ordens são executadas de verdade?**

## Onde

Plataforma da XP com envio de estratégia (ordem de duas pernas com preço líquido), em **conta simulada** se houver;
se não houver, com o menor lote possível (100 opções por perna) em conta real, risco máximo de algumas centenas de
reais por operação. Sem robô: as ordens são enviadas à mão.

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
- **Envio:** no dia seguinte, na abertura, ordem estruturada com o crédito pedido, **válida só no dia**. Não executou,
  cancela e não persegue o preço.
- **Alvo:** executada a entrada, deixa uma ordem estruturada de recompra a 25% do crédito, renovada todo dia até o
  vencimento. Sem stop.

## O que anotar (uma linha por ordem, numa planilha)

Data, papel, as duas opções, crédito pedido, ofertas de compra e venda de cada perna no envio, se executou (sim, não
ou parcial), horário e preço da execução. Para a recompra: data, preço pedido, se executou e a que preço. No
vencimento: valor intrínseco e resultado.

## Duração e critério

- **Duração:** 3 meses ou 40 ordens de entrada enviadas, o que vier depois.
- **A execução se confirma** se:
  1. pelo menos 50% das ordens de entrada forem executadas no crédito pedido;
  2. pelo menos 50% das entradas executadas tiverem a recompra a 25% executada antes do vencimento;
  3. nenhuma execução parcial (uma perna sem a outra).
- Se confirmar, a O6 ganha um novo registro com o histórico desses 3 meses como fora da amostra. Se não confirmar, a
  linha de travas na B3 se encerra.

## O que este teste não responde

Se a O6 dá lucro. Com 3 meses e poucas operações, o resultado em reais não diz nada. O único objetivo é medir a
execução.
