import pytest

from app.slo import (
    RequestObservation,
    SLODefinition,
    SLOObservations,
    calculate_burn_rate,
    evaluate_slo,
    observe_requests,
)


AVAILABILITY = SLODefinition("availability", 0.999, "30d")
SUCCESS_RATE = SLODefinition("request-success-rate", 0.999, "30d")
LATENCY = SLODefinition(
    "latency",
    0.99,
    "30d",
    latency_threshold_ms=500,
)


def evaluation(definition, eligible, good):
    return evaluate_slo(definition, SLOObservations(eligible, good))


@pytest.mark.parametrize(
    ("eligible", "good", "expected_sli", "compliant"),
    [
        (1000, 1000, 1.0, True),
        (1000, 999, 0.999, True),
        (1000, 998, 0.998, False),
        (100, 99, 0.99, False),
    ],
)
def test_availability_sli_and_slo_compliance(
    eligible, good, expected_sli, compliant
):
    result = evaluation(AVAILABILITY, eligible, good)

    assert result.sli_value == pytest.approx(expected_sli)
    assert result.slo_compliant is compliant
    assert result.slo_target == 0.999


def test_zero_eligible_requests_have_no_compliance_or_rates():
    result = evaluation(AVAILABILITY, 0, 0)

    assert result.sli_value is None
    assert result.slo_compliant is None
    assert result.observed_bad_rate is None
    assert result.consumed_error_budget is None
    assert result.remaining_error_budget_percent is None
    assert result.burn_rate is None
    assert result.error_budget == 0


def test_all_requests_failing():
    result = evaluation(AVAILABILITY, 10, 0)

    assert result.bad_events == 10
    assert result.sli_value == 0
    assert result.slo_compliant is False


def test_mixed_client_and_server_errors_count_only_server_errors_as_bad():
    observations = observe_requests(
        AVAILABILITY,
        [
            RequestObservation("/api/v1/items", 200, 0.1),
            RequestObservation("/api/v1/items", 404, 0.1),
            RequestObservation("/api/v1/items", 500, 0.1),
        ],
    )

    assert observations.eligible_events == 3
    assert observations.good_events == 2
    assert observations.bad_events == 1


def test_success_rate_sli_is_intentionally_aligned_with_availability():
    requests = [
        RequestObservation("/api/v1/items", 200, 0.1),
        RequestObservation("/api/v1/items", 404, 0.1),
        RequestObservation("/api/v1/items", 500, 0.1),
    ]

    assert observe_requests(AVAILABILITY, requests) == observe_requests(
        SUCCESS_RATE, requests
    )


def test_health_requests_are_excluded_from_request_slo():
    observations = observe_requests(
        AVAILABILITY,
        [
            RequestObservation("/health", 500, 1),
            RequestObservation("/api/v1/items", 200, 0.1),
        ],
    )

    assert observations == SLOObservations(eligible_events=1, good_events=1)


@pytest.mark.parametrize(
    ("definition", "eligible", "good", "allowed_rate"),
    [
        (AVAILABILITY, 1_000_000, 999_000, 0.001),
        (SLODefinition("99-percent", 0.99, "30d"), 1000, 990, 0.01),
    ],
)
def test_error_budget_math(definition, eligible, good, allowed_rate):
    result = evaluation(definition, eligible, good)

    assert result.allowed_bad_rate == pytest.approx(allowed_rate)
    assert result.allowed_bad_events == pytest.approx(eligible * allowed_rate)
    assert result.error_budget == result.allowed_bad_events


def test_zero_failures_consume_no_budget():
    result = evaluation(AVAILABILITY, 1000, 1000)

    assert result.consumed_error_budget == 0
    assert result.remaining_error_budget == pytest.approx(1)
    assert result.remaining_error_budget_percent == pytest.approx(100)


def test_partial_error_budget_consumption():
    result = evaluation(AVAILABILITY, 1_000_000, 999_750)

    assert result.error_budget == pytest.approx(1000)
    assert result.consumed_error_budget == pytest.approx(0.25)
    assert result.remaining_error_budget == pytest.approx(750)
    assert result.remaining_error_budget_percent == pytest.approx(75)


def test_exactly_exhausted_error_budget():
    result = evaluation(AVAILABILITY, 1_000_000, 999_000)

    assert result.consumed_error_budget == pytest.approx(1)
    assert result.remaining_error_budget == 0
    assert result.remaining_error_budget_percent == 0


def test_error_budget_exceeded_is_not_capped_as_consumed():
    result = evaluation(AVAILABILITY, 1_000_000, 998_000)

    assert result.consumed_error_budget == pytest.approx(2)
    assert result.remaining_error_budget == 0
    assert result.remaining_error_budget_percent == 0


def test_zero_eligible_events_have_no_defined_budget_consumption():
    result = evaluation(AVAILABILITY, 0, 0)

    assert result.error_budget == 0
    assert result.consumed_error_budget is None
    assert result.remaining_error_budget_percent is None


@pytest.mark.parametrize(
    ("observed_rate", "allowed_rate", "expected_burn_rate"),
    [
        (0, 0.001, 0),
        (0.001, 0.001, 1),
        (0.005, 0.001, 5),
        (0.5, 0.001, 500),
    ],
)
def test_burn_rate(observed_rate, allowed_rate, expected_burn_rate):
    assert calculate_burn_rate(observed_rate, allowed_rate) == pytest.approx(
        expected_burn_rate
    )


def test_zero_allowed_bad_rate_has_no_burn_rate():
    with pytest.raises(ValueError, match="allowed bad rate is zero"):
        calculate_burn_rate(0, 0)

    perfect_slo = SLODefinition("perfection", 1, "30d")
    assert evaluation(perfect_slo, 100, 100).burn_rate is None


def test_latency_requests_at_or_under_threshold_are_good():
    observations = observe_requests(
        LATENCY,
        [
            RequestObservation("/api/v1/items", 200, 0.499),
            RequestObservation("/api/v1/items", 200, 0.5),
        ],
    )

    assert observations == SLOObservations(eligible_events=2, good_events=2)


def test_latency_above_threshold_is_bad():
    observations = observe_requests(
        LATENCY,
        [RequestObservation("/api/v1/items", 200, 0.501)],
    )

    assert observations == SLOObservations(eligible_events=1, good_events=0)


def test_latency_counts_slow_and_failed_requests_as_not_good():
    observations = observe_requests(
        LATENCY,
        [
            RequestObservation("/api/v1/items", 200, 0.7),
            RequestObservation("/api/v1/items", 500, 0.1),
            RequestObservation("/api/v1/items", 404, 0.1),
        ],
    )

    assert observations.eligible_events == 3
    assert observations.good_events == 1
    assert observations.bad_events == 2


def test_latency_excludes_health_requests():
    observations = observe_requests(
        LATENCY,
        [
            RequestObservation("/health", 200, 10),
            RequestObservation("/api/v1/items", 200, 0.1),
        ],
    )

    assert observations == SLOObservations(eligible_events=1, good_events=1)


def test_engine_accepts_arbitrary_windows_without_tenant_identifiers():
    five_minute_slo = SLODefinition("availability", 0.999, "5m")
    one_hour_slo = SLODefinition("availability", 0.999, "1h")
    six_hour_slo = SLODefinition("availability", 0.999, "6h")
    daily_slo = SLODefinition("availability", 0.999, "24h")

    results = [
        evaluate_slo(definition, SLOObservations(1000, 999))
        for definition in (five_minute_slo, one_hour_slo, six_hour_slo, daily_slo)
    ]

    assert [result.window for result in results] == ["5m", "1h", "6h", "24h"]
    assert all(result.sli_value == pytest.approx(0.999) for result in results)
    with pytest.raises(TypeError):
        evaluate_slo(
            five_minute_slo,
            SLOObservations(1000, 999),
            tenant_id="unvalidated-client-input",
        )


def test_calculations_are_deterministic():
    observations = SLOObservations(1000, 995)

    assert evaluate_slo(AVAILABILITY, observations) == evaluate_slo(
        AVAILABILITY, observations
    )


@pytest.mark.parametrize(
    ("eligible", "good"),
    [(-1, 0), (1, -1), (1, 2), (True, 1), (1, False), (1.5, 1)],
)
def test_invalid_observation_counts_are_rejected(eligible, good):
    with pytest.raises(ValueError):
        SLOObservations(eligible, good)
