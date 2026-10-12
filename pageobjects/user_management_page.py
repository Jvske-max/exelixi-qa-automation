from playwright.sync_api import Error, Page, TimeoutError, expect


class UserManagementPage:
    def __init__(self, page: Page):
        self.page = page

        # Private locators at the top of __init__
        self._mantenimiento_link = "a:has-text('Mantenimiento'), button:has-text('Mantenimiento'), span:has-text('Mantenimiento')"
        self._seguridad_link = "a:has-text('Seguridad'), button:has-text('Seguridad'), span:has-text('Seguridad')"
        self._add_user_button = "button:has-text('Agregar Usuario'), a:has-text('Agregar Usuario')"
        self._modal_dialog = ".modal-dialog, [role='dialog'], .modal-content, form"
        self._username_input = "input[name='username'], input[name='usuario'], input[placeholder*='Usuario'], #username, #usuario"
        self._email_input = "input[name='email'], input[name='correo'], input[type='email'], #email"
        self._password_input = "input[name='password'], input[name='contrasena'], input[type='password']"
        self._confirm_password_input = "input[name='confirmPassword'], input[name='confirmar_contrasena'], input[placeholder*='Confirmar']"
        self._save_button = "button:has-text('Guardar'), button[type='submit']:has-text('Guardar')"
        self._cancel_button = "button:has-text('Cancelar'), button:has-text('Cerrar')"
        self._validation_error = ".invalid-feedback, .error-message, .text-danger, [role='alert'], span.error, :invalid"
        self._users_table = "table, .table, .mat-table, .user-grid, div[role='grid'], button:has-text('Agregar Usuario')"

    def navigate_to_user_management(self):
        mantenimiento = self.page.locator(self._mantenimiento_link).first
        expect(mantenimiento).to_be_visible(timeout=10000)
        mantenimiento.click()

        seguridad = self.page.locator(self._seguridad_link).first
        expect(seguridad).to_be_visible(timeout=10000)
        seguridad.click()

        self.page.wait_for_load_state("domcontentloaded")

    def open_add_user_form(self):
        add_btn = self.page.locator(self._add_user_button).first
        expect(add_btn).to_be_visible(timeout=10000)
        add_btn.click()

        modal_or_user_input = self.page.locator(f"{self._modal_dialog}, {self._username_input}").first
        expect(modal_or_user_input).to_be_visible(timeout=10000)

    def fill_user_form(self, username: str, email: str, password: str, confirm_password: str):
        if username:
            user_field = self.page.locator(self._username_input).first
            expect(user_field).to_be_visible(timeout=5000)
            user_field.fill(username)

        if email:
            email_field = self.page.locator(self._email_input).first
            expect(email_field).to_be_visible(timeout=5000)
            email_field.fill(email)

        if password:
            pwd_field = self.page.locator(self._password_input).first
            expect(pwd_field).to_be_visible(timeout=5000)
            pwd_field.fill(password)

        if confirm_password:
            confirm_pwd_field = self.page.locator(self._confirm_password_input).first
            expect(confirm_pwd_field).to_be_visible(timeout=5000)
            confirm_pwd_field.fill(confirm_password)

    def save_user(self):
        save_btn = self.page.locator(self._save_button).first
        expect(save_btn).to_be_visible(timeout=5000)
        save_btn.click()

    def is_form_validation_displayed(self) -> bool:
        try:
            # Check for validation messages or HTML5 invalid pseudo-classes
            validation_loc = self.page.locator(self._validation_error).first
            validation_loc.wait_for(state="visible", timeout=4000)
            return True
        except (TimeoutError, Error):
            # Fallback: check if required fields are flagged as invalid via standard browser validation
            required_invalid = self.page.locator("input:invalid").count()
            return required_invalid > 0

    def is_user_management_loaded(self) -> bool:
        try:
            table_loc = self.page.locator(self._users_table).first
            table_loc.wait_for(state="visible", timeout=10000)
            return True
        except (TimeoutError, Error):
            return False
