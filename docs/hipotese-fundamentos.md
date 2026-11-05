# Hipóteses C (carteira por fundamentos) e D (reação ao balanço)

Registrado em **05/11/2026, antes de baixar os balanços históricos e antes de rodar qualquer número**. As regras e os critérios abaixo não mudam depois de ver o resultado.

São estudos só de leitura, separados do app. Não mexem na estratégia congelada (`docs/congelamento.md`).

**Motivação.** O Diego perguntou se uma abordagem por fundamentos funciona melhor que a técnica. A literatura tem dois efeitos fundamentalistas com décadas de estudos:
- **valor:** lucro alto em relação ao preço;
- **qualidade:** lucro bruto alto em relação aos ativos (Novy-Marx, 2013).

Ela também registra a **deriva depois do balanço**: o preço continua andando na direção da surpresa do resultado por algumas semanas.

## Dados (EUA nesta etapa)

- **Balanços:** XBRL da SEC (`companyfacts`), com o **campo `filed`**, que é a data em que o número ficou público. Um número só pode ser usado a partir do pregão **seguinte** a essa data.
- **Data da divulgação do resultado (para D):** o 8-K item 2.02 mais próximo, entre 0 e 60 dias antes do 10-Q/10-K. Sem 8-K, vale a data do próprio 10-Q/10-K.
- **Preços:** Yahoo Finance desde 2009, com dois preços:
  - o fechamento ajustado por proventos, para os retornos;
  - o fechamento ajustado só por desdobramento, junto com as datas de desdobramento, para o valor de mercado.
- **Candidatos:** os 1.000 papéis dos EUA mais negociados hoje no app que têm CIK na SEC.
- **Lucro dos últimos 12 meses:** soma dos últimos 4 trimestres de 3 meses. O 4º trimestre é calculado como o ano menos os três primeiros, disponível na data do 10-K. Os 4 trimestres precisam ser consecutivos.

## Hipótese C: carteira valor + qualidade

- **Rebalanceamento:** último pregão de fevereiro, maio, agosto e novembro, cerca de 45 dias depois do fim de cada trimestre.
- **Elegíveis em cada data:**
  - preço ≥ US$ 5;
  - entre os 500 mais negociados (volume financeiro médio de 60 pregões) **naquela data**;
  - com lucro dos 12 meses, lucro bruto dos 12 meses, ativo total, patrimônio > 0 e número de ações;
  - último balanço com fim de período até 200 dias antes da data;
  - lucro dos 12 meses > 0.
- **Nota:** média dos percentis de dois indicadores entre os elegíveis:
  - **valor** = lucro dos 12 meses ÷ valor de mercado;
  - **qualidade** = lucro bruto dos 12 meses ÷ ativo total.
- **Carteira:** as 30 maiores notas, pesos iguais. Custo de 0,1% sobre o giro a cada rebalanceamento.
- **Comparações:**
  - SPY com dividendos;
  - todos os elegíveis com pesos iguais;
  - 200 carteiras sorteadas de 30 elegíveis, com o mesmo custo.
- **Robustez:** só valor; só qualidade; 15 e 60 papéis; custo ×2; rebalanceamento semestral (maio e novembro).

**Critérios (todos):**
1. O retorno total fica acima do **percentil 95** das carteiras sorteadas.
2. O retorno anual fica acima do SPY, com queda máxima até 1,5× a do SPY.
3. Vence a carteira de todos os elegíveis com pesos iguais **nas duas metades** do período.
4. Com custo ×2, continua acima do SPY.

## Hipótese D: deriva depois do balanço

- **Evento:** cada 10-Q/10-K dos elegíveis (mesmos filtros de C, na data do evento).
- **Surpresa:** variação do lucro do trimestre contra o mesmo trimestre do ano anterior, dividida pelo ativo total.
- **Reação:** do fechamento 2 pregões antes da divulgação até o fechamento 1 pregão depois.
- **Deriva:** do fechamento 1 pregão depois até 60 pregões depois. Mede-se o retorno do papel e o retorno do papel menos o SPY nas mesmas datas.
- **Grupos:** quintis de surpresa em cada trimestre do calendário. Compara-se o quintil mais alto com o mais baixo.

**Critérios (todos):**
1. A deriva do quintil alto, menos a do baixo, é positiva e fica acima do **percentil 95** de 500 embaralhamentos da surpresa dentro de cada trimestre.
2. A diferença é positiva **nas duas metades** do período.
3. Comprar só o quintil alto rende acima do SPY nas mesmas datas, em média, depois de custo de 0,2% (ida e volta).

## Limitações conhecidas antes de rodar

- **Viés de sobrevivência:** os candidatos são empresas que existem e são negociadas hoje. Quem quebrou ou foi comprada não aparece, o que favorece qualquer carteira de ações contra o SPY. Por isso, os critérios exigem bater as carteiras sorteadas e os pesos iguais **do mesmo universo**, e não só o índice.
- **XBRL só a partir de 2009–2011:** o período é de cerca de 15 anos, com um mercado de alta longo.
- **Etiquetas do XBRL variam entre empresas** (por exemplo, `Revenues` ou `RevenueFromContractWithCustomerExcludingAssessedTax`). Se o número não existir, a empresa fica de fora naquela data, nunca é estimada.
- **Brasil:** vem numa etapa separada (balanços da CVM), com as mesmas regras e um registro próprio antes de rodar.

## Resultado (rodado em 05/11/2026, 00:31 UTC, depois do registro acima)

Dados: 999 papéis dos EUA com balanço na SEC e preço desde 2009 (execução 41940350930 do GitHub Actions).

### C: valor + qualidade, **REPROVADA**

De 28/02/2011 a 04/11/2026: 63 rebalanceamentos, cerca de 155 elegíveis por data.

| carteira | retorno total | ao ano | queda máxima | Sharpe |
|---|---|---|---|---|
| valor + qualidade (30 papéis) | 609% | 13,2% | 21,2% | 1,10 |
| SPY | 659% | 13,7% | 12,3% | 1,34 |
| todos os elegíveis, pesos iguais | 741% | 14,5% | 14,8% | 1,28 |
| acaso (200 carteiras de 30) | p5 464% · mediana 663% · p95 966% | | | |

Robustez (todas abaixo do SPY): só valor 10,0% ao ano; só qualidade 13,3%; 15 papéis 12,8%; 60 papéis 13,5%; custo ×2 13,0%; semestral 12,9%.

Metades: 2011–2018, carteira 188% × pesos iguais 183% × SPY 142%. 2018–2026, carteira 146% × pesos iguais 197% × SPY 214%.

Os quatro critérios falharam: ficou abaixo da mediana do acaso, perdeu para o SPY com quase o dobro da queda, perdeu para os pesos iguais na 2ª metade e, com custo ×2, continuou abaixo do SPY. Valor e qualidade venceram de 2011 a 2018 e perderam muito de 2018 a 2026, a fase das grandes empresas de tecnologia.

### D: deriva depois do balanço, **APROVADA nos critérios registrados, com ressalvas**

De 2009T3 a 2026T3, 25.940 balanços.

- **Reação** (de 2 pregões antes a 1 depois): quintil alto +1,48%, baixo −0,33%.
- **Deriva de 60 pregões:**
  - alto +4,68%, baixo +3,71%;
  - diferença **0,96 ponto**, contra p50 0,01 e p95 0,64 de 500 embaralhamentos;
  - metades: **0,06** e **1,69** ponto.
- **Quintil alto menos SPY, depois de 0,2% de custo:** +1,03 ponto. A média de todos os balanços rendeu 3,74%, contra 3,46% do SPY nas mesmas datas.

Os três critérios passaram. Mas, antes de chamar de vantagem, ficam as ressalvas:

1. **A 1ª metade quase não tem efeito (0,06 ponto).** Tudo vem de 2018 a 2026. A literatura registra que essa deriva enfraqueceu nas grandes empresas depois dos anos 2000. Aqui ela some e volta, o que pede confirmação.
2. **O viés de sobrevivência infla a comparação com o SPY.** Mesmo a média de todos os balanços venceu o SPY (+0,28 ponto). O ganho do quintil alto sobre a média do próprio universo é de cerca de 0,9 ponto em 60 pregões, antes do custo.
3. **O efeito é pequeno e exige muitas operações:** cerca de 1 ponto a cada 3 meses, comprando dezenas de papéis por temporada de balanços. No Brasil, com corretagem, emolumentos e 15% de IR sobre o ganho, sobra menos.

**Próximo passo:** uma confirmação registrada antes de rodar (`docs/hipotese-deriva-confirmacao.md`), com o quintil alto contra o próprio universo, ano a ano, só grandes empresas e uma carteira contínua. Enquanto ela não passar, o app só **mostra** a surpresa do balanço como informação, sem sinal de compra.
