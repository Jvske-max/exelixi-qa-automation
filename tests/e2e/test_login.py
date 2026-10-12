import pytest
from playwright.sync_api import Page

from pageobjects.login_page import LoginPage


@pytest.mark.e2e
def test_valid_login(page: Page, base_url, valid_credentials):
    """Prueba de inicio de sesión exitoso con credenciales válidas."""
    login_page = LoginPage(page)
    login_page.navigate(base_url)
    
    login_page.login(valid_credentials["username"], valid_credentials["password"])
    
    # Asumimos que el inicio de sesión es exitoso si aparece un elemento del dashboard
    # En un caso real, podríamos verificar el cambio de URL o un saludo
    assert login_page.is_login_successful(), "El login falló o no se encontró el elemento del dashboard"

@pytest.mark.e2e
def test_invalid_login(page: Page, base_url, invalid_credentials):
    """Prueba de inicio de sesión fallido con credenciales inválidas."""
    login_page = LoginPage(page)
    login_page.navigate(base_url)
    
    login_page.login(invalid_credentials["username"], invalid_credentials["password"])
    
    # Verificamos que el login no fue exitoso
    assert not login_page.is_login_successful(), "El login no debería ser exitoso con credenciales inválidas"
