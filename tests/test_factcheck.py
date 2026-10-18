from ecom.ai.factcheck import CheckResult, check_point, extract_numbers

FACTS = {
    "revenue": {"id": "revenue", "value": 82726.4, "unit": "currency"},
    "mom": {"id": "mom", "value": -0.0612, "unit": "pct"},
    "review": {"id": "review", "value": 4.26, "unit": "score"},
    "orders": {"id": "orders", "value": 374.0, "unit": "count"},
}


def run(text, ids):
    r = CheckResult()
    check_point(text, ids, FACTS, r)
    return r


def test_extracts_currency_percent_and_scaled_numbers():
    vals = [(m.value, m.is_pct) for m in extract_numbers("R$ 82.7k revenue, down 6.1%, 1,234 orders")]
    assert vals == [(82700.0, False), (6.1, True), (1234.0, False)]


def test_ignores_years_and_small_counts():
    assert extract_numbers("In 2018 the top 3 categories") == []


def test_accepts_rounded_and_scaled_values():
    assert run("Revenue was R$ 82.7k, from 374 orders", ["revenue", "orders"]).passed
    assert run("Revenue was R$ 82,726", ["revenue"]).passed


def test_accepts_magnitude_of_negative_change():
    assert run("Revenue fell 6.1% month on month", ["mom"]).passed


def test_flags_number_not_in_cited_facts():
    r = run("Revenue grew 12.5% to R$ 82.7k", ["revenue", "mom"])
    assert not r.passed and any("12.5%" in u for u in r.unverified)


def test_flags_number_matching_an_uncited_fact():
    assert not run("Average review was 4.26", ["revenue"]).passed


def test_percent_never_matches_a_plain_number():
    assert not run("Reviews were 4.26%", ["review"]).passed


def test_flags_unknown_fact_ids():
    assert run("All good", ["made_up"]).unknown_fact_ids == ["made_up"]
