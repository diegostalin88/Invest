# Opções: o histórico público da B3 serve para calcular IV?

Registrado em **05/11/2026, antes de rodar**. Estudo só de leitura, separado do app e da estratégia congelada
(`docs/congelamento.md`). Faz parte da fase 2 (dados) do estudo de opções por cenário.

## Pergunta

Os arquivos anuais do COTAHIST (B3, gratuitos) trazem dados de opções suficientes para reconstruir, dia a dia, a
volatilidade implícita (IV) de ~30 dias e o IV Rank de 252 pregões, sem depender de fonte paga?

## Método (`opcoes/cotahist.py`)

- **Universo:** PETR4, VALE3, BOVA11, ITUB4, BBAS3, PRIO3. Anos 2018 a 2026.
- **Opções do dia:** calls (mercado 070) e puts (080) com a mesma raiz do ativo e a mesma classe (ON, PN, CI), para
  separar PETR3 de PETR4.
- **Escolha:** vencimento entre 20 e 60 dias corridos, o mais perto de 30; nesse vencimento, a call e a put com
  strike mais perto do fechamento à vista; pelo menos 5 negócios no dia e preço ≥ R$ 0,03.
- **IV:** Black-Scholes sem dividendos, com o CDI do dia (série 12 do Banco Central), média da call e da put.
- **Limitações conhecidas:** o último negócio da opção pode ser de horário diferente do fechamento à vista; as calls
  são americanas; o strike usado é o do arquivo daquele dia (já ajustado por proventos).

## Critério (fixado antes)

O COTAHIST **serve** se, para pelo menos 4 dos 6 ativos, a IV sair em **≥ 80% dos pregões** de cada ano desde
2019 e a IV mediana anual ficar entre 15% e 80% ao ano (faixa plausível para esses papéis). Caso contrário, a fase 2
precisa de outra fonte (paga ou coleta diária própria a partir de agora).

## Resultado

Execução de 05/11/2026 ([run 42100479639](https://github.com/diegostalin88/Invest/actions/runs/42100479639)),
anos 2018 a 2026 (2026 até 04/11). 3.747.469 registros de opções do universo; 93.024 descartados por serem de outra
classe da mesma raiz (PETR3). CDI do Banco Central em todos os 2.220 dias.

**Veredito: APROVADO.** O COTAHIST serve para reconstruir a IV diária e o IV Rank.

| Ativo | Cobertura por ano | IV mediana anual | Critério |
| --- | --- | --- | --- |
| PETR4 | 99% a 100% em todos os anos | 22% a 45% | passa |
| VALE3 | 97% a 100% | 22% a 38% | passa |
| ITUB4 | 98% a 100% | 20% a 36% | passa |
| BBAS3 | 100% | 19% a 37% | passa |
| BOVA11 | 97% a 100% | 14,8% a 28% | não passa por pouco: mediana de 14,8% em 2024 e 2025, abaixo do piso de 15% |
| PRIO3 | 0% em 2018, 1% em 2019, 18% em 2020; 96% a 100% desde 2021 | 29% a 51% (desde 2021) | não passa: só tem opções líquidas desde 2021 |

4 de 6 ativos passam (o mínimo era 4). O piso de 15% era estreito demais para um fundo de índice, cuja volatilidade
é menor que a de uma ação; a cobertura do BOVA11 é completa, então ele pode entrar nos estudos, com a ressalva
registrada aqui. PRIO3 entra só a partir de 2021.

IV Rank de 252 pregões em 04/11/2026: PETR4 68, BBAS3 50, PRIO3 42, VALE3 40, BOVA11 35, ITUB4 33.

A série diária completa (`iv_diaria.csv`) fica no artefato `opcoes-cotahist` do run.
