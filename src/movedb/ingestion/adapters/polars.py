"""Polars adapter for ingestion.

This module provides functions to convert C3D data to Polars DataFrames.
The actual C3D reading is done in c3d.py; this module handles DataFrame operations.
"""

from __future__ import annotations

import logging

import polars as pl

logger = logging.getLogger(__name__)
