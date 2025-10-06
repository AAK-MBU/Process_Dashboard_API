"""Custom exceptions for the application."""


class ProcessDashboardException(Exception):
    """Base exception for Process Dashboard API."""


class ResourceNotFoundError(ProcessDashboardException):
    """Base class for resource not found errors."""

    def __init__(self, resource_type: str, resource_id: int | str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(self.message)


class ProcessNotFoundError(ResourceNotFoundError):
    """Process not found."""

    def __init__(self, process_id: int):
        super().__init__("Process", process_id)


class ProcessRunNotFoundError(ResourceNotFoundError):
    """Process run not found."""

    def __init__(self, run_id: int):
        super().__init__("Process run", run_id)


class StepNotFoundError(ResourceNotFoundError):
    """Process step not found."""

    def __init__(self, step_id: int):
        super().__init__("Process step", step_id)


class StepRunNotFoundError(ResourceNotFoundError):
    """Process step run not found."""

    def __init__(self, step_run_id: int):
        super().__init__("Process step run", step_run_id)


class RunNotFoundError(ResourceNotFoundError):
    """Process run not found."""

    def __init__(self, run_id: int):
        super().__init__("Run", run_id)


class StepRunError(ProcessDashboardException):
    """Error related to step run operations."""


class AuthenticationError(ProcessDashboardException):
    """Authentication related errors."""


class AuthorizationError(ProcessDashboardException):
    """Authorization related errors."""
