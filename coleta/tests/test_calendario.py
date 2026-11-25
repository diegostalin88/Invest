from datetime import date

from calendario import eh_pregao, feriados, pascoa, pregoes_entre


def test_pascoa():
    assert pascoa(2024) == date(2024, 3, 31)
    assert pascoa(2026) == date(2026, 4, 5)
    assert pascoa(2027) == date(2027, 3, 28)


def test_b3_2026():
    esperado = {date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3), date(2026, 4, 21),
                date(2026, 5, 1), date(2026, 6, 4), date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2),
                date(2026, 11, 20), date(2026, 12, 24), date(2026, 12, 25), date(2026, 12, 31)}
    uteis = {d for d in feriados('br', 2026) if d.weekday() < 5}
    assert uteis == esperado
    assert eh_pregao(date(2026, 2, 18), 'br')       # Quarta-feira de Cinzas tem pregão
    assert eh_pregao(date(2026, 1, 26), 'br')


def test_nyse_2026():
    esperado = {date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
                date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25)}
    assert set(feriados('us', 2026)) == esperado
    assert date(2027, 12, 31) not in feriados('us', 2027)   # Ano Novo de 2028 no sábado não antecipa
    assert date(2027, 12, 24) in feriados('us', 2027)       # Natal no sábado vai para sexta


def test_pregoes_entre_pula_feriado():
    # sexta 13/11/2026 até segunda 23/11/2026: 16, 17, 18, 19, 23 (20/11 é feriado na B3, não na NYSE)
    assert pregoes_entre('2026-11-13', '2026-11-23', 'br') == 5
    assert pregoes_entre('2026-11-13', '2026-11-23', 'us') == 6
    assert pregoes_entre(date(2026, 11, 13), date(2026, 11, 13)) == 0


def test_dados_velhos_depois_do_feriado():
    import agente
    # último pregão na quinta 19/11, coleta na segunda 23/11: só 1 pregão perdido na B3, não 2
    assert agente.dias_uteis('2026-11-19', date(2026, 11, 23), 'br') == 1
