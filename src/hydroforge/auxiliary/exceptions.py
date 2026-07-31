"""Custom exceptions for HydroForge auxiliary operations.

This module defines custom exception classes for handling specific error conditions:
- UserConfigLoadException: Errors during configuration file loading/parsing
- EPANETFileParserError: Errors during EPANET input file parsing

All exceptions support rich-formatted error messages for better user feedback.
"""
from rich import print as rprint

class UserConfigLoadException(Exception):
    """Wrapper for errors loading or parsing user configuration.

    This exception wraps various configuration file errors (file not found,
    permission denied, YAML parsing errors) into a single, user-friendly
    exception type with optional rich formatting.

    Parameters
    ----------
    message : str
        Human-friendly message describing the error.
    original : Exception or None, optional
        Original exception instance that triggered this error.
    show_original : bool, default=False
        If True, __str__ and log() include the original exception details.

    Attributes
    ----------
    message : str
        The error message.
    original : Exception or None
        The original exception if provided.
    show_original : bool
        Whether to display the original exception.

    Examples
    --------
    >>> try:
    ...     with open('missing.yaml') as f:
    ...         pass
    ... except FileNotFoundError as e:
    ...     raise UserConfigLoadException(
    ...         "Config file not found", e, show_original=True
    ...     )
    """

    def __init__(
            self,
            message: str,
            original: Exception | None = None,
            *,
            show_original: bool = False) -> None:
        """Initialize the exception.

        Parameters
        ----------
        message : str
            Human-friendly error message.
        original : Exception or None, optional
            Original exception that caused this error.
        show_original : bool, default=False
            Whether to include original exception in string representation.
        """
        super().__init__(message)
        self.message = message
        self.original = original
        self.show_original = show_original

    def __str__(self) -> str:
        """Return string representation including original exception if requested.

        Returns
        -------
        str
            Error message, optionally with original exception details.
        """
        if self.show_original and self.original is not None:
            return f"{self.message} (caused by {self.original!r})"
        return self.message

    def log(self) -> None:
        """Pretty-print the error using rich formatting.

        Prints the error message to console with rich formatting.
        If show_original is True, also displays the original exception.
        """
        if self.show_original and self.original is not None:
            rprint(f"[red]Error:[/red] {self.message}\n[dim]Original:[/dim] {self.original!r}")
        else:
            rprint(f"[red]Error:[/red] {self.message}")
            

class EPANETFileParserError(Exception):
    """Custom exception for EPANET file parsing errors.

    This exception is raised when there are errors parsing EPANET input files,
    such as invalid format, unexpected structure, or malformed sections.

    Parameters
    ----------
    message : str
        Description of the parsing error.

    Attributes
    ----------
    message : str
        The error message.

    Examples
    --------
    >>> raise EPANETFileParserError("Expected '[', found: 'TITLE'")
    """
    def __init__(self, message: str):
        """Initialize the exception.

        Parameters
        ----------
        message : str
            Description of the parsing error.
        """
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return string representation of the exception.

        Returns
        -------
        str
            Formatted error message with 'EPANET File Parser Error:' prefix.
        """
        return f'EPANET File Parser Error: {self.message}'
    
    def log(self) -> None:
        """Pretty-print the error using rich formatting.

        Prints the error message to console with red color formatting.
        """
        rprint(f"[red]EPANET File Parser Error:[/red] {self.message}")