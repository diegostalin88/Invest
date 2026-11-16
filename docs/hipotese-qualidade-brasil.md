# Hipótese Q-BR: carteira de ações de qualidade no Brasil (rentáveis e pouco endividadas)

Registrado em **07/11/2026, antes de escrever o código e de baixar qualquer dado**. As regras e os critérios abaixo
não mudam depois de ver o resultado. Estudo só de leitura, separado do app e da estratégia congelada
(`docs/congelamento.md`).

## Por que este teste

O Diego quer montar uma carteira de longo prazo com **núcleo no índice** e pediu para testar se uma parte satélite
escolhida por **bons fundamentos** vale a pena no Brasil. Os testes anteriores olharam sobretudo **preço**: valor +
qualidade nos EUA (C) e lucro/preço + dividendos no Brasil (C-BR), os dois reprovados. Este teste olha só a
**qualidade da empresa**, sem olhar se a ação está barata, como no fator "qualidade" da literatura (Asness, Frazzini e
Pedersen, *Quality Minus Junk*, 2019): empresas que dão mais lucro sobre o capital dos sócios e dependem menos de
dívida.

**Aviso registrado antes:** os dados de 2012 a 2026 já foram usados pela C-BR com outros indicadores. Este é o
terceiro teste de seleção por fundamentos no Brasil; por isso os critérios são **mais duros** que os da C-BR (critério
6).

## Dados

- **Balanços:** dados abertos da CVM (ITR e DFP, 2010 a 2026), com o código de `coleta/balancos_cvm.py`
  (consolidado, ou individual se não houver). Um número só vale a partir do pregão **seguinte** à primeira entrega à
  CVM.
- **Lucro dos 12 meses:** soma dos 4 últimos trimestres consecutivos, como na C-BR. O último trimestre precisa ter
  terminado até 200 dias antes da data.
- **Patrimônio líquido, ativo total e passivo** (passivo = conta 2 menos o patrimônio) do último balanço disponível.
- Não precisa da quantidade de ações nem do valor de mercado, então cobre **todo o período desde 2012** (a C-BR só
  tinha valor de mercado a partir de 2020).
- **Preços:** Yahoo Finance (.SA), fechamento ajustado por proventos. **CDI:** Banco Central (SGS 12). **Índice:**
  BOVA11.

## Universo

O mesmo da C-BR: a lista de reserva do IBOVESPA (`coleta/ibovespa_reserva.txt`), sem units, um código por empresa (o
de maior volume financeiro na data).

## Regras

- **Rebalanceamento:** último pregão de março, junho, setembro e dezembro.
- **Elegíveis em cada data:** preço ≥ R$ 1; volume financeiro médio de 60 pregões ≥ R$ 5 milhões; 4 trimestres de
  lucro consecutivos; patrimônio > 0; ativo > 0.
- **Nota:** média dos percentis de dois indicadores entre os elegíveis:
  - **rentabilidade** = lucro dos 12 meses ÷ patrimônio líquido (ROE), maior é melhor;
  - **segurança** = passivo ÷ ativo total, menor é melhor.
- **Carteira:** as **15** maiores notas, pesos iguais. Custo de 0,1% sobre o giro a cada rebalanceamento. Imposto
  fora.
- Uma data só entra se houver pelo menos 30 elegíveis.
- **Comparações:** BOVA11; CDI; todos os elegíveis com pesos iguais; 200 carteiras sorteadas de 15 elegíveis, com o
  mesmo custo.
- **Robustez (só informação):** só rentabilidade; só segurança; 10 e 20 papéis; custo × 2; sem bancos e seguradoras
  (o passivo deles é o dinheiro dos clientes, o que sempre os coloca no fim da lista de segurança).

## Critérios de aprovação (todos)

1. O retorno total fica acima do **percentil 95** das carteiras sorteadas.
2. O retorno anual fica acima do BOVA11, com queda máxima até 1,5 × a do BOVA11.
3. Vence a carteira de todos os elegíveis com pesos iguais **nas duas metades** do período.
4. Com custo × 2, continua acima do BOVA11.
5. O retorno total fica acima do CDI acumulado no mesmo período.
6. **(mais duro que a C-BR)** Em **cada metade**, o retorno fica acima do **percentil 90** das carteiras sorteadas
   naquela metade.

Se passar, a carteira vira **candidata** a satélite no app, mostrada como informação e acompanhada para frente por 12
meses contra o BOVA11 e os pesos iguais antes de qualquer uso com dinheiro real. Se não passar, o satélite fica sem
seleção por fundamentos e o núcleo segue no índice.

## Limitações conhecidas antes de rodar

- **Viés de sobrevivência:** o universo é a carteira atual do IBOVESPA. Por isso os critérios 1, 3 e 6 comparam com o
  acaso e os pesos iguais **do mesmo universo**.
- **Período já visto** pela C-BR (outros indicadores): por isso o critério 6.
- **Lucro contábil:** itens não recorrentes (venda de ativos, impairment) entram no lucro dos 12 meses.
- **Bancos** ficam sempre mal na segurança; a robustez sem eles mostra o efeito.

## Resultado (07/11/2026, [run 42333421810](https://github.com/diegostalin88/Invest/actions/runs/42333421810))

A 1ª execução (run 42332572888) calculou tudo, mas caiu ao gravar o JSON antes de imprimir os números (tipo do
numpy); só a gravação foi corrigida, nenhuma regra mudou.

**Veredito: REPROVADA.** Passou nos critérios 1 a 5 e falhou no 6. Período de 30/03/2012 a 30/09/2026, 58
trimestres, ~52 elegíveis por data.

| Carteira | Retorno | Ao ano | Queda máx. | Sharpe |
| --- | --- | --- | --- | --- |
| **Qualidade (15 papéis)** | **734,3%** | **15,8%** | 31,5% | 0,79 |
| BOVA11 | 188,1% | 7,6% | 37,7% | 0,44 |
| CDI | 281,3% | 9,7% | 0,0% | – |
| Pesos iguais, todos os elegíveis | 510,1% | 13,3% | 35,8% | 0,65 |
| Acaso (200 carteiras de 15) | p5 244,4%, mediana 450,2%, p95 716,3% | | | |
| Só rentabilidade (ROE) | 749,6% | 15,9% | 34,3% | 0,82 |
| Só segurança (passivo/ativo) | 371,1% | 11,3% | 34,4% | 0,58 |
| 10 papéis | 524,1% | 13,5% | 34,3% | 0,68 |
| 20 papéis | 764,1% | 16,0% | 29,5% | 0,82 |
| Custo × 2 | 717,9% | 15,6% | 31,6% | 0,79 |
| Sem bancos e seguradoras | 694,7% | 15,4% | 30,8% | 0,77 |

- Percentil entre as carteiras sorteadas no período inteiro: **96** (critério 1 passou por pouco: 734% contra p95
  de 716%).
- **Metades (critério 6):**
  - 2012 a 2019: carteira 193,4% contra pesos iguais 190,3% e acaso mediana 177,7% / p90 254,9%: **percentil 60**.
    Falhou.
  - 2019 a 2026: carteira 184,4% contra pesos iguais 110,1% e acaso p90 151,1%: percentil 97. Passou.
- Por ano (carteira / BOVA11 / CDI): 2012 18,7/−6,6/5,7; 2013 −2,4/−15,8/7,9; 2014 9,4/−3,4/10,6;
  2015 −7,2/−13,2/13,0; 2016 35,4/38,2/13,9; 2017 48,2/26,8/9,9; 2018 2,9/14,6/6,3; 2019 58,6/31,5/5,9;
  2020 14,6/3,1/2,7; 2021 −8,2/−12,1/4,3; 2022 20,6/5,1/12,3; 2023 16,4/23,1/13,0; 2024 −2,9/−10,1/10,8;
  2025 35,9/34,7/14,1; 2026 11,2/16,5/10,5.
- Conferência à mão (balanço mais recente): PETR4 ROE 27,8%, passivo/ativo 62%; ITUB4 21,0% e 93%; WEGE3 31,3% e
  53%. VALE3 aparece com lucro de 12 meses de R$ 0,6 bilhão (o mesmo problema da CVM visto na C-BR).
- Carteira de hoje (só informação): CXSE3, BBSE3, ITSA4, WEGE3, VIVA3, MULT3, POMO4, ABEV3, TOTS3, CYRE3, B3SA3,
  LREN3, CURY3, PETR4, HYPE3.

**Leitura:** o mesmo desenho da C-BR. De 2012 a 2019 a seleção por qualidade empatou com os pesos iguais e com o
acaso do mesmo universo; toda a vantagem veio de 2019 a 2026. Pela regra registrada, isso não conta como vantagem
confirmada: a carteira **não entra no app como satélite** e não deve ser reaberta com outros pesos, indicadores ou
número de papéis no mesmo período. Uma confirmação honesta só pode vir **para frente**: se o Diego quiser, a lista de
hoje pode ser acompanhada por 12 meses contra o BOVA11 e os pesos iguais, sem dinheiro real.
