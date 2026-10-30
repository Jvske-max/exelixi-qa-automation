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

## 📖 Beginner's Guide (How to Install & Use)

Welcome! If you are a QA tester, analyst, or team member at **Exelixi.Tech** without a software engineering background, this guide is designed for you.

### 🤔 What does this tool do?
Think of this tool as an **automated virtual assistant**:
1. You receive a **Word (`.docx`) or PDF document** from developers describing manual test steps.
2. You pass that file to this tool.
3. The tool **reads the document, opens Google Chrome, performs the clicks and text inputs step-by-step, and takes screenshot evidence of every action**.
4. When finished, it delivers an **Executive PDF Report** showing what passed, what failed, and the full screenshot log.

---

### 💻 Step-by-Step Setup (One-Time Setup)

You only need to complete this setup once on your computer.

#### Step 1: Open your Terminal
- **Windows**: Press `Win + R`, type `powershell`, and press Enter.
- **Mac / Linux**: Open the **Terminal** app.

#### Step 2: Download the Project
Copy and paste this command into your terminal:
```bash
git clone https://github.com/Jvske-max/exelixi-qa-automation.git
cd exelixi-qa-automation
```

#### Step 3: Create Your Private Work Environment
Python uses a "virtual environment" (a private sandbox so it doesn't conflict with other programs):

- **On Mac / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- **On Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```
*(You will see `(.venv)` appear at the start of your command prompt. That means your environment is active!)*

#### Step 4: Install Dependencies
Run this command to install all required libraries:
```bash
pip install -r requirements.txt
```

#### Step 5: Install the Automated Browser
Download the automated Chrome browser:
```bash
playwright install chromium
```
🎉 **Setup is complete! You are ready to run tests.**

---

### 🚀 How to Run a Test from a Word (`.docx`) or PDF Document

Whenever developers deliver a test specification document (such as `pruebas QA # 1 R-055429...docx`):

#### 1. Place the document in the project folder
Copy your `.docx` or `.pdf` file into the `exelixi-qa-automation` folder.

#### 2. Run the Automation
Run this command in your terminal:

```bash
python -m runners.doc_runner \
  --doc "pruebas QA # 1 R-055429_mantenimiento_usuarios_usuario_para_reporteria fecha 24092026.docx" \
  --output-report "artifacts/execution_report.pdf" \
  --headed
```

**Command options explained:**
- `--doc`: The filename of the Word or PDF document you want to execute.
- `--output-report`: Where to save the final PDF report (e.g. `artifacts/execution_report.pdf`).
- `--headed`: *(Recommended for visual observation)* Opens the browser on your screen so you can watch the robot click and fill fields in real time. Remove `--headed` if you want it to run silently in the background.

#### 3. View Your Results!
- Open the `artifacts/` folder on your computer.
- Double-click **`execution_report.pdf`** to view your executive report with all test steps, timestamps, and embedded screenshots.
- Individual full-size screenshots are also saved in `test-evidence/screenshots/`.

---

### ⚡ Running Pre-Configured Test Suites

If you want to run the automated framework checks:

- **⚡ Fast Smoke & API Tests** (runs in under 1 second without network dependencies):
  ```bash
  pytest -m "smoke or api" -v
  ```
- **🌐 End-to-End Browser Tests Live** (runs against the QA environment with browser visible):
  ```bash
  pytest -m e2e --headed -v
  ```
- **📊 Code Coverage Report**:
  ```bash
  pytest --cov=parsers --cov=reporting --cov=runners tests/unit/ tests/integration/
  ```

---

### ❓ Frequently Asked Questions & Troubleshooting

- **Q: It says `python3: command not found` or `python is not recognized`.**  
  👉 You need to install Python 3.13 from [python.org](https://www.python.org/downloads/). On Windows, ensure you check the box *"Add Python to PATH"* during installation.
- **Q: It says `playwright: command not found` or the browser doesn't open.**  
  👉 Ensure your virtual environment is active (you see `(.venv)` in your terminal prompt) and run `playwright install chromium`.
- **Q: How do I customize Sys2000 test credentials?**  
  👉 Tests require credentials configured via environment variables or `.env` (`QA_USERNAME` and `QA_PASSWORD`), or use `test_user` as an example. Set them before running:
  - Mac/Linux: `export QA_USERNAME="your_user"` and `export QA_PASSWORD="your_password"`
  - Windows: `$env:QA_USERNAME="your_user"` and `$env:QA_PASSWORD="your_password"`

---

## 🧪 Normalizar una prueba

Cuando recibes una prueba redactada con estilo libre (`.docx` o `.pdf`), utiliza el pipeline normalizador para convertirla al formato canónico ejecutable e identificar qué datos faltan.

> [!NOTE]
> **Nota sobre el enmascarado:** El proceso de enmascaramiento automático protege credenciales, correos electrónicos, cédulas (con y sin puntos), RIF y tokens JWT. **NO** cubre nombres de personas, números de póliza, teléfonos ni nombres de servidores internos. El archivo generado mediante `--dry-run` se almacena exclusivamente dentro de `build/<id>/` (directorio ignorado por Git).

Ejecuta estos cinco pasos en PowerShell (cada uno en una sola línea):

### 1. Extraer texto, metadatos y capturas del documento original
```powershell
python -m normalizer.extract build/sample/muestra.docx --out build/sample/dump
```

### 2. Normalizar con el sub-agente IA
```powershell
agy "Normaliza build/sample/muestra.docx usando build/sample/dump. Escribe normalized/muestra.json y valídalo."
```

### 3. Validar esquema y reglas de grounding
```powershell
python -m normalizer.cli validate normalized/muestra.json
```

### 4. Renderizar a especificación canónica (.docx) y reporte de faltantes (.gaps.md)
```powershell
python -m normalizer.cli render normalized/muestra.json --out normalized/
```

### 5. Ejecutar el caso normalizado con el runner
```powershell
python -m runners.doc_runner --doc normalized/R-SAMPLE-01-caso1.docx --output-report artifacts/reporte_caso1.pdf
```
*(Si un caso tiene estado `NEEDS_INFO` o `UNSUPPORTED`, el runner no abrirá el navegador, imprimirá la ruta de su archivo `.gaps.md` adyacente y saldrá inmediatamente con código 2).*

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
