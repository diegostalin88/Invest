# Hipóteses novas: momento de 12 meses e tendência no índice

Pedido do Diego em 04/11/2026, depois da auditoria adversarial. É um teste **separado** da estratégia congelada (`docs/congelamento.md`): não muda o app nem o Relatório.
Este arquivo foi escrito e publicado **antes** de rodar qualquer número. Parâmetros e critérios não podem mudar depois de ver o resultado.

## Hipótese A: momento de 12 meses entre ações (estilo Jegadeesh & Titman, AQR)

**Regra (fixa, da literatura, sem ajuste):**

1. **Rebalanceamento no último pregão de cada mês.**
2. **Papéis elegíveis:**
   - Têm preço no dia e há 252 pregões.
   - O preço é de pelo menos US$ 5 (EUA) ou R$ 2 (Brasil).
   - Estão entre os **400 mais líquidos dos EUA** ou os **60 mais líquidos do Brasil**. A liquidez é medida pelo volume financeiro médio dos 20 pregões **até aquela data**, não pela liquidez de hoje.
3. **Nota de cada papel:** o retorno de 12 meses **sem o último mês** (do pregão −252 ao −21).
4. **Carteira:** compra em pesos iguais as **40 maiores notas nos EUA** (o décimo superior) e as **10 maiores no Brasil**. A posição é mantida até o fim do mês seguinte.
5. **Custo:** 0,1% por perna sobre o que é trocado na carteira.

**Comparações:**

- índice real (SPY nos EUA, BOVA11 no Brasil);
- carteira de pesos iguais com todos os elegíveis;
- 200 carteiras sorteadas, com o mesmo número de papéis, sorteadas todo mês entre os elegíveis (o acaso).

**Variações só para checar robustez** (nenhuma delas substitui a regra principal):

- momento de 6 e de 3 meses;
- metade e dobro de papéis;
- custo ×2.

**Aprovada se, nos dois mercados separadamente, valerem as três condições:**

1. O retorno total supera o percentil 95 das carteiras sorteadas.
2. O retorno total supera o do índice real, e a queda máxima não passa de 1,5 vez a do índice.
3. Com custo ×2, o retorno total continua acima do índice.

## Hipótese B: tendência no índice (estilo Faber, média de 10 meses)

**Regra (fixa):**

- No último pregão de cada mês, se o índice fechou **acima da média dos últimos 10 fechamentos mensais**, a posição fica no índice no mês seguinte.
- Se fechou abaixo, a posição vai para o caixa.
- Custo: 0,1% por troca.

**Dados:**

- EUA: SPY com dividendos (desde 1993).
- Brasil: Ibovespa (^BVSP, que já reinveste dividendos), desde 2000.
- O caixa rende o juro curto real: T-bill de 13 semanas (^IRX) nos EUA e CDI (série 12 do Banco Central) no Brasil. Se o juro não puder ser baixado, o caixa rende 0%, e isso é dito no resultado.

**Aprovada se, no período inteiro e também na segunda metade (a mais recente), valerem as duas condições:**

1. Sharpe maior ou igual ao de comprar e segurar.
2. Queda máxima de no máximo 2/3 da queda de comprar e segurar.

Esta hipótese não precisa render mais; o objetivo dela é cair menos.

## Limitações conhecidas (antes de rodar)

- **A: viés de sobrevivência.** Os dados de ações só têm as empresas que existem hoje, e as que quebraram ficam de fora. As carteiras sorteadas e a de pesos iguais usam o mesmo universo, então parte do viés se cancela na comparação, mas não com o índice.
- **A: histórico curto.** Os EUA têm cerca de 3 anos de dados, ou seja, uns 2 anos de teste depois dos 12 meses de nota. O Brasil tem 5 anos, ou seja, uns 4 de teste, e inclui 2022.
- **B: estudo já feito.** A regra B foi estudada com dados até 2008 na literatura. Os anos de 2009 a 2026 são, para ela, dados novos.

## Resultado (04/11/2026, rodado depois do registro acima, sem nenhum ajuste)

Execução: https://github.com/diegostalin88/Invest/actions/runs/41903112455

| teste | resultado | critérios | veredito |
|---|---|---|---|
| A · EUA (nov/2024 a nov/2026, 24 meses) | momento +45,9% (queda 33,9%) × SPY +28,1% (queda 7,6%); acaso p95 37,6% | acima do acaso: sim · vence o índice com queda ≤ 1,5×: **não** · custo ×2: sim | REPROVADA |
| A · Brasil (nov/2022 a nov/2026, 48 meses) | momento +28,5% (queda 17,1%) × BOVA11 +50,1% (queda 12%); acaso p95 49,8% | acaso: não · índice: não · custo ×2: não | REPROVADA |
| B · EUA (SPY, 1993 a 2026) | período inteiro: Sharpe 0,71 × 0,60, queda 22% × 51%; 2010–2026: anual 7,8% × 13,9%, Sharpe 0,60 × 0,88 | inteiro: sim · segunda metade: **não** | REPROVADA |
| B · Brasil (Ibovespa, 2000 a 2026, caixa no CDI) | Sharpe sobre o CDI −0,10 × 0,03; 2013–2026: −0,19 × 0,07 | inteiro: não · segunda metade: não | REPROVADA |

Leitura: o momento nos EUA escolheu melhor que o acaso, mas com queda 4,5× maior que a do índice num período curto (24 meses, só empresas que existem hoje). A tendência no índice reduz a queda, como a literatura diz, mas nos últimos 16 anos dos EUA custou retorno e Sharpe; no Brasil o CDI alto faz o caixa ganhar quase sempre do índice, então nenhuma das duas formas vence o juro.
