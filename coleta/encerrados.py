"""Papéis da carteira que deixaram de negociar (25/11/2026, achados do Consultor).

Eles continuam na coleta da carteira (estão no histórico do Diego e entram na rentabilidade dos períodos em que ele
os teve), mas não são "falhas": o Yahoo não tem mais o código. Datas = último pregão no COTAHIST da B3.
"""
ENCERRADOS = {
    'BTOW3': {'ultimaData': '2021-07-16', 'sucessor': 'AMER3', 'motivo': 'incorporada pela Americanas (AMER3) em 19/07/2021'},
    'LAME4': {'ultimaData': '2022-01-21', 'sucessor': 'AMER3', 'motivo': 'incorporada pela Americanas (AMER3) em 2022'},
    'VVAR3': {'ultimaData': '2021-08-13', 'sucessor': 'BHIA3', 'motivo': 'virou VIIA3 (16/08/2021) e depois BHIA3 (20/09/2023)'},
    'AZUL4': {'ultimaData': '2025-05-28', 'sucessor': 'AZUL3', 'motivo': 'reestruturação da Azul; negocia como AZUL3 (2026)'},
    'NGRD3': {'ultimaData': '2026-07-13', 'sucessor': None, 'motivo': 'deslistada em 13/07/2026'},
    'STBP3': {'ultimaData': '2025-10-02', 'sucessor': None, 'motivo': 'deslistada em 02/10/2025'},
    'BIYW39': {'ultimaData': '2022-10-07', 'sucessor': None, 'motivo': 'BDR encerrado em 07/10/2022'},
}


def separar(falhas):
    """(encerrados, falhas de verdade) a partir da lista de códigos que o Yahoo não devolveu."""
    enc = [{'papel': t, **ENCERRADOS[t]} for t in falhas if t in ENCERRADOS]
    return enc, [t for t in falhas if t not in ENCERRADOS]
