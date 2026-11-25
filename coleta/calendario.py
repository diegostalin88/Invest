"""Calendário de pregões da B3 e da NYSE (16/11/2026), só com a biblioteca padrão.

Antes, "dia útil" era segunda a sexta; feriado contava como pregão. Isso acendia o alerta de dados velhos depois de
feriado e esticava as janelas de 20/60/120 pregões do placar do Consultor. Bibliotecas prontas (exchange_calendars,
pandas_market_calendars) puxam pandas, pesado para a VM de 1 GB; as regras abaixo cabem em poucas linhas.

B3: 1/1, Carnaval (segunda e terça), Sexta-feira Santa, 21/4, 1/5, Corpus Christi, 7/9, 12/10, 2/11, 15/11,
    20/11 (feriado nacional desde 2024), 24/12, 25/12 e 31/12. A Quarta-feira de Cinzas tem pregão (abre à tarde).
    Os feriados municipais de São Paulo (25/1 e 9/7) têm pregão desde 2022.
NYSE: Ano Novo, Martin Luther King, Presidents' Day, Sexta-feira Santa, Memorial Day, Juneteenth (desde 2022),
    4 de Julho, Labor Day, Thanksgiving e Natal; sábado passa para sexta e domingo para segunda (Ano Novo no sábado
    não é antecipado). Fechamentos extraordinários (luto oficial, por exemplo) não entram.
"""
from datetime import date, timedelta


def pascoa(ano):
    """Domingo de Páscoa (algoritmo de Meeus/Butcher, calendário gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def _enesimo(ano, mes, dia_semana, n):
    """n-ésimo dia da semana do mês (n = -1: o último). dia_semana: 0 = segunda."""
    if n > 0:
        d = date(ano, mes, 1)
        d += timedelta(days=(dia_semana - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(ano, mes + 1, 1) - timedelta(days=1) if mes < 12 else date(ano, 12, 31)
    return d - timedelta(days=(d.weekday() - dia_semana) % 7)


def _observado(d, antecipa_sabado=True):
    if d.weekday() == 5:
        return d - timedelta(days=1) if antecipa_sabado else None
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


_CACHE = {}


def feriados(mercado, ano):
    chave = (mercado, ano)
    if chave in _CACHE:
        return _CACHE[chave]
    p = pascoa(ano)
    if mercado == 'br':
        fs = {date(ano, 1, 1), p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2),
              date(ano, 4, 21), date(ano, 5, 1), p + timedelta(days=60), date(ano, 9, 7), date(ano, 10, 12),
              date(ano, 11, 2), date(ano, 11, 15), date(ano, 12, 24), date(ano, 12, 25), date(ano, 12, 31)}
        if ano >= 2024:
            fs.add(date(ano, 11, 20))
        if ano < 2022:
            fs |= {date(ano, 1, 25), date(ano, 7, 9)}
    else:
        fs = {_observado(date(ano, 1, 1), antecipa_sabado=False), _enesimo(ano, 1, 0, 3), _enesimo(ano, 2, 0, 3),
              p - timedelta(days=2), _enesimo(ano, 5, 0, -1), _observado(date(ano, 7, 4)), _enesimo(ano, 9, 0, 1),
              _enesimo(ano, 11, 3, 4), _observado(date(ano, 12, 25))}
        if ano >= 2022:
            fs.add(_observado(date(ano, 6, 19)))
        fs.discard(None)
    _CACHE[chave] = frozenset(fs)
    return _CACHE[chave]


def eh_pregao(d, mercado='br'):
    return d.weekday() < 5 and d not in feriados(mercado, d.year)


def pregoes_entre(de, ate, mercado='br'):
    """Pregões depois de `de` até `ate` (inclusive). Aceita date ou 'AAAA-MM-DD'."""
    d0 = date.fromisoformat(de) if isinstance(de, str) else de
    d1 = date.fromisoformat(ate) if isinstance(ate, str) else ate
    return sum(1 for k in range(1, (d1 - d0).days + 1) if eh_pregao(d0 + timedelta(days=k), mercado))
