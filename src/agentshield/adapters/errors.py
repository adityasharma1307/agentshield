"""Errors raised by agent adapters."""


class AdapterError(Exception):
    """The target agent could not produce a step.

    `status_code` is set when the failure came from an HTTP response.
    The message must not repeat secrets that were sent in the run context.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
