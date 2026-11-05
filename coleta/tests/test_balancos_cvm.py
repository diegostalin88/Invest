"""Balanços do Brasil (CVM) com arquivos de mentira no mesmo formato dos dados abertos (sem rede)."""
import io
import json
import zipfile
from datetime import date

import balancos_cvm as bc

CNPJ = '33.000.167/0001-01'
CAB_DRE = 'CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA'
CAB_BP = 'CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA'
CAB_IDX = 'CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC'


def _dre(ref, ini, fim, rev, ni, versao=1, ordem='ÚLTIMO'):
    base = f'{CNPJ};{ref};{versao};PETROBRAS;009512;DF Consolidado - Demonstração do Resultado;REAL;MIL;{ordem};{ini};{fim}'
    return [f'{base};3.01;Receita de Venda de Bens e/ou Serviços;{rev};S', f'{base};3.03;Resultado Bruto;{rev / 2};S',
            f'{base};3.09;Resultado Líquido das Operações Continuadas;{ni};S', f'{base};3.11;Lucro/Prejuízo Consolidado do Período;{ni};S']


def _bp(ref, ativo, pl):
    a = f'{CNPJ};{ref};1;PETROBRAS;009512;DF Consolidado - Balanço Patrimonial Ativo;REAL;MIL;ÚLTIMO;{ref}'
    p = f'{CNPJ};{ref};1;PETROBRAS;009512;DF Consolidado - Balanço Patrimonial Passivo;REAL;MIL;ÚLTIMO;{ref}'
    return [f'{a};1;Ativo Total;{ativo};S'], [f'{p};2;Passivo Total;{ativo};S', f'{p};2.03;Patrimônio Líquido Consolidado;{pl};S']


def _zip(arqs):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for nome, linhas in arqs.items():
            z.writestr(nome, '\n'.join(linhas).encode('latin-1'))
    return b.getvalue()


def _itr():
    dre = [CAB_DRE]
    dre += _dre('2025-03-31', '2025-01-01', '2025-03-31', 100, 10)
    dre += _dre('2025-03-31', '2024-01-01', '2024-03-31', 90, 9, ordem='PENÚLTIMO')   # ano anterior: ignorado
    dre += _dre('2025-06-30', '2025-04-01', '2025-06-30', 110, 12) + _dre('2025-06-30', '2025-01-01', '2025-06-30', 210, 22)
    dre += _dre('2025-09-30', '2025-07-01', '2025-09-30', 120, 5, versao=1) + _dre('2025-09-30', '2025-07-01', '2025-09-30', 120, 15, versao=2)
    dre += _dre('2025-09-30', '2025-01-01', '2025-09-30', 330, 37, versao=2)
    bpa, bpp = [CAB_BP], [CAB_BP]
    for ref in ('2025-03-31', '2025-06-30', '2025-09-30'):
        a, p = _bp(ref, 1000, 400)
        bpa += a
        bpp += p
    idx = [CAB_IDX, f'{CNPJ};2025-03-31;1;PETROBRAS;009512;ITR;1;2025-05-12;x', f'{CNPJ};2025-06-30;1;PETROBRAS;009512;ITR;2;2025-08-07;x',
           f'{CNPJ};2025-09-30;1;PETROBRAS;009512;ITR;3;2025-11-06;x', f'{CNPJ};2025-09-30;2;PETROBRAS;009512;ITR;4;2025-11-20;x']
    return _zip({'itr_cia_aberta_2025.csv': idx, 'itr_cia_aberta_DRE_con_2025.csv': dre,
                 'itr_cia_aberta_BPA_con_2025.csv': bpa, 'itr_cia_aberta_BPP_con_2025.csv': bpp})


def _dfp():
    dre = [CAB_DRE] + _dre('2025-12-31', '2025-01-01', '2025-12-31', 460, 50)
    a, p = _bp('2025-12-31', 1100, 450)
    return _zip({'dfp_cia_aberta_2025.csv': [CAB_IDX, f'{CNPJ};2025-12-31;1;PETROBRAS;009512;DFP;9;2026-02-26;x'],
                 'dfp_cia_aberta_DRE_con_2025.csv': dre, 'dfp_cia_aberta_BPA_con_2025.csv': [CAB_BP] + a, 'dfp_cia_aberta_BPP_con_2025.csv': [CAB_BP] + p})


def _fca():
    cab = 'CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Valor_Mobiliario;Sigla_Classe_Acao_Preferencial;Classe_Acao_Preferencial;Codigo_Negociacao;Composicao_BDR_Unit;Mercado'
    return _zip({'fca_cia_aberta_valor_mobiliario_2026.csv': [cab, f'{CNPJ};2026-01-01;1;1;PETROBRAS;Ações Preferenciais;PN;;PETR4;;Bolsa',
                                                             f'{CNPJ};2026-01-01;1;1;PETROBRAS;Ações Ordinárias;;;PETR3;;Bolsa']})


def test_trimestres_quarto_trimestre_e_versao(tmp_path):
    acc = bc.Acumulador({CNPJ})
    acc.ler_zip(_itr(), 'ITR', 2025)
    acc.ler_zip(_dfp(), 'DFP', 2025)
    t, b = acc.empresa(CNPJ)
    assert [x[0] for x in t] == ['2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31']
    assert t[0] == ['2025-03-31', '2025-05-12', 100000, 10000, None, 50000]          # MIL × 1.000
    assert t[2][3] == 15000 and t[2][1] == '2025-11-06'                                # números da versão 2, data da 1ª entrega
    assert t[3][2] == (460 - 330) * 1000 and t[3][3] == (50 - 37) * 1000 and t[3][1] == '2026-02-26'   # 4º tri = ano − 9 meses
    assert b[0] == ['2025-03-31', 1000000, 400000, 1000000] and b[-1][0] == '2025-12-31'


def test_main_grava_para_os_tickers_do_app(tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps({'arquivosPrecos': ['p.json']}))
    (tmp_path / 'p.json').write_text(json.dumps({'formato': 'colunar-v1', 'ativos': {'PETR4': {}, 'VALE3': {}}}))
    arquivos = {'fca_cia_aberta_2026.zip': _fca(), 'itr_cia_aberta_2025.zip': _itr(), 'dfp_cia_aberta_2025.zip': _dfp()}
    pedidos = []

    def falso(url):
        pedidos.append(url)
        return arquivos.get(url.rsplit('/', 1)[1])
    assert bc.main([str(tmp_path), '--anos', '1'], baixar=falso, hoje=date(2026, 11, 5)) == 0
    out = json.loads((tmp_path / 'balancos.json').read_text())
    assert set(out['ativos']) == {'PETR4'} and len(out['ativos']['PETR4']['t']) == 4
    assert json.loads((tmp_path / 'manifest.json').read_text())['arquivoBalancos'] == 'balancos.json'
    assert any('ITR/DADOS/itr_cia_aberta_2026.zip' in u for u in pedidos)
