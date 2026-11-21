# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The /api/v1 router. Later tasks add their sub-routers with `api_router.include_router`."""

from fastapi import APIRouter

from supertrends.api.routes.read import router as read_router
from supertrends.api.routes.watchlist import router as watchlist_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(watchlist_router)
api_router.include_router(read_router)
