import pytest
from playwright.sync_api import Page

from pageobjects.login_page import LoginPage
from pageobjects.user_management_page import UserManagementPage


@pytest.mark.e2e
def test_navigate_to_user_management_flow(page: Page, base_url, valid_credentials):
    """Verifica el flujo positivo de navegación al módulo de mantenimiento de usuarios."""
    login_page = LoginPage(page)
    login_page.navigate(base_url)
    login_page.login(valid_credentials["username"], valid_credentials["password"])
    assert login_page.is_login_successful(), "El login falló o no se cargó el dashboard"

    user_mgmt_page = UserManagementPage(page)
    user_mgmt_page.navigate_to_user_management()

    assert user_mgmt_page.is_user_management_loaded(), (
        "El módulo de gestión de usuarios no se cargó correctamente"
    )


@pytest.mark.e2e
def test_add_user_empty_fields_validation_negative(page: Page, base_url, valid_credentials):
    """Verifica que intentar guardar un usuario con campos vacíos muestre errores de validación."""
    login_page = LoginPage(page)
    login_page.navigate(base_url)
    login_page.login(valid_credentials["username"], valid_credentials["password"])
    assert login_page.is_login_successful(), "El login falló o no se cargó el dashboard"

    user_mgmt_page = UserManagementPage(page)
    user_mgmt_page.navigate_to_user_management()
    assert user_mgmt_page.is_user_management_loaded(), (
        "No se pudo cargar la vista de gestión de usuarios"
    )

    user_mgmt_page.open_add_user_form()
    # Enviar formulario con campos vacíos
    user_mgmt_page.fill_user_form(username="", email="", password="", confirm_password="")
    user_mgmt_page.save_user()

    assert user_mgmt_page.is_form_validation_displayed(), (
        "Se esperaba mensaje de validación o campos requeridos marcados como inválidos"
    )
