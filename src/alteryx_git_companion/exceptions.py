"""Typed exception hierarchy for alteryx_git_companion parse errors.

All parsing failures are reported through these exceptions. They carry both
a plain-English ``message`` and the ``filepath`` that caused the failure,
so CLI error handlers can present structured output without needing to parse
the exception message string.

This module has zero project-internal imports; it is safe to import from
any pipeline stage without risk of circular dependencies.
"""

from __future__ import annotations

__all__ = [
    "ParseError",
    "MalformedXMLError",
    "MissingFileError",
    "UnreadableFileError",
]


class ParseError(Exception):
    """Base class for all parse-time errors raised by alteryx_git_companion.

    All subclasses carry ``filepath`` (the file that triggered the error)
    and ``message`` (a plain-English description of the problem).
    The CLI catches ``ParseError`` subclasses and exits with code 2.
    """

    def __init__(self, *, filepath: str, message: str) -> None:
        super().__init__(message)
        self.filepath: str = filepath
        self.message: str = message


class MalformedXMLError(ParseError):
    """Raised when lxml cannot parse the file as well-formed XML.

    This includes the empty-file case: lxml reports "Document is empty" as
    an ``XMLSyntaxError``, which the parser translates to this exception.
    """


class MissingFileError(ParseError):
    """Raised when the given path does not exist on the filesystem."""


class UnreadableFileError(ParseError):
    """Raised when the path exists but cannot be read as a regular file.

    Covers directories, permission errors, and other OS-level I/O failures
    that prevent the parser from opening the file.
    """
