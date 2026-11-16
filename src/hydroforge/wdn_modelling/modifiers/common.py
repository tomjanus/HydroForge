"""

Classes:
    - PipeNotFoundException: Exception raised when a specified pipe is not found in the network.
    - BridgeRemovalException: Exception raised when attempting to remove a pipe that is a bridge.
    - LoggingMixin: Mixin class to add text logging functionality to modifiers.
    - StructuredLoggingMixin: Mixin class to add structured logging functionality to modifiers.

"""

from typing import Any, Optional, Dict, TypeAlias

ComponentName: TypeAlias = Any


class PipeNotFoundException(Exception):
    pass


class BridgeRemovalException(Exception):
    pass


class LoggingMixin:
    """Mixin class to add text logging functionality to modifiers."""

    def __init__(self, text_logging: bool = False) -> None:
        self.text_logging = text_logging
        self.text_log: list = []

    def log_modification(self, message: str) -> None:
        """Log modification if text_logging is enabled."""
        if not self.text_logging:
            return
        self.text_log.append(message)


class StructuredLoggingMixin:
    """Mixin class to add structured logging functionality to modifiers."""

    def __init__(self, structured_logging: bool = False) -> None:
        self.structured_logging = structured_logging
        self.structured_log: dict = {}

    def add_to_structured_log(
        self,
        component_name: ComponentName,
        component_type: str,
        attribute: str,
        old_value: Any,
        new_value: Any,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an entry to the structured log if structured_logging is enabled."""
        if not self.structured_logging:
            return
        class_name = self.__class__.__name__
        self.structured_log.setdefault(class_name, [])
        log_entry = {
            "component_name": component_name,
            "component_type": component_type,
            "attribute": attribute,
            "old_value": old_value,
            "new_value": new_value,
        }
        if details:
            log_entry.update(details)
        self.structured_log[class_name].append(log_entry)
