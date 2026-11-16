from aerosafe.nlp.triage import analyze


def test_triage_signals_explain_rank_and_relative_share():
    result = analyze("Hydraulic pressure drop during landing gear retraction")
    assert result.signals
    assert [signal["rank"] for signal in result.signals] == list(range(1, len(result.signals) + 1))
    assert sum(signal["relative_match_share"] for signal in result.signals) == 1
    assert all(signal["matched_terms"] for signal in result.signals)
    assert all("probability" not in signal for signal in result.signals)


def test_unmatched_description_has_no_ranked_signal():
    result = analyze("intermittent issue")
    assert result.ata == []
    assert result.signals == []
