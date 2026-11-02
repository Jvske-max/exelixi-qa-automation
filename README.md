# Sistema de Automatización y Normalización Cognitiva de Pruebas con IA

> **Proyecto de Pasantías de Ingeniería de Software e Inteligencia Artificial**  
> **Organización:** Desarrollado para la empresa **ExelixiTech, C.A.**  
> **Autor:** Fernando José Silva Trejo  
> **Tecnologías:** Python 3.13 | Playwright | FastAPI | Pydantic v2 | Mypy | Pytest | Allure 2 | ReportLab | Google Antigravity

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Type Checked: Mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](http://mypy-lang.org/)
[![Linted: Ruff](https://img.shields.io/badge/linter-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests: 227 passing](https://img.shields.io/badge/tests-227%20passing-brightgreen.svg)]()
[![Methodology: Spec--Driven Development](https://img.shields.io/badge/methodology-OpenSpec-purple.svg)]()
[![Security: Zero Secrets & PII Masking](https://img.shields.io/badge/security-PII%20Masked-success.svg)]()

---

## 📌 Resumen Ejecutivo y Propósito

En entornos empresariales de alta criticidad en **ExelixiTech, C.A.** (atendiendo plataformas como **Sys2000** y microservicios auxiliares), los equipos de Control de Calidad (QA) y Pruebas Funcionales reciben continuamente especificaciones de pruebas redactadas en lenguaje natural no estructurado (Word `.docx`, PDF, actas de requerimiento y matrices manuales). Estas especificaciones suelen presentar:
- Ambigüedades en los pasos de prueba.
- Parámetros faltantes (URLs, datos de prueba no documentados o selectores tácitos).
- Credenciales o datos sensibles expuestos en el texto del documento.
- Brecha operativa entre el documento funcional y su implementación en código automatizado.

Este proyecto aborda dicha problemática implementando una **arquitectura híbrida de ingeniería de software e inteligencia artificial generativa**, diseñada bajo los más rigurosos estándares de seguridad y observabilidad requeridos en la industria del software y seguros:

1. **Ingestión y Normalización Asistida por IA**: Transforma narrativas de prueba libres en especificaciones canónicas estructuradas y ejecutables, detectando vacíos de información (*gap analysis*) antes de tocar el navegador.
2. **Grounding Anti-Alucinación**: Algoritmo de verificación que valida que cada acción, URL y valor provenga estrictamente del documento original mediante citas textuales verificadas, rechazando cualquier invención del modelo.
3. **Privacidad de Datos y Protección de Información Sensible (PII)**: Enmascaramiento irreversible de credenciales, tokens JWT, correos, Cédulas de Identidad venezolanas y RIFs antes de cualquier interacción con modelos de lenguaje, complementado con modo seguro `--dry-run`.
4. **Ejecución Documental y Tolerancia a Fallos**: Motor automatizado con Playwright que despacha pasos de prueba, valida precondiciones mediante un *pre-flight gate* (deteniendo la ejecución con código de salida `2` si faltan datos críticos) y captura evidencias visuales paso a paso.
5. **Reportería Dual de Nivel Corporativo**: Emisión simultánea de reportes ejecutivos en PDF para auditoría y artefactos estructurados en Allure 2 para dashboards de ingeniería.
6. **Calidad de Código y Tipado Estático Estricto**: 100% tipado y verificado con **Mypy** (cero errores en 28 módulos del núcleo), cobertura exhaustiva de pruebas (227 tests unitarios e integración) y pipeline de Integración Continua (CI) multi-sistema operativo.

---

## 🏛️ Arquitectura del Sistema

El framework sigue una arquitectura limpia en capas desacopladas, asegurando modularidad, testabilidad y mantenibilidad:

```text
QA_AUTOMATIZACIÓN/
├── normalizer/                 # Pipeline de Normalización Cognitiva con IA
│   ├── extract.py              # Ingestión cruda de texto, metadatos y capturas
│   ├── gaps.py                 # Detección determinista de datos faltantes (rules.yaml)
│   ├── grounding.py            # Verificación anti-alucinaciones por coincidencia exacta
│   ├── schema.py               # Esquema canónico validado en Pydantic v2
│   ├── render.py               # Generador de especificaciones canónicas .docx
│   ├── cli.py                  # Interfaz de línea de comandos unificada del normalizador
│   └── providers/              # Proveedores desacoplados de inferencia (AgentFile, API)
│       ├── masking.py          # Enmascaramiento criptográfico de secretos y PII
│       ├── protocol.py         # Protocolo de proveedor normalizador (NormalizerProvider)
│       ├── agent_file.py       # Proveedor local basado en artefactos JSON
│       └── api.py              # Proveedor agnóstico de modelo con fail-safe
├── runners/                    # Motor de Ejecución Documental
│   └── doc_runner.py           # Dispatcher Playwright, gating de normalización y variables de entorno
├── reporting/                  # Generación de Evidencias y Reportería Dual
│   ├── pdf_reporter.py         # Reportes ejecutivos PDF (ReportLab Platypus) con capturas
│   └── allure_reporter.py      # Telemetría de pruebas Allure 2 JSON con sanitización de errores
├── pageobjects/                # Implementaciones del Page Object Model (POM)
│   ├── login_page.py           # Autenticación, selectores privados y esperas explícitas
│   └── user_management_page.py # Flujos de mantenimiento de usuarios (Sys2000)
├── apiclients/ & mocks/        # Clientes HTTP y simulaciones en memoria (FastAPI)
├── tests/                      # Suite Integral de Pruebas (227 pruebas automatizadas)
│   ├── unit/                   # Pruebas unitarias de esquemas, normalizador, tipado y reportería
│   ├── integration/            # Pruebas de integración de runners, providers y reporte dual
│   └── e2e/                    # Pruebas de navegador en vivo con Playwright
├── openspec/                   # Gobernanza de Arquitectura: Spec-Driven Development (SDD)
│   ├── specs/                  # Especificaciones canónicas vivas del sistema
│   ├── changes/archive/        # Trazabilidad histórica de cambios completados con ISO date
│   └── config.yaml             # Configuración de herramientas, linters y capacidades de testing
├── .agents/                    # Subagentes autónomos de ingeniería (Antigravity)
│   ├── agents/                 # Roles especializados (test-normalizer, test-writer, code-auditor, pipeline-engineer)
│   └── skills/                 # Habilidades operativas (pom-conventions, secrets-and-pii, canonical-test-format)
├── .github/workflows/ci.yml    # Pipeline multi-OS (Ubuntu y Windows) en GitHub Actions
├── pyproject.toml              # Configuración centralizada de Mypy y Ruff
├── pytest.ini                  # Configuración de suite de pruebas y marcadores
└── requirements.txt            # Dependencias del proyecto en Python 3.13
```

---

## 🛡️ Seguridad, Privacidad y Gobernanza de Datos (PII)

En entornos corporativos y aseguradores, el envío inadvertido de información confidencial a proveedores externos de IA representa un riesgo inaceptable. Este sistema implementa defensas a nivel de diseño:

### 1. Enmascaramiento Unidireccional de Secretos y PII
Antes de serializar cualquier información para un modelo de lenguaje o persistirla en logs de ejecución, el módulo [`normalizer/providers/masking.py`](normalizer/providers/masking.py) aplica expresiones regulares compiladas que reemplazan los datos reales por marcadores estables:
- **Credenciales y Contraseñas**: Claves en texto plano o entrecomilladas (`password: "secreto 123"`) $\rightarrow$ `password: [REDACTED]`.
- **Autenticación en URLs**: `https://usuario:clave@servidor.empresa/api` $\rightarrow$ `https://usuario:[REDACTED]@servidor.empresa/api`.
- **Identificación Venezolana**: Cédulas de identidad con o sin formato (`V-12.345.678`, `E87654321`) y RIFs jurídicos/personales (`J-12345678-9`) $\rightarrow$ `[CEDULA_1]`, `[RIF_1]`.
- **Tokens de Sesión**: JWTs en formato base64 (`eyJ...`) $\rightarrow$ `[JWT_1]`.
- **Correos Electrónicos**: Direcciones corporativas o de clientes $\rightarrow$ `[EMAIL_1]`.

> [!IMPORTANT]
> **Modo `--dry-run` para Auditoría**: Permite exportar exactamente el texto enmascarado que se enviaría a la IA dentro de un directorio seguro (`build/<id>/`, excluido de Git), garantizando que los equipos de ciberseguridad puedan auditar la sanitización sin realizar ninguna llamada de red.

### 2. Grounding Anti-Alucinaciones
Para evitar que un modelo de IA invente selectores, URLs o credenciales no presentes en el documento original, el módulo [`normalizer/grounding.py`](normalizer/grounding.py) impone tres reglas estrictas:
1. **Citas Obligatorias (`source_quote`)**: Cada paso normalizado debe incluir la cita textual de donde provino, con una longitud mínima de 8 caracteres para evitar coincidencias triviales.
2. **Coincidencia Exacta**: La cita debe ser una subcadena literal del texto extraído del documento original (ya enmascarado).
3. **No-Invención de URLs ni Contraseñas**: Las URLs de destino deben coincidir de forma completa (o compartir el mismo host/origen) con las declaradas en el documento; las contraseñas que no estén documentadas no pueden ser inventadas y deben marcarse como datos faltantes.

### 3. Pre-Flight Normalization Gate (Fallo Seguro)
Cuando el documento presenta ambigüedades críticas (por ejemplo, falta la URL del entorno, faltan las credenciales requeridas o un paso no es ejecutable de forma determinista), el normalizador asigna el estado `NEEDS_INFO` o `UNSUPPORTED`.
El motor de ejecución ([`runners/doc_runner.py`](runners/doc_runner.py)) evalúa este estado antes de iniciar el navegador:
- Si el caso no está en estado `READY`, **el runner no abre el navegador**, muestra el reporte de faltantes generado (`.gaps.md`) y finaliza de inmediato con código de salida `2`.
- Esto previene falsos positivos y ejecuciones erráticas en pipelines desatendidos.

---

## 🚀 Capacidades y Flujos de Ejecución

### 1. Flujo Completo de Normalización de Pruebas

Si se recibe un archivo Word (`.docx`) o PDF con instrucciones manuales:

#### Paso 1: Extracción de Contenido Crudo
Extrae el texto secuencial, tablas, metadatos y capturas de pantalla embebidas:
```bash
python -m normalizer.extract "docs-qa/matriz_prueba_transferencias.docx" --out "build/dump"
```

#### Paso 2: Normalización con IA o Proveedor Local
El subagente `test-normalizer` procesa el volcado y produce el esquema canónico estructurado en formato JSON:
```bash
# Ejecución vía CLI con proveedor de IA (soporta --dry-run para auditoría de seguridad previa)
python -m normalizer.cli normalize "docs-qa/matriz_prueba_transferencias.docx" --provider api --dry-run
```

#### Paso 3: Validación de Esquema y Grounding
Verifica que la salida cumpla el contrato Pydantic v2 y no presente alucinaciones:
```bash
python -m normalizer.cli validate "normalized/matriz_prueba_transferencias.json"
```

#### Paso 4: Renderizado Canónico
Produce el documento canónico `.docx` de prueba individual y su respectivo informe de faltantes (`.gaps.md`):
```bash
python -m normalizer.cli render "normalized/matriz_prueba_transferencias.json" --out "normalized/"
```

---

### 2. Ejecución Automatizada y Reportería Dual

Una vez obtenido el caso normalizado en estado `READY`:

```bash
python -m runners.doc_runner \
  --doc "normalized/R-055429-caso1.docx" \
  --output-report "artifacts/reporte_ejecutivo.pdf" \
  --allure-dir "artifacts/allure-results" \
  --headed
```

#### Salidas Generadas:
1. **Reporte Ejecutivo PDF (`reporte_ejecutivo.pdf`)**: Diseñado con ReportLab Platypus, incluye cabecera formal, resumen de estados, métricas de duración, tabla detallada de pasos y miniaturas (*thumbnails*) de las capturas de pantalla tomadas en cada interacción.
2. **Resultados Allure 2 (`artifacts/allure-results/`)**: Archivos JSON estándar (`*-result.json`, `*-container.json`) que mapean cada paso con su estado (`passed`, `failed`, `broken`), tiempos en milisegundos, trazas de excepción con datos sensibles enmascarados y capturas completas en formato PNG.

Para visualizar el tablero de control de Allure:
```bash
allure serve artifacts/allure-results
```

---

### 3. Ejecución de la Suite de Pruebas Automatizadas

El framework incluye 227 pruebas automatizadas que certifican cada componente:

- **Pruebas Rápidas (Smoke & API)**:
  ```bash
  pytest -m "smoke or api" -v
  ```
- **Pruebas Unitarias e Integración (sin dependencias de red externas)**:
  ```bash
  pytest tests/unit tests/integration -q
  ```
- **Verificación de Tipado Estático Estricto (Mypy)**:
  ```bash
  python -m mypy
  ```
- **Inspección de Estilo y Reglas de Código (Ruff)**:
  ```bash
  ruff check .
  ```
- **Reporte de Cobertura de Código**:
  ```bash
  pytest --cov=normalizer --cov=parsers --cov=reporting --cov=runners tests/unit/ tests/integration/
  ```

---

## ⚙️ Guía de Instalación y Requisitos

### Requisitos Previos
- **Python 3.13** (64-bit) instalado.
- **Git** instalado.
- Sistema operativo: **Linux**, **macOS** o **Windows** (soporte verificado en CI).

### Instalación Paso a Paso

1. **Clonar el Repositorio**:
   ```bash
   git clone https://github.com/Jvske-max/exelixi-qa-automation.git
   cd exelixi-qa-automation
   ```

2. **Crear y Activar el Entorno Virtual**:
   - En Linux / macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - En Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```

3. **Instalar Dependencias de Producción y Desarrollo**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Instalar los Navegadores de Playwright**:
   ```bash
   playwright install chromium
   ```

5. **Configurar Variables de Entorno Seguras**:
   Los casos de prueba normalizados expanden dinámicamente credenciales desde el entorno en lugar de almacenarlas en archivos:
   - Linux / macOS:
     ```bash
     export QA_USERNAME="usuario_qa_pruebas"
     export QA_PASSWORD="clave_segura_pruebas"
     ```
   - Windows (PowerShell):
     ```powershell
     $env:QA_USERNAME="usuario_qa_pruebas"
     $env:QA_PASSWORD="clave_segura_pruebas"
     ```

---

## 📊 Métricas de Calidad del Proyecto

| Indicador | Estado / Resultado | Descripción |
|---|---|---|
| **Total de Pruebas** | **227 pasadas (100%)** | Pruebas unitarias y de integración en ~28s de ejecución |
| **Tipado Estático** | **0 errores (28 módulos)** | Verificado con `mypy` en Python 3.13 bajo configuración estricta |
| **Linter & Formato** | **0 advertencias** | Verificado con `ruff` (`line-length = 100`) |
| **Integración Continua** | **Multi-OS Matrix** | GitHub Actions ejecutando pruebas simultáneamente en Ubuntu y Windows |
| **Gobernanza SDD** | **OpenSpec v1** | 5 especificaciones canónicas vivas y 5 cambios archivados con auditoría formal |
| **Auditoría de Seguridad** | **Auditado por `code-auditor`** | Auditoría interna automatizada con subagente de IA: cero contraseñas expuestas, cero URLs de producción, enmascaramiento activo de PII |

---

## 🤖 Ingeniería Asistida por Agentes (Antigravity)

El desarrollo del proyecto siguió la metodología **Spec-Driven Development (SDD)** orquestada mediante subagentes especializados de **Google Antigravity**, integrando habilidades modulares (*skills*):
- `test-normalizer`: Subagente cognitivo que procesa volcados de documentos libres y genera el JSON canónico verificando el vocabulario de acciones y el grounding.
- `test-writer`: Subagente responsable de generar Page Objects y pruebas unitarias/integración bajo la metodología **Test-Driven Development (TDD estricto)**: ciclo Rojo $\rightarrow$ Verde $\rightarrow$ Refactorización.
- `code-auditor`: Subagente adversario que audita cada commit verificando la ausencia de secretos, selectores privados en Page Objects y ausencia total de `time.sleep()`.
- `pipeline-engineer`: Subagente encargado del aprovisionamiento de dependencias, scripts de benchmarking y configuración del flujo de CI/CD.

---

## 👤 Información del Autor

**Fernando José Silva Trejo**  
*Ingeniería de Software / Automatización QA / Inteligencia Artificial Aplicada*  
- **Proyecto:** Proyecto de pasantías desarrollado para la empresa **ExelixiTech, C.A.**, enfocado en automatización avanzada de pruebas, normalización cognitiva de especificaciones asistida por IA y observabilidad integral.  
- **Repositorio:** [github.com/Jvske-max/exelixi-qa-automation](https://github.com/Jvske-max/exelixi-qa-automation)
