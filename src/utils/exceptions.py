"""
Portugal Data Intelligence — Custom exception hierarchy.

Usage:
    from src.utils.exceptions import DataFetchError, AnalysisError
    raise DataFetchError("Eurostat API timeout")
"""


class PDIBaseError(Exception):
    """Base exception for all Portugal Data Intelligence errors."""


class ETLError(PDIBaseError):
    """Raised for general ETL pipeline failures."""


class DataFetchError(ETLError):
    """Raised when fetching data from an external source fails."""


class DataTransformError(ETLError):
    """Raised when transforming or validating fetched data fails."""


class AnalysisError(PDIBaseError):
    """Raised when an analysis computation fails unrecoverably."""


class DatabaseError(PDIBaseError):
    """Raised for database connection or query failures."""
