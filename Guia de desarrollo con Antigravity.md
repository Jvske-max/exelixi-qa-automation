# Guia de desarrollo con Antigravity

Oct 8, 2026 - @Fernando

## Resumen

Este documento traduce el roadmap de 8 fases que ya definimos en una guía operativa para construirlo con **Antigravity CLI** — el agente de terminal de Google (lanzado el 19 de mayo de 2026, sucesor de Gemini CLI) que vas a usar como cerebro del desarrollo.

Antigravity soporta de forma nativa tres mecanismos que vamos a aprovechar aquí:

- **Sub-agentes**: procesos concurrentes y especializados — uno escribe tests, otro revisa seguridad, otro investiga el código — que corren en paralelo sin bloquear tu sesión principal.
- **Skills**: paquetes de instrucciones reutilizables que el agente lee automáticamente cuando detecta que son relevantes para la tarea.
- **Hooks**: scripts que se disparan en puntos del ciclo de ejecución del agente — por ejemplo, correr pytest después de cada archivo editado, la pieza que conecta Antigravity con la idea de continuous testing que es el corazón de tu tesis.

Cada sección siguiente configura una pieza, mapeada directamente a las fases de tu roadmap.

## Configuración inicial del entorno

Instala el binario `agy` (así se llama el comando real de Antigravity CLI):

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Al lanzar `agy` por primera vez se abre tu navegador para autenticarte con tu cuenta de Google; en sesiones remotas por SSH, el CLI te muestra una URL y un código para pegar manualmente.

Crea esta estructura dentro de tu repositorio del framework de pruebas. La carpeta `.agents/` es la que Antigravity lee automáticamente, y conviene subirla a git para que el piloto en Exelixi quede versionado:

```
qa-automation/
├── .agents/
│   ├── agents/          # sub-agentes personalizados
│   ├── skills/           # skills reutilizables
│   └── hooks.json         # hooks del ciclo de vida
├── tests/
│   ├── e2e/
│   ├── api/
│   └── conftest.py
├── pageobjects/
├── apiclients/
├── requirements.txt
└── pytest.ini
```

Con esto listo, `agy` reconoce tus sub-agentes y skills apenas abras una sesión dentro de esta carpeta.

## Arquitectura del framework y su mapeo a Exelixi

&#91;embedded content: arquitectura en capas · 5 niveles\]

Cada capa de la arquitectura solo conoce la inmediatamente inferior: los casos de prueba nunca llaman directo a Playwright, siempre pasan por un Page Object o un cliente de API.

## Sub-agentes recomendados

Antigravity trae tres sub-agentes integrados (`research`, `browser`, `self`) y te deja definir los tuyos en archivos Markdown. Estos son los que recomiendo para tu proyecto:

| Sub-agente | Para qué sirve | Fase | Cómo activarlo |
| --- | --- | --- | --- |
| `research` (integrado) | Explorar el código de Exelixi y mapear flujos críticos | Fase 0 | Automático, no requiere configuración |
| `test-writer` | Escribe Page Objects, clientes de API y casos de prueba siguiendo POM | Fase 3 | `.agents/agents/test-writer.md` |
| `pipeline-engineer` | Diseña y ajusta workflows de GitHub Actions y Docker | Fase 4 | `.agents/agents/pipeline-engineer.md` |
| `code-auditor` | Revisa seguridad y calidad antes de integrar a CI/CD | Fase 4 | `.agents/agents/code-auditor.md` |
| `flaky-hunter` | Diagnostica y corrige tests inestables | Fases 5 y 6 | `.agents/agents/flaky-hunter.md` |
| `browser` (integrado) | Pruebas interactivas de UI en un navegador aislado | Fase 3 | Invócalo con `/browser` |

### Ejemplo: test-writer

Guarda esto en `.agents/agents/test-writer.md`:

```markdown
---
name: test-writer
description: Escribe Page Objects, clientes de API y casos de prueba pytest+Playwright siguiendo el patrón establecido en pageobjects/ y apiclients/. Úsalo al implementar nuevos casos de prueba del framework.
tools:
  - view_file
  - replace_file_content
  - write_to_file
  - run_command
subagent: true
mainAgent: false
model: pro
commandExecutionPolicy: sandbox
skills:
  - skills/pom-conventions
---

# System Prompt
Eres un ingeniero de QA automation experto en Playwright y pytest, y en el patrón Page Object Model. Antes de escribir un test nuevo, revisa los Page Objects y clientes de API existentes para reutilizar convenciones.

# Reglas
1. Nunca hardcodees credenciales ni URLs de producción.
2. Cada test necesita un caso positivo y al menos un caso negativo.
3. Usa los marcadores smoke, api o e2e según corresponda.
```

## Skills recomendadas

Cada skill vive en una carpeta con un archivo SKILL.md. Antigravity la convierte automáticamente en un comando como /pom-conventions, y el agente la lee solo cuando detecta que aplica a la tarea.

| Skill | Qué hace | Se activa cuando |
| --- | --- | --- |
| `pom-conventions` | Documenta cómo nombrar y estructurar Page Objects y clientes de API | El agente crea o revisa un test |
| `bug-report-format` | Convierte un fallo de test en un reporte de bug con tu formato de Exelixi | Un test automatizado falla |
| `cicd-workflow-patterns` | Plantillas probadas de GitHub Actions: smoke en cada push, regresión nocturna, publicación de Allure | El agente genera o modifica un workflow |
| `insurance-domain-glossary` | Glosario del dominio asegurador — póliza, prima, siniestro, RCV | El agente escribe datos o casos de prueba |

### Ejemplo: pom-conventions

Guarda esto en `.agents/skills/pom-conventions/SKILL.md`:

```markdown
---
name: pom-conventions
description: Documenta las convenciones del Page Object Model usadas en este proyecto. Úsala al crear o revisar cualquier Page Object nuevo.
---

# Convenciones de Page Objects

1. Una clase por pantalla o flujo (LoginPage, FormularioEmisionPage).
2. Los selectores van como atributos privados al inicio de la clase, nunca dentro de los métodos.
3. Cada método público representa una acción del usuario, no un paso técnico.
4. Las esperas son siempre explícitas, nunca con sleep.
```

## Flujo de trabajo fase por fase con Antigravity

&#91;embedded content: roadmap de 4 etapas · un sub-agente por etapa\]

Cada etapa tiene un sub-agente protagonista: usa research para explorar Exelixi, test-writer para construir el framework, pipeline-engineer para el pipeline, y flaky-hunter para el piloto final. Así no improvisas con cuál invocar en cada momento.

## Primer caso concreto: mock de FastAPI para OCR

El módulo de OCR es buen candidato para tu primer mock: es el más propenso a fallar por causas ajenas a tu código (el documento no es legible, el proveedor está lento). Aislarlo con un servicio FastAPI controlado por ti hace que tus pruebas sean deterministas.

Pídele esto al sub-agente test-writer:

> Crea un servicio mock con FastAPI en mocks/ocr\_service.py que simule el endpoint de reconocimiento de documentos. Necesito tres rutas: una que devuelva una extracción exitosa con datos de cédula de ejemplo, una que devuelva un error 422 simulando un documento ilegible, y una que simule un timeout de 10 segundos. Documenta cada ruta con un comentario explicando qué caso de Exelixi representa.

Un punto de partida de lo que debería generar:

```python
from fastapi import FastAPI, HTTPException
import asyncio

app = FastAPI()

@app.post('/ocr/extraer')
async def extraccion_exitosa():
    # Caso feliz: documento legible, datos completos
    return {'cedula': 'V-12345678', 'nombre': 'Usuario Prueba', 'confianza': 0.97}

@app.post('/ocr/extraer/ilegible')
async def documento_ilegible():
    # Simula un documento borroso o mal escaneado
    raise HTTPException(status_code=422, detail='No se pudo extraer texto del documento')

@app.post('/ocr/extraer/timeout')
async def proveedor_lento():
    # Simula al proveedor de OCR real respondiendo tarde
    await asyncio.sleep(10)
    return {'cedula': None}
```

Corre el mock localmente con `uvicorn mocks.ocr_service:app --port 8001`, y en tus fixtures de pytest apunta OCR\_SERVICE\_URL a http://localhost:8001 solo en el entorno de pruebas — nunca al proveedor real. Así cada test de emisión que dependa de OCR es rápido, gratis y 100% reproducible.

## Buenas prácticas, límites y seguridad

- Nunca apuntes a producción: usa siempre una URL de staging y credenciales de un usuario de prueba dedicado.
- Deja commandExecutionPolicy: sandbox en los sub-agentes que ejecutan comandos, sobre todo los que tocan git o despliegues.
- Revisa siempre el diff antes de aprobar un commit — Antigravity no reemplaza tu juicio, menos en un sistema de seguros en producción.
- Antes de un git push o una migración de base de datos, puedes definir un hook PreToolUse con decision ask, para que el agente pida confirmación explícita en vez de ejecutar solo.
- El anidamiento de sub-agentes tiene un límite de 10 niveles; no es un problema real aquí, pero conviene saberlo.

El hook más valioso para este proyecto corre las pruebas smoke automáticamente cada vez que el agente edita un archivo. Guarda esto en `.agents/hooks.json`:

```json
{
  "auto-smoke-test": {
    "PostToolUse": [
      { "matcher": "write_to_file|replace_file_content", "hooks": [{ "command": "pytest -m smoke -q", "timeout": 60 }] }
    ]
  }
}
```

Con esto, cada edición del agente se autoexamina al instante: es, literalmente, continuous testing aplicado a tu propio flujo de desarrollo con el agente.

## Checklist de arranque: primeros prompts

Pégalos en `agy`, en orden, dentro de la carpeta del proyecto:

- [ ] 1\. Pide: crea la estructura de carpetas tests/e2e, tests/api, pageobjects, apiclients, y un requirements.txt con pytest, pytest-playwright, playwright, requests y allure-pytest.
- [ ] 2\. Crea `.agents/agents/test-writer.md` con el contenido de la sección anterior, luego pide: usando el sub-agente test-writer, escribe un test de login que replique tu caso manual del documento Word.
- [ ] 3\. Pide: revisa con el sub-agente code-auditor el test que acabas de generar, antes de correrlo.
- [ ] 4\. Pide: genera un workflow de GitHub Actions en .github/workflows/ci.yml que instale las dependencias, los navegadores de Playwright, y corra pytest -m smoke en cada push.
- [ ] 5\. Crea `.agents/hooks.json` con el hook auto-smoke-test de la sección anterior.
- [ ] 6\. Escribe /agents y confirma en el panel que test-writer aparece disponible.
