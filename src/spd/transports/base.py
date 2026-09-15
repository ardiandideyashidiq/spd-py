"""Abstract base transport interface for Unisoc BSL communication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Self


class TransportError(Exception):
    """Base exception for transport layer communication errors."""


class BaseTransport(ABC):
    """Abstract interface representing a physical or simulated communication transport."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the target device."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the target device."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if connection is active."""

    @abstractmethod
    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        """Read up to max_bytes from the transport within timeout seconds."""

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Write bytes to the transport. Return number of bytes written."""

    @property
    def name(self) -> str:
        """Friendly name of the transport."""
        return self.__class__.__name__

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.disconnect()
