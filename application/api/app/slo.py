from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import math
import re
from typing import Iterable


_WINDOW_PATTERN = re.compile(r"^[1-9]\d*[smhd]$")
_COMPLIANCE_TOLERANCE = 1e-12
_WINDOW_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"


class AlertState(str, Enum):
    NO_DATA = "no_data"
    UNDEFINED = "undefined"
    HEALTHY = "healthy"
    FIRING = "firing"


@dataclass(frozen=True)
class AlertPolicy:
    name: str
    severity: AlertSeverity
    short_window: str
    long_window: str
    burn_rate_threshold: float
    budget_fraction: float
    threshold_reference_window: str
    slo_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("alert policy name must not be empty")
        if not isinstance(self.severity, AlertSeverity):
            raise ValueError("alert severity must be critical or warning")
        _duration_seconds(self.short_window)
        _duration_seconds(self.long_window)
        _duration_seconds(self.threshold_reference_window)
        if _duration_seconds(self.short_window) >= _duration_seconds(self.long_window):
            raise ValueError("short window must be shorter than long window")
        if (
            isinstance(self.burn_rate_threshold, bool)
            or not isinstance(self.burn_rate_threshold, (int, float))
            or not math.isfinite(self.burn_rate_threshold)
            or self.burn_rate_threshold <= 0
        ):
            raise ValueError("burn-rate threshold must be a finite positive number")
        if (
            isinstance(self.budget_fraction, bool)
            or not isinstance(self.budget_fraction, (int, float))
            or not math.isfinite(self.budget_fraction)
            or not 0 < self.budget_fraction <= 1
        ):
            raise ValueError("budget fraction must be greater than 0 and at most 1")
        if not self.slo_names or any(
            not isinstance(name, str) or not name.strip() for name in self.slo_names
        ):
            raise ValueError("alert policy must reference at least one SLO name")


@dataclass(frozen=True)
class AlertEvaluation:
    policy: str
    slo_name: str
    severity: AlertSeverity
    state: AlertState
    alert: bool | None
    short_window: str
    long_window: str
    short_burn_rate: float | None
    long_burn_rate: float | None
    burn_rate_threshold: float
    slo_target: float
    allowed_bad_rate: float
    budget_fraction: float
    threshold_reference_window: str
    long_window_eligible_events: int
    long_window_bad_events: int
    long_window_allowed_bad_events: float
    long_window_projected_budget_consumption_percent: float | None
    recovered: bool
    reason: str


def _duration_seconds(window: str) -> int:
    if not isinstance(window, str) or not _WINDOW_PATTERN.fullmatch(window):
        raise ValueError("window must be a positive duration such as 5m or 30d")
    return int(window[:-1]) * _WINDOW_SECONDS[window[-1]]


def burn_rate_threshold_for_budget(
    definition: SLODefinition,
    budget_fraction: float,
    over_window: str,
) -> float:
    if (
        isinstance(budget_fraction, bool)
        or not isinstance(budget_fraction, (int, float))
        or not math.isfinite(budget_fraction)
        or not 0 < budget_fraction <= 1
    ):
        raise ValueError("budget fraction must be greater than 0 and at most 1")
    return (
        budget_fraction
        * _duration_seconds(definition.window)
        / _duration_seconds(over_window)
    )


def evaluate_alert_policy(
    definition: SLODefinition,
    short_window: SLOEvaluation,
    long_window: SLOEvaluation,
    policy: AlertPolicy,
    previous_state: AlertState | None = None,
) -> AlertEvaluation:
    if previous_state is not None and not isinstance(previous_state, AlertState):
        raise ValueError("previous state must be a defined alert state")
    if definition.name not in policy.slo_names:
        raise ValueError(f"policy {policy.name!r} does not apply to {definition.name!r}")
    expected_threshold = burn_rate_threshold_for_budget(
        definition,
        policy.budget_fraction,
        policy.threshold_reference_window,
    )
    if not math.isclose(
        policy.burn_rate_threshold,
        expected_threshold,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "configured burn-rate threshold does not match its error-budget basis"
        )
    for evaluation, expected_window in (
        (short_window, policy.short_window),
        (long_window, policy.long_window),
    ):
        if (
            evaluation.name != definition.name
            or evaluation.slo_target != definition.target
            or not math.isclose(
                evaluation.allowed_bad_rate,
                1 - definition.target,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("window evaluation does not match the configured SLO")
        if evaluation.observed_bad_rate is not None:
            expected_burn_rate = (
                calculate_burn_rate(
                    evaluation.observed_bad_rate,
                    evaluation.allowed_bad_rate,
                )
                if evaluation.allowed_bad_rate > 0
                else None
            )
            burn_rate_mismatch = (
                expected_burn_rate is None and evaluation.burn_rate is not None
            ) or (
                expected_burn_rate is not None
                and (
                    evaluation.burn_rate is None
                    or not math.isclose(
                        evaluation.burn_rate,
                        expected_burn_rate,
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                )
            )
            if burn_rate_mismatch:
                raise ValueError("window burn rate is inconsistent with its SLO")
        if evaluation.window != expected_window:
            raise ValueError(
                f"policy {policy.name!r} requires a {expected_window} evaluation"
            )

    has_observations = (
        short_window.eligible_events > 0 and long_window.eligible_events > 0
    )
    has_data = (
        has_observations
        and short_window.burn_rate is not None
        and long_window.burn_rate is not None
    )
    long_window_projected_consumption = (
        long_window.burn_rate
        * _duration_seconds(policy.long_window)
        / _duration_seconds(definition.window)
        * 100
        if has_data
        else None
    )

    if not has_data:
        alert = None
        recovered = False
        if has_observations:
            state = AlertState.UNDEFINED
            reason = "burn rate is undefined because the SLO allows no bad events"
        else:
            state = AlertState.NO_DATA
            reason = "insufficient eligible events in one or both required windows"
    elif (
        short_window.burn_rate > policy.burn_rate_threshold
        and long_window.burn_rate > policy.burn_rate_threshold
    ):
        state = AlertState.FIRING
        alert = True
        recovered = False
        reason = (
            "both required windows exceed the configured burn-rate threshold; "
            "error budget is being consumed too quickly"
        )
    else:
        state = AlertState.HEALTHY
        alert = False
        recovered = previous_state is AlertState.FIRING
        reason = (
            "required windows are below or equal to the configured burn-rate "
            "threshold"
        )
        if recovered:
            reason = f"recovered: {reason}"

    return AlertEvaluation(
        policy=policy.name,
        slo_name=definition.name,
        severity=policy.severity,
        state=state,
        alert=alert,
        short_window=policy.short_window,
        long_window=policy.long_window,
        short_burn_rate=short_window.burn_rate,
        long_burn_rate=long_window.burn_rate,
        burn_rate_threshold=policy.burn_rate_threshold,
        slo_target=definition.target,
        allowed_bad_rate=short_window.allowed_bad_rate,
        budget_fraction=policy.budget_fraction,
        threshold_reference_window=policy.threshold_reference_window,
        long_window_eligible_events=long_window.eligible_events,
        long_window_bad_events=long_window.bad_events,
        long_window_allowed_bad_events=long_window.allowed_bad_events,
        long_window_projected_budget_consumption_percent=long_window_projected_consumption,
        recovered=recovered,
        reason=reason,
    )


@dataclass(frozen=True)
class SLODefinition:
    name: str
    target: float
    window: str
    excluded_routes: tuple[str, ...] = ("/health",)
    latency_threshold_ms: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("SLO name must not be empty")
        if (
            isinstance(self.target, bool)
            or not isinstance(self.target, (int, float))
            or not math.isfinite(self.target)
            or not 0 <= self.target <= 1
        ):
            raise ValueError("SLO target must be a finite value between 0 and 1")
        if not isinstance(self.window, str) or not _WINDOW_PATTERN.fullmatch(
            self.window
        ):
            raise ValueError("SLO window must be a positive duration such as 5m or 30d")
        if self.latency_threshold_ms is not None and (
            isinstance(self.latency_threshold_ms, bool)
            or not isinstance(self.latency_threshold_ms, (int, float))
            or not math.isfinite(self.latency_threshold_ms)
            or self.latency_threshold_ms < 0
        ):
            raise ValueError("latency threshold must be a finite non-negative value")


@dataclass(frozen=True)
class RequestObservation:
    route: str
    status_code: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if not self.route:
            raise ValueError("request route must not be empty")
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or not 100 <= self.status_code <= 599
        ):
            raise ValueError("HTTP status code must be between 100 and 599")
        if (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or not math.isfinite(self.duration_seconds)
            or self.duration_seconds < 0
        ):
            raise ValueError("request duration must be a finite non-negative value")


@dataclass(frozen=True)
class SLOObservations:
    eligible_events: int
    good_events: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.eligible_events, bool)
            or isinstance(self.good_events, bool)
            or not isinstance(self.eligible_events, int)
            or not isinstance(self.good_events, int)
            or self.eligible_events < 0
            or self.good_events < 0
            or self.good_events > self.eligible_events
        ):
            raise ValueError(
                "event counts must be non-negative integers with good events "
                "no greater than eligible events"
            )

    @property
    def bad_events(self) -> int:
        return self.eligible_events - self.good_events


@dataclass(frozen=True)
class SLOEvaluation:
    name: str
    window: str
    eligible_events: int
    good_events: int
    bad_events: int
    sli_value: float | None
    slo_target: float
    slo_compliant: bool | None
    allowed_bad_rate: float
    allowed_bad_events: float
    observed_bad_rate: float | None
    error_budget: float
    consumed_error_budget: float | None
    remaining_error_budget: float
    remaining_error_budget_percent: float | None
    burn_rate: float | None


def observe_requests(
    definition: SLODefinition,
    requests: Iterable[RequestObservation],
) -> SLOObservations:
    eligible_events = 0
    good_events = 0
    for request in requests:
        if request.route in definition.excluded_routes:
            continue

        eligible_events += 1
        is_good = request.status_code < 500
        if definition.latency_threshold_ms is not None:
            is_good = is_good and (
                request.duration_seconds * 1000 <= definition.latency_threshold_ms
            )
        good_events += int(is_good)

    return SLOObservations(
        eligible_events=eligible_events,
        good_events=good_events,
    )


def evaluate_slo(
    definition: SLODefinition,
    observations: SLOObservations,
) -> SLOEvaluation:
    allowed_bad_rate = float(Decimal(1) - Decimal(str(definition.target)))
    eligible_events = observations.eligible_events
    bad_events = observations.bad_events
    error_budget = float(
        Decimal(eligible_events) * Decimal(str(allowed_bad_rate))
    )

    if eligible_events == 0:
        sli_value = None
        slo_compliant = None
        observed_bad_rate = None
        consumed_error_budget = None
        remaining_error_budget_percent = None
        burn_rate = None
    else:
        sli_value = observations.good_events / eligible_events
        slo_compliant = sli_value >= definition.target or math.isclose(
            sli_value,
            definition.target,
            rel_tol=0,
            abs_tol=_COMPLIANCE_TOLERANCE,
        )
        observed_bad_rate = bad_events / eligible_events
        if error_budget > 0:
            consumed_error_budget = bad_events / error_budget
            remaining_error_budget_percent = (
                max(error_budget - bad_events, 0) / error_budget * 100
            )
        else:
            consumed_error_budget = None
            remaining_error_budget_percent = None
        burn_rate = (
            calculate_burn_rate(observed_bad_rate, allowed_bad_rate)
            if allowed_bad_rate > 0
            else None
        )

    return SLOEvaluation(
        name=definition.name,
        window=definition.window,
        eligible_events=eligible_events,
        good_events=observations.good_events,
        bad_events=bad_events,
        sli_value=sli_value,
        slo_target=definition.target,
        slo_compliant=slo_compliant,
        allowed_bad_rate=allowed_bad_rate,
        allowed_bad_events=error_budget,
        observed_bad_rate=observed_bad_rate,
        error_budget=error_budget,
        consumed_error_budget=consumed_error_budget,
        remaining_error_budget=max(error_budget - bad_events, 0),
        remaining_error_budget_percent=remaining_error_budget_percent,
        burn_rate=burn_rate,
    )


def calculate_burn_rate(observed_bad_rate: float, allowed_bad_rate: float) -> float:
    if (
        isinstance(observed_bad_rate, bool)
        or not isinstance(observed_bad_rate, (int, float))
        or not math.isfinite(observed_bad_rate)
        or not 0 <= observed_bad_rate <= 1
    ):
        raise ValueError("observed bad rate must be a finite value between 0 and 1")
    if (
        isinstance(allowed_bad_rate, bool)
        or not isinstance(allowed_bad_rate, (int, float))
        or not math.isfinite(allowed_bad_rate)
        or not 0 <= allowed_bad_rate <= 1
    ):
        raise ValueError("allowed bad rate must be a finite value between 0 and 1")
    if allowed_bad_rate == 0:
        raise ValueError("burn rate is undefined when the allowed bad rate is zero")
    return observed_bad_rate / allowed_bad_rate
