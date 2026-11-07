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
