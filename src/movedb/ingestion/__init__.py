"""Ingestion workflows — compose adapters + storage for data conversion."""

from .session import process_session

__all__ = ["process_session"]
