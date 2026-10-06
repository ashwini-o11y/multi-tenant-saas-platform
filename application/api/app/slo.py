from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
import re
from typing import Iterable


_WINDOW_PATTERN = re.compile(r"^[1-9]\d*[smhd]$")
_COMPLIANCE_TOLERANCE = 1e-12


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
