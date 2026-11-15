# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The /api/v1 router. Later tasks add their sub-routers with `api_router.include_router`."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
