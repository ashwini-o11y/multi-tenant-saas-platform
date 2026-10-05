from app.models import TenantStatus


class TenantLifecycleError(Exception):
    status_code = 400


class InvalidTenantIdError(TenantLifecycleError):
    def __init__(self) -> None:
        super().__init__(
            "tenant_id must be 3-50 lowercase letters or digits, with single hyphens "
            "between segments"
        )


class InvalidTenantNameError(TenantLifecycleError):
    def __init__(self) -> None:
        super().__init__("Tenant name must not be empty")


class TenantAlreadyExistsError(TenantLifecycleError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("Tenant already exists")


class TenantNotFoundError(TenantLifecycleError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Tenant not found")


class InvalidTenantTransitionError(TenantLifecycleError):
    status_code = 409

    def __init__(self, current: TenantStatus, target: TenantStatus) -> None:
        super().__init__(f"Cannot transition tenant from {current.value} to {target.value}")
