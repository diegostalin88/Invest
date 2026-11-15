import json
from datetime import date

import pareceres

CSV = """data,papel,mercado,tese,confianca,preco_ref,indice,indice_ref,mudaria_opiniao,data_agente_json
2026-11-16,PETR4,br,a favor da tese,média,30,BOVA11,100,queda do petróleo,2026-11-13
16/11/2026,VALE3,br,Contra a tese,baixa,"60,0",BOVA11,100,,2026-11-13
2026-11-17,NVDA,us,neutro,alta,200,SPY,500,,2026-11-14
,SEMDATA,br,a favor,,1,,1,,
"""

AG = {'mercados': {'br': {'termometro': {'ult': 110.0}, 'papeis': {'PETR4': {'p': 36.0}, 'VALE3': {'p': 63.0}}},
                   'us': {'termometro': {'ult': 500.0}, 'papeis': {'NVDA': {'p': 210.0}}}}}


def test_le_csv_com_formatos_variados(tmp_path):
    p = tmp_path / 'p.csv'
    p.write_text(CSV, encoding='utf-8')
    l = pareceres.ler_csv(str(p))
    assert [x['papel'] for x in l] == ['PETR4', 'VALE3', 'NVDA']        # linha sem data descartada
    assert l[1]['data'] == '2026-11-16' and l[1]['precoRef'] == 60.0 and l[1]['tese'] == 'contra'
    assert l[0]['tese'] == 'a favor' and l[2]['tese'] == 'neutro'


def test_placar_excesso_e_acerto(tmp_path):
    p = tmp_path / 'p.csv'
    p.write_text(CSV, encoding='utf-8')
    o = pareceres.montar(pareceres.ler_csv(str(p)), AG, hoje=date(2026, 11, 20))
    por = {x['papel']: x for x in o['recentes']}
    assert por['PETR4']['excesso'] == 0.1 and por['PETR4']['acertou'] is True     # +20% contra +10% do índice
    assert por['VALE3']['excesso'] == -0.05 and por['VALE3']['acertou'] is True   # contra a tese e ficou atrás
    assert 'acertou' not in por['NVDA']                                           # neutro não conta
    assert o['placar']['comTese'] == 2 and o['placar']['acertoAteHoje'] == 1.0
    assert o['placar']['podeConcluir'] is False and o['placar']['maduros120'] == 0
    assert o['ultimaData'] == '2026-11-17' and [x['papel'] for x in o['ultimos']] == ['NVDA']


def test_main_sem_planilha_e_com(tmp_path):
    (tmp_path / 'data').mkdir()
    assert pareceres.main(['x', str(tmp_path / 'nao.csv'), str(tmp_path / 'data')]) == 2
    (tmp_path / 'p.csv').write_text(CSV, encoding='utf-8')
    (tmp_path / 'data' / 'agente.json').write_text(json.dumps(AG))
    assert pareceres.main(['x', str(tmp_path / 'p.csv'), str(tmp_path / 'data')]) == 0
    assert json.load(open(tmp_path / 'data' / 'pareceres.json'))['placar']['pareceres'] == 3
