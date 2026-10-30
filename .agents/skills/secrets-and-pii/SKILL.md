---
name: secrets-and-pii
description: Reglas y directivas de detección, enmascaramiento y auditoría de secretos y datos personales (PII) en automatización QA.
---

# Directivas de Seguridad: Secretos y Datos Personales (PII)

## Alcance del enmascarado
El enmascaramiento automático protege:
- Credenciales y contraseñas (en texto plano o entrecomilladas)
- Correos electrónicos
- Cédulas de identidad (con y sin puntos, ej. `V-12.345.678` y `V-12345678`)
- RIF (`J-...`, `G-...`, `V-...`, `E-...`)
- Tokens JWT (`eyJ...`)

> [!WARNING]
> **Limitación de cobertura:** El enmascarado **NO** cubre nombres de personas, números de póliza, teléfonos ni nombres de servidores internos. Estos datos deben ser tratados con discreción por los analistas o reemplazados por datos sintéticos de prueba.

## Reglas obligatorias
1. Ningún secreto ni dato personal real debe ser persistido en código fuente, fixtures de prueba, commits de Git, reportes públicos ni trazas de error.
2. Todas las credenciales en especificaciones normalizadas deben usar referencias a variables de entorno (`${QA_USER_<ROL>}`, `${QA_PASS_<ROL>}`).
3. En proveedores externos o llamadas API, los datos sensibles deben sustituirse por marcadores estables (`[EMAIL_N]`, `[CEDULA_N]`, etc.) antes de la transmisión.
4. Las capturas de pantalla visuales no admiten enmascarado automático; su transmisión debe ser siempre explícita (`--with-images`).
5. El archivo generado por `--dry-run` se escribe exclusivamente en `build/<id>/` (ruta ignorada por Git) y nunca en carpetas versionadas.
