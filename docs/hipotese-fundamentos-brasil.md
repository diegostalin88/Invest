# Hipótese C-BR: carteira de ações baratas e boas pagadoras de dividendos no Brasil

Registrado em **06/11/2026, antes de baixar os dados e de rodar qualquer número**. As regras e os critérios abaixo
não mudam depois de ver o resultado. Estudo só de leitura, separado do app e da estratégia congelada
(`docs/congelamento.md`).

**Motivação.** Depois dos testes de opções (`docs/opcoes/relatorio-testes.md`), a análise de outra IA trazida pelo
Diego afirmou que o "terreno fértil comprovado" na B3 seriam ações com valuation descontado (P/L baixo e
dividendos), citando os 82,4% de comprar e manter quatro papéis na O5. Esse número não testa nenhuma regra de
escolha. Este teste faz a etapa do Brasil prevista em `docs/hipotese-fundamentos.md` (a hipótese C, valor +
qualidade, foi reprovada nos EUA), com os dois indicadores da proposta: **lucro sobre preço** e **dividendos sobre
preço**.

## Dados

- **Balanços:** dados abertos da CVM (ITR trimestral e DFP anual, 2010 a 2026), com o código de `coleta/balancos_cvm.py`
  (consolidado, ou individual se não houver consolidado). Um número só vale a partir do pregão **seguinte** à data
  da primeira entrega à CVM (`DT_RECEB`).
- **Ações em circulação:** composição do capital do mesmo ITR/DFP (total menos tesouraria), com a mesma regra de
  data.
- **Lucro dos 12 meses:** soma dos 4 últimos trimestres disponíveis, consecutivos; o 4º trimestre é o ano (DFP)
  menos os 9 meses do ITR de setembro. O último trimestre precisa ter terminado até 200 dias antes da data.
- **Preços:** Yahoo Finance (sufixo .SA), desde 2010: fechamento ajustado por proventos para o retorno total, e
  fechamento ajustado só por desdobramento para o valor de mercado.
- **Dividendos dos 12 meses (por ação ÷ preço):** deduzidos da razão entre o fechamento ajustado e o não ajustado
  um ano antes e hoje. Essa razão só muda com proventos e usa só datas ex já passadas.
- **CDI:** Banco Central (série SGS 12). **Índice:** BOVA11 com o fechamento ajustado.

## Universo

- Papéis da lista de reserva da carteira do IBOVESPA (`coleta/ibovespa_reserva.txt`, 82 códigos).
- **Ficam de fora as units** (código terminado em 11), porque o preço é de um pacote de ações e o valor de mercado
  sairia errado.
- **Um código por empresa** (o de maior volume financeiro na data), para não comprar a mesma empresa duas vezes.

## Regras

- **Rebalanceamento:** último pregão de março, junho, setembro e dezembro.
- **Elegíveis em cada data:**
  - preço ≥ R$ 1;
  - volume financeiro médio de 60 pregões ≥ R$ 5 milhões;
  - lucro dos 12 meses > 0, patrimônio > 0 e número de ações;
  - P/L entre 1 e 100. Abaixo de 1 é tratado como erro de escala nos dados da CVM e fica de fora; a quantidade de
    exclusões é informada.
- **Nota:** média dos percentis de dois indicadores entre os elegíveis:
  - **valor** = lucro dos 12 meses ÷ valor de mercado (o inverso do P/L);
  - **dividendos** = dividendos por ação dos 12 meses ÷ preço.
- **Carteira:** as **15** maiores notas, pesos iguais. Custo de 0,1% sobre o giro a cada rebalanceamento. Imposto
  fora.
- Uma data só entra se houver pelo menos 30 elegíveis.
- **Comparações:** BOVA11; CDI; todos os elegíveis com pesos iguais; 200 carteiras sorteadas de 15 elegíveis, com o
  mesmo custo.
- **Robustez:** só valor; só dividendos; 10 e 20 papéis; custo × 2; rebalanceamento semestral (março e setembro).

## Critérios de aprovação (todos)

1. O retorno total fica acima do **percentil 95** das carteiras sorteadas.
2. O retorno anual fica acima do BOVA11, com queda máxima até 1,5 × a do BOVA11.
3. Vence a carteira de todos os elegíveis com pesos iguais **nas duas metades** do período.
4. Com custo × 2, continua acima do BOVA11.
5. O retorno total fica acima do CDI acumulado no mesmo período.

## Limitações conhecidas antes de rodar

- **Viés de sobrevivência:** o universo é a carteira atual do IBOVESPA. Empresas que saíram do índice, quebraram ou
  fecharam o capital não aparecem, e as que entraram costumam ter subido antes. Isso favorece qualquer carteira
  contra o BOVA11. Por isso, os critérios 1 e 3 comparam com carteiras sorteadas e pesos iguais **do mesmo
  universo**.
- **Valor de mercado aproximado:** total de ações (ordinárias e preferenciais) vezes o preço do código escolhido.
  Quando as duas classes têm preços muito diferentes, o P/L sai aproximado.
- **Dividendos do Yahoo:** incluem juros sobre capital próprio como provento; podem faltar em alguns papéis.
- **Período:** cerca de 14 anos (2012 a 2026), com CDI alto em boa parte; um único período, sem amostra separada.
  Por isso o critério 3 olha as duas metades.

## 1ª execução (06/11/2026, run 42198555992): descartada por erro nos dados

A conferência à mão no próprio log mostrou que a quantidade de ações vinha errada para muitas empresas: VALE3 com
4,07 milhões de ações (são 4,07 bilhões) e ITUB4 com 11 milhões (são cerca de 11 bilhões). Parte das companhias
informa a composição do capital à CVM **em milhares de ações**, sem indicar a escala. O valor de mercado saía 1.000
vezes menor e o P/L ficava abaixo de 1; essas empresas eram excluídas pela regra de "erro de escala" (452 exclusões).
Com isso, antes de 2021 quase nenhuma data tinha 30 elegíveis, o teste só começou em 06/2021, e o universo ficou
restrito às empresas que informam em unidades. O resultado não vale.

**Correção (nenhuma outra regra mudou):** quando o valor de mercado calculado fica abaixo de R$ 1 bilhão, a quantidade
de ações é tratada como informada em milhares e multiplicada por 1.000. Todas as empresas do universo valem mais de
R$ 1 bilhão. O número de correções e os papéis corrigidos aparecem no resultado. A regra do P/L entre 1 e 100
continua valendo como segunda proteção.
