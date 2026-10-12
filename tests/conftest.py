import os

import pytest


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("QA_BASE_URL", "https://qasys2000.lamundialdeseguros.com/#/login")

@pytest.fixture
def valid_credentials():
    return {
        "username": os.getenv("QA_USERNAME", "rmuñoz"),
        "password": os.getenv("QA_PASSWORD", "rmuñoz")
    }

@pytest.fixture
def invalid_credentials():
    return {"username": "invalid_user", "password": "wrong_password"}
