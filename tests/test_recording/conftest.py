"""Pytest configuration and fixtures for recording tests."""
import os
import pytest


@pytest.fixture
def clear_recording_env():
    """Clear recording environment variables before test."""
    os.environ.pop("PRAETORIAN_NO_RECORD", None)
