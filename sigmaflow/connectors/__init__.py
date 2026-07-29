"""
SigmaFlow Data Connectors
=========================
Abstract base class and concrete implementations for data ingestion.

Connectors handle reading data from various sources into pandas DataFrames
with metadata extraction and validation.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from sigmaflow.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ConnectorConfig:
    """Base configuration for all connectors."""
    name: str
    source_type: str
    config: dict = field(default_factory=dict)


@dataclass
class IngestionResult:
    """Result of a data ingestion operation."""
    success: bool
    dataset_id: Optional[str] = None
    file_hash: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = field(default_factory=list)
    dtypes: dict = field(default_factory=dict)
    sample_data: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):
    """
    Abstract base class for all data connectors.

    Subclasses must implement:
    - validate_config(): Verify configuration is valid
    - connect(): Establish connection (if needed)
    - read(): Read data into DataFrame
    - close(): Clean up resources
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._connected = False
        self._connection = None

    @abstractmethod
    def validate_config(self) -> tuple[bool, Optional[str]]:
        """
        Validate connector configuration.

        Returns:
            (is_valid, error_message)
        """
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to data source.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def read(self, **kwargs) -> IngestionResult:
        """
        Read data from source into DataFrame.

        Args:
            **kwargs: Source-specific parameters (e.g., query, table_name, file_path)

        Returns:
            IngestionResult with data and metadata
        """
        pass

    def close(self) -> None:
        """Close connection and cleanup resources."""
        self._connected = False
        self._connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def is_connected(self) -> bool:
        return self._connected


class CSVConnector(BaseConnector):
    """Connector for CSV files."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.default_encoding = config.config.get("encoding", "utf-8")
        self.default_separator = config.config.get("separator", ",")
        self.default_na_values = config.config.get("na_values", ["", "NA", "N/A", "null", "NULL", "nan", "NaN"])

    def validate_config(self) -> tuple[bool, Optional[str]]:
        return True, None

    def connect(self) -> bool:
        self._connected = True
        return True

    def read(
        self,
        file_path: str,
        encoding: Optional[str] = None,
        separator: Optional[str] = None,
        na_values: Optional[list] = None,
        **kwargs
    ) -> IngestionResult:
        """Read CSV file into DataFrame."""
        path = Path(file_path)
        if not path.exists():
            return IngestionResult(
                success=False,
                error=f"File not found: {file_path}"
            )

        try:
            df = pd.read_csv(
                path,
                encoding=encoding or self.default_encoding,
                sep=separator or self.default_separator,
                na_values=na_values or self.default_na_values,
                **kwargs
            )

            file_hash = self._compute_hash(path)

            return IngestionResult(
                success=True,
                file_hash=file_hash,
                row_count=len(df),
                column_count=len(df.columns),
                columns=list(df.columns),
                dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
                sample_data=df.head(5).to_dict(orient="records"),
                metadata={
                    "source_type": "csv",
                    "file_path": str(path),
                    "file_size": path.stat().st_size,
                }
            )
        except Exception as e:
            logger.error(f"CSV read failed: {e}")
            return IngestionResult(success=False, error=str(e))

    def _compute_hash(self, path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


class ExcelConnector(BaseConnector):
    """Connector for Excel files (.xlsx, .xls)."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.default_sheet = config.config.get("sheet_name", 0)

    def validate_config(self) -> tuple[bool, Optional[str]]:
        return True, None

    def connect(self) -> bool:
        self._connected = True
        return True

    def read(
        self,
        file_path: str,
        sheet_name: Optional[str | int] = None,
        **kwargs
    ) -> IngestionResult:
        """Read Excel file into DataFrame."""
        path = Path(file_path)
        if not path.exists():
            return IngestionResult(
                success=False,
                error=f"File not found: {file_path}"
            )

        try:
            df = pd.read_excel(
                path,
                sheet_name=sheet_name or self.default_sheet,
                **kwargs
            )

            # If multiple sheets, read returns dict
            if isinstance(df, dict):
                # Take first sheet or named sheet
                first_key = list(df.keys())[0]
                df = df[first_key]
                logger.info(f"Multiple sheets found, using '{first_key}'")

            file_hash = self._compute_hash(path)

            return IngestionResult(
                success=True,
                file_hash=file_hash,
                row_count=len(df),
                column_count=len(df.columns),
                columns=list(df.columns),
                dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
                sample_data=df.head(5).to_dict(orient="records"),
                metadata={
                    "source_type": "excel",
                    "file_path": str(path),
                    "file_size": path.stat().st_size,
                    "sheet_name": sheet_name or self.default_sheet,
                }
            )
        except Exception as e:
            logger.error(f"Excel read failed: {e}")
            return IngestionResult(success=False, error=str(e))

    def _compute_hash(self, path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


class SQLConnector(BaseConnector):
    """Connector for SQL databases (PostgreSQL, MySQL, SQL Server, SQLite)."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.connection_string = config.config.get("connection_string", "")
        self.engine = None

    def validate_config(self) -> tuple[bool, Optional[str]]:
        if not self.connection_string:
            return False, "connection_string is required for SQL connector"
        return True, None

    def connect(self) -> bool:
        try:
            from sqlalchemy import create_engine
            self.engine = create_engine(self.connection_string)
            # Test connection
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"SQL connection failed: {e}")
            return False

    def read(
        self,
        query: str,
        params: Optional[dict] = None,
        chunksize: Optional[int] = None,
        **kwargs
    ) -> IngestionResult:
        """Execute SQL query and return DataFrame."""
        if not self._connected or self.engine is None:
            if not self.connect():
                return IngestionResult(success=False, error="Database connection failed")

        try:
            if chunksize:
                # For large results, we'd need a different approach
                df = pd.read_sql(query, self.engine, params=params, chunksize=chunksize)
                # For now, just take first chunk
                df = next(df)
            else:
                df = pd.read_sql(query, self.engine, params=params)

            return IngestionResult(
                success=True,
                row_count=len(df),
                column_count=len(df.columns),
                columns=list(df.columns),
                dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
                sample_data=df.head(5).to_dict(orient="records"),
                metadata={
                    "source_type": "sql",
                    "query": query[:200] + "..." if len(query) > 200 else query,
                }
            )
        except Exception as e:
            logger.error(f"SQL read failed: {e}")
            return IngestionResult(success=False, error=str(e))

    def close(self) -> None:
        if self.engine:
            self.engine.dispose()
            self.engine = None
        super().close()


class APIConnector(BaseConnector):
    """Connector for REST APIs returning JSON data."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.base_url = config.config.get("base_url", "")
        self.headers = config.config.get("headers", {})
        self.auth = config.config.get("auth")  # tuple (user, pass) or token
        self.timeout = config.config.get("timeout", 30)
        self.client = None

    def validate_config(self) -> tuple[bool, Optional[str]]:
        if not self.base_url:
            return False, "base_url is required for API connector"
        return True, None

    def connect(self) -> bool:
        try:
            import httpx
            self.client = httpx.Client(
                base_url=self.base_url,
                headers=self.headers,
                auth=self.auth,
                timeout=self.timeout,
            )
            # Test with a HEAD request to base
            resp = self.client.head("/")
            resp.raise_for_status()
            self._connected = True
            return True
        except Exception as e:
            logger.warning(f"API connection test failed (may still work for actual endpoints): {e}")
            self._connected = True  # Allow anyway for POST endpoints etc.
            return True

    def read(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        data_path: Optional[str] = None,  # e.g., "data.items" for nested JSON
        **kwargs
    ) -> IngestionResult:
        """Call API endpoint and convert response to DataFrame."""
        if not self._connected or self.client is None:
            if not self.connect():
                return IngestionResult(success=False, error="API client not connected")

        try:
            import httpx
            resp = self.client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json,
                **kwargs
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract nested data if path provided
            if data_path:
                for key in data_path.split("."):
                    if isinstance(data, dict):
                        data = data.get(key, [])
                    elif isinstance(data, list) and key.isdigit():
                        data = data[int(key)]
                    else:
                        data = []

            if not isinstance(data, list):
                data = [data] if data else []

            df = pd.DataFrame(data)

            return IngestionResult(
                success=True,
                row_count=len(df),
                column_count=len(df.columns),
                columns=list(df.columns),
                dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
                sample_data=df.head(5).to_dict(orient="records"),
                metadata={
                    "source_type": "api",
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": resp.status_code,
                }
            )
        except Exception as e:
            logger.error(f"API read failed: {e}")
            return IngestionResult(success=False, error=str(e))

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
        super().close()


# ── Connector Factory ────────────────────────────────────────────────────────

class ConnectorRegistry:
    """Registry for available connector types."""

    _connectors: dict[str, type[BaseConnector]] = {
        "csv": CSVConnector,
        "excel": ExcelConnector,
        "sql": SQLConnector,
        "api": APIConnector,
    }

    @classmethod
    def register(cls, name: str, connector_class: type[BaseConnector]) -> None:
        cls._connectors[name] = connector_class

    @classmethod
    def get(cls, name: str) -> Optional[type[BaseConnector]]:
        return cls._connectors.get(name.lower())

    @classmethod
    def create(cls, name: str, config: ConnectorConfig) -> Optional[BaseConnector]:
        connector_class = cls.get(name)
        if connector_class:
            return connector_class(config)
        return None

    @classmethod
    def list_available(cls) -> list[str]:
        return list(cls._connectors.keys())


def get_connector_registry() -> ConnectorRegistry:
    return ConnectorRegistry()