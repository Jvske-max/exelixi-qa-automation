from playwright.sync_api import Error, Page, TimeoutError


class LoginPage:
    def __init__(self, page: Page):
        self.page = page
        self._username_input = "input[type='text'], input[name='username'], input[name='usuario']"
        self._password_input = "input[type='password'], input[name='password'], input[name='clave']"
        self._login_button = "button[type='submit'], button:has-text('Ingresar'), button:has-text('Login')"
        self._error_message = ".error-message, .alert-danger, [role='alert']"
        self._dashboard_element = ".dashboard, .main-menu, nav"

    def navigate(self, url: str):
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

    def login(self, username, password):
        self.page.wait_for_selector(self._username_input, state="visible", timeout=10000)
        self.page.fill(self._username_input, username)
        
        self.page.wait_for_selector(self._password_input, state="visible")
        self.page.fill(self._password_input, password)
        
        self.page.wait_for_selector(self._login_button, state="visible")
        self.page.click(self._login_button)

    def is_login_successful(self) -> bool:
        try:
            self.page.wait_for_selector(self._dashboard_element, state="visible", timeout=5000)
            return True
        except (TimeoutError, Error):
            return False

    def get_error_message(self) -> str:
        self.page.wait_for_selector(self._error_message, state="visible", timeout=5000)
        return self.page.locator(self._error_message).first.text_content()
