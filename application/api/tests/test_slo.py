from dataclasses import replace

import pytest

from app.slo import (
    AlertPolicy,
    AlertSeverity,
    AlertState,
    RequestObservation,
    SLODefinition,
    SLOObservations,
    burn_rate_threshold_for_budget,
    calculate_burn_rate,
    evaluate_alert_policy,
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
FAST_BURN = AlertPolicy(
    name="fast_burn",
    severity=AlertSeverity.CRITICAL,
    short_window="5m",
    long_window="1h",
    burn_rate_threshold=14.4,
    budget_fraction=0.02,
    threshold_reference_window="1h",
    slo_names=("availability", "request-success-rate", "latency"),
)
SLOW_BURN = AlertPolicy(
    name="slow_burn",
    severity=AlertSeverity.WARNING,
    short_window="6h",
    long_window="24h",
    burn_rate_threshold=6,
    budget_fraction=0.05,
    threshold_reference_window="6h",
    slo_names=("availability", "request-success-rate", "latency"),
)


def evaluation(definition, eligible, good):
    return evaluate_slo(definition, SLOObservations(eligible, good))


def window_evaluation(definition, window, burn_rate, eligible=1_000_000):
    window_definition = SLODefinition(
        definition.name,
        definition.target,
        window,
        definition.excluded_routes,
        definition.latency_threshold_ms,
    )
    allowed_bad_rate = 1 - definition.target
    bad_events = round(burn_rate * allowed_bad_rate * eligible)
    return evaluate_slo(
        window_definition,
        SLOObservations(eligible, eligible - bad_events),
    )


def evaluate_policy(policy, definition, short_burn, long_burn, previous_state=None):
    return evaluate_alert_policy(
        definition,
        window_evaluation(definition, policy.short_window, short_burn),
        window_evaluation(definition, policy.long_window, long_burn),
        policy,
        previous_state,
    )


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


@pytest.mark.parametrize(
    ("short_burn", "long_burn"),
    [(1, 1), (15, 14), (14, 15)],
)
def test_fast_burn_requires_both_windows_to_exceed_threshold(
    short_burn, long_burn
):
    result = evaluate_policy(FAST_BURN, AVAILABILITY, short_burn, long_burn)

    assert result.state is AlertState.HEALTHY
    assert result.alert is False
    assert result.severity is AlertSeverity.CRITICAL


def test_fast_burn_fires_with_both_windows_above_threshold():
    result = evaluate_policy(FAST_BURN, AVAILABILITY, 15, 16)

    assert result.state is AlertState.FIRING
    assert result.alert is True
    assert result.policy == "fast_burn"
    assert result.slo_name == "availability"
    assert result.short_window == "5m"
    assert result.long_window == "1h"
    assert result.short_burn_rate == pytest.approx(15)
    assert result.long_burn_rate == pytest.approx(16)
    assert result.burn_rate_threshold == pytest.approx(14.4)
    assert result.slo_target == 0.999
    assert result.allowed_bad_rate == pytest.approx(0.001)
    assert result.long_window_bad_events > result.long_window_allowed_bad_events
    assert result.long_window_projected_budget_consumption_percent == pytest.approx(
        16 / 720 * 100
    )
    assert "both required windows exceed" in result.reason


def test_fast_burn_exactly_at_threshold_does_not_fire():
    result = evaluate_policy(FAST_BURN, AVAILABILITY, 14.4, 14.4)

    assert result.state is AlertState.HEALTHY
    assert result.alert is False


def test_fast_burn_supports_very_high_burn_rates():
    result = evaluate_policy(FAST_BURN, AVAILABILITY, 500, 600)

    assert result.state is AlertState.FIRING
    assert result.short_burn_rate == pytest.approx(500)
    assert result.long_burn_rate == pytest.approx(600)


@pytest.mark.parametrize(
    ("short_burn", "long_burn"),
    [(1, 1), (7, 5), (5, 7)],
)
def test_slow_burn_requires_both_windows_to_exceed_threshold(
    short_burn, long_burn
):
    result = evaluate_policy(SLOW_BURN, AVAILABILITY, short_burn, long_burn)

    assert result.state is AlertState.HEALTHY
    assert result.alert is False
    assert result.severity is AlertSeverity.WARNING


def test_slow_burn_fires_as_warning_when_both_windows_exceed_threshold():
    result = evaluate_policy(SLOW_BURN, AVAILABILITY, 8, 9)

    assert result.state is AlertState.FIRING
    assert result.alert is True
    assert result.policy == "slow_burn"
    assert result.severity is AlertSeverity.WARNING
    assert result.short_window == "6h"
    assert result.long_window == "24h"
    assert result.burn_rate_threshold == pytest.approx(6)
    assert result.long_window_projected_budget_consumption_percent == pytest.approx(
        9 * 24 / 720 * 100
    )


def test_no_data_is_neither_healthy_nor_firing():
    no_data_short = evaluate_slo(
        SLODefinition("availability", 0.999, "5m"),
        SLOObservations(0, 0),
    )
    no_data_long = evaluate_slo(
        SLODefinition("availability", 0.999, "1h"),
        SLOObservations(0, 0),
    )
    result = evaluate_alert_policy(
        AVAILABILITY,
        no_data_short,
        no_data_long,
        FAST_BURN,
    )

    assert no_data_short.burn_rate is None
    assert no_data_long.burn_rate is None
    assert result.state is AlertState.NO_DATA
    assert result.alert is None
    assert result.recovered is False
    assert result.long_window_projected_budget_consumption_percent is None
    assert "insufficient eligible events" in result.reason


def test_no_data_does_not_claim_recovery_from_a_firing_state():
    no_data_short = evaluate_slo(
        SLODefinition("availability", 0.999, "5m"),
        SLOObservations(0, 0),
    )
    no_data_long = evaluate_slo(
        SLODefinition("availability", 0.999, "1h"),
        SLOObservations(0, 0),
    )
    result = evaluate_alert_policy(
        AVAILABILITY,
        no_data_short,
        no_data_long,
        FAST_BURN,
        previous_state=AlertState.FIRING,
    )

    assert result.state is AlertState.NO_DATA
    assert result.alert is None
    assert result.recovered is False


@pytest.mark.parametrize(
    ("short_eligible", "long_eligible"),
    [(0, 1000), (1000, 0)],
)
def test_data_missing_from_either_window_produces_no_data(
    short_eligible, long_eligible
):
    short = evaluate_slo(
        SLODefinition("availability", 0.999, "5m"),
        SLOObservations(short_eligible, short_eligible),
    )
    long = evaluate_slo(
        SLODefinition("availability", 0.999, "1h"),
        SLOObservations(long_eligible, long_eligible),
    )

    result = evaluate_alert_policy(AVAILABILITY, short, long, FAST_BURN)

    assert result.state is AlertState.NO_DATA
    assert result.alert is None


def test_zero_allowed_error_rate_is_undefined_not_no_data_or_healthy():
    perfect_slo = SLODefinition("availability", 1, "30d")
    short = evaluate_slo(
        SLODefinition("availability", 1, "5m"),
        SLOObservations(1000, 1000),
    )
    long = evaluate_slo(
        SLODefinition("availability", 1, "1h"),
        SLOObservations(1000, 1000),
    )
    policy = AlertPolicy(
        name="fast_burn",
        severity=AlertSeverity.CRITICAL,
        short_window="5m",
        long_window="1h",
        burn_rate_threshold=14.4,
        budget_fraction=0.02,
        threshold_reference_window="1h",
        slo_names=("availability",),
    )

    result = evaluate_alert_policy(perfect_slo, short, long, policy)

    assert result.state is AlertState.UNDEFINED
    assert result.alert is None
    assert "allows no bad events" in result.reason


def test_alert_reports_recovery_when_both_windows_return_below_threshold():
    result = evaluate_policy(
        FAST_BURN,
        AVAILABILITY,
        1,
        1,
        previous_state=AlertState.FIRING,
    )

    assert result.state is AlertState.HEALTHY
    assert result.alert is False
    assert result.recovered is True
    assert result.reason.startswith("recovered:")


@pytest.mark.parametrize("definition", [AVAILABILITY, SUCCESS_RATE, LATENCY])
def test_alert_policies_can_evaluate_each_existing_slo(definition):
    result = evaluate_policy(FAST_BURN, definition, 15, 16)

    assert result.slo_name == definition.name
    assert result.slo_target == definition.target
    assert result.state is AlertState.FIRING


def test_availability_and_success_rate_share_alert_decision_without_duplicates():
    availability = evaluate_policy(FAST_BURN, AVAILABILITY, 15, 16)
    success_rate = evaluate_policy(FAST_BURN, SUCCESS_RATE, 15, 16)

    assert availability.state is success_rate.state
    assert availability.short_burn_rate == success_rate.short_burn_rate
    assert availability.long_burn_rate == success_rate.long_burn_rate


def test_threshold_is_derived_from_error_budget_fraction_and_reference_window():
    assert burn_rate_threshold_for_budget(AVAILABILITY, 0.02, "1h") == pytest.approx(
        14.4
    )
    assert burn_rate_threshold_for_budget(AVAILABILITY, 0.05, "6h") == pytest.approx(
        6
    )


def test_policy_threshold_must_match_error_budget_basis():
    mismatched_policy = AlertPolicy(
        name="fast_burn",
        severity=AlertSeverity.CRITICAL,
        short_window="5m",
        long_window="1h",
        burn_rate_threshold=10,
        budget_fraction=0.02,
        threshold_reference_window="1h",
        slo_names=("availability",),
    )

    with pytest.raises(ValueError, match="does not match its error-budget basis"):
        evaluate_policy(mismatched_policy, AVAILABILITY, 20, 20)


def test_policy_rejects_slo_not_in_its_mapping():
    policy = AlertPolicy(
        name="availability-only",
        severity=AlertSeverity.CRITICAL,
        short_window="5m",
        long_window="1h",
        burn_rate_threshold=14.4,
        budget_fraction=0.02,
        threshold_reference_window="1h",
        slo_names=("availability",),
    )

    with pytest.raises(ValueError, match="does not apply"):
        evaluate_policy(policy, LATENCY, 20, 20)


def test_policy_rejects_window_evaluation_from_another_slo():
    wrong_slo = window_evaluation(SUCCESS_RATE, "5m", 15)
    long_slo = window_evaluation(AVAILABILITY, "1h", 15)

    with pytest.raises(ValueError, match="does not match the configured SLO"):
        evaluate_alert_policy(AVAILABILITY, wrong_slo, long_slo, FAST_BURN)


def test_policy_rejects_burn_rate_inconsistent_with_slo_observations():
    short = replace(window_evaluation(AVAILABILITY, "5m", 15), burn_rate=2)
    long = window_evaluation(AVAILABILITY, "1h", 15)

    with pytest.raises(ValueError, match="burn rate is inconsistent"):
        evaluate_alert_policy(AVAILABILITY, short, long, FAST_BURN)
