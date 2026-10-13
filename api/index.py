"""Vercel serverless entrypoint for the FitControl backend.

Vercel routes ``/api/*`` and ``/health`` here (see ``vercel.json``); the request
path is preserved, so the FastAPI app serves its usual routes unchanged. The
backend package lives in ``backend/`` and is bundled via ``includeFiles``.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.main import app  # noqa: E402,F401
