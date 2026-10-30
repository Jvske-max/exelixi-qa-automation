import os

import pytest


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("QA_BASE_URL", "https://qa.example.test/login")

@pytest.fixture
def valid_credentials():
    return {
        "username": os.getenv("QA_USERNAME", "test_user"),
        "password": os.getenv("QA_PASSWORD", "test_password")
    }

@pytest.fixture
def invalid_credentials():
    return {"username": "invalid_user", "password": "wrong_password"}
