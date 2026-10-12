# Exelixi.Tech - QA Automation Framework

A modern, multi-tier QA test automation framework designed for **Exelixi.Tech** to automate manual testing flows for insurance systems (such as **Sys2000** for La Mundial de Seguros) and auxiliary microservices (OCR document extraction).

Powered by **Playwright**, **pytest**, **FastAPI**, and orchestrated with **Google Antigravity** autonomous subagents and Spec-Driven Development (**OpenSpec**).

---

## 🏛️ Architecture & Project Structure

The framework strictly follows the **Page Object Model (POM)** and separates UI interactions from test logic and API mocking:

```text
QA_AUTOMATIZACIÓN/
├── .agents/                    # Antigravity agent configuration
│   ├── agents/                 # Custom subagents (test-writer, pipeline-engineer, code-auditor)
│   ├── skills/                 # Reusable domain skills (pom-conventions)
│   └── hooks.json              # Local life-cycle hooks for continuous testing
├── apiclients/                 # API client abstractions (e.g. OCRClient)
├── mocks/                      # In-memory service mocks (e.g. FastAPI OCR mock)
├── pageobjects/                # Page Object Model classes (LoginPage, UserManagementPage)
├── tests/
│   ├── api/                    # Microservice and mock API test suites
│   ├── e2e/                    # Playwright end-to-end browser test suites
│   └── conftest.py             # Shared pytest fixtures and environment configuration
├── openspec/                   # Spec-Driven Development changes, tasks, and reports
├── .github/workflows/ci.yml    # GitHub Actions continuous integration workflow
├── pytest.ini                  # Pytest configuration and test markers
└── requirements.txt            # Python project dependencies
```

### Layered Separation
1. **E2E Browser Layer (`pageobjects/` & `tests/e2e/`)**: Playwright drives browser workflows. Locators are encapsulated privately within Page Objects; tests only invoke high-level business actions.
2. **API Mock Layer (`apiclients/` & `tests/api/`)**: Simulates external third-party services (e.g., OCR processing) locally via FastAPI. Runs in sub-second execution without network dependency.
3. **Subagent Layer (`.agents/agents/`)**: Autonomous AI agents tailored for QA engineering tasks:
   - `test-writer`: Generates Page Objects and tests adhering to POM conventions.
   - `pipeline-engineer`: Manages virtual environments, tooling, and CI pipelines.
   - `code-auditor`: Validates security (no hardcoded passwords), explicit wait strategies, and test completeness.

---

## 🚀 Getting Started (for Exelixi.Tech Team)

### 1. Prerequisites
- **Python 3.13+** installed.
- **Git** installed and configured.

### 2. Environment Setup

Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/Jvske-max/exelixi-qa-automation.git
cd exelixi-qa-automation

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Environment Variables

Create or export the credentials required for the QA environment (Sys2000):

```bash
export QA_BASE_URL="https://qasys2000.lamundialdeseguros.com/#/login"
export QA_USERNAME="your_qa_username"
export QA_PASSWORD="your_qa_password"
```

*(If omitted, tests fall back to local test defaults configured in `tests/conftest.py`)*.

---

## 🧪 Running Tests

The test suite uses `pytest` markers (`smoke`, `api`, `e2e`):

### ⚡ Fast Smoke & API Tests (Sub-second execution)
Ideal for pre-commit verification and continuous feedback:
```bash
pytest -m "smoke or api" -v
```

### 🌐 End-to-End Browser Tests (Playwright)
Executes browser flows against the QA environment:
```bash
# Headless mode
pytest -m e2e -v

# Headed mode (watch the browser actions live)
pytest -m e2e --headed -v
```

### 📊 Code Coverage
Generate coverage reports for clients and internal services:
```bash
pytest --cov=apiclients --cov=mocks -m "smoke or api"
```

### 🔍 Code Quality & Linting
Run Ruff to check formatting and code standards:
```bash
ruff check .
```

---

## 🤖 Developing with Antigravity Agents

When pair-programming with the Antigravity CLI (`agy`):

- **New Test Case / Page Object**: Ask `test-writer` to automate a manual test sheet:
  > *"Using test-writer, create a Page Object for policy emission following pom-conventions."*
- **Audit Code**: Run `code-auditor` to check for security or bad practices:
  > *"Using code-auditor, audit the new test file before committing."*
- **Continuous Hooks**: The `.agents/hooks.json` automatically triggers fast smoke validation upon saving files.

---

## 📄 License & Maintainers
Maintained by the QA Engineering Team at **Exelixi.Tech**.
