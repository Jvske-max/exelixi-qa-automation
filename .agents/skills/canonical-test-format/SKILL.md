---
name: canonical-test-format
description: Formato canónico de prueba que lee parsers/docx_parser.py, vocabulario cerrado de acciones, tipos de faltante y estados. Úsala al normalizar, validar o renderizar pruebas.
---

# Formato canónico (lo que DocParser ya entiende)
Un archivo por caso. Tabla "Identificación" con: Fecha, Módulo, Identificador del caso, Descripción corta, Descripción completa, Ambiente de prueba, Analista Programador, Analista de prueba y Estado de normalización. Después, un párrafo por línea:
- `Link: <url>`
- `Caso N: <título>`  (debe ir antes de cualquier otro párrafo que contenga la palabra "caso")
- `Objetivo de la Prueba: <texto>`
- `Usuario: ${QA_USER_ROL}` y `Clave: ${QA_PASS_ROL}`
- `Paso N: <acción>`

Nunca escribas `Usuario:` ni `Clave:` dentro de un paso.

# Vocabulario cerrado
| Acción | Forma del paso | Ejemplo en el relato |
| --- | --- | --- |
| navigate | `Paso N: navegar a <url>` | "Ingresamos al link de la prueba" |
| fill | `Paso N: escribir <valor> en <campo>` | "Colocamos el código en el campo Código" |
| click | `Paso N: clic en <texto visible>` | "Pulsamos Emitir" |
| verify | `Paso N: verificar <texto visible>` | "Se muestra el mensaje Pago procesado" |
| manual | `Pendiente manual N: <motivo>` (nunca `Paso`) | subir archivos, descargas, OTP, pasarelas, correo, SISIP |

Un desplegable son dos `click`. Lo que no encaje es `manual`; nunca fuerces un verbo.

Un paso manual jamás se escribe como Paso N:: el parser lo ejecutaría como un clic sobre ese texto. Se escribe como Pendiente manual N:, que el parser ignora.

# Faltantes
| Tipo | Severidad | Cuándo | Qué se le pide al usuario |
| --- | --- | --- | --- |
| missing_url | blocking | No hay `Link:` ni URL en el caso ni en la cabecera | Añadir `Link: https://...` en el caso N |
| missing_credentials | blocking | Hay un paso de inicio de sesión y no hay usuario | Indicar el usuario de prueba; la clave va en `.env` como `QA_PASS_<ROL>` |
| credentials_in_plaintext | warning | El original trae una clave escrita | Cambiar esa clave y moverla a `.env` |
| missing_expected | warning | Una verificación dice solo "funciona correctamente" | Escribir qué texto o estado se espera |
| ambiguous_step | blocking si falta el elemento | La frase no dice qué elemento se usa | Nombrar el botón o campo tal como se ve |
| data_in_screenshot | warning | El dato está solo en una captura o no se lee bien | Escribir el dato de prueba (ficticio) en texto |
| unsupported_flow | info | OTP, pasarela de pago, correo, SISIP, subida de archivos | Nada; el paso queda como pendiente manual |

# Estados
- NEEDS_INFO: hay al menos un faltante blocking.
- UNSUPPORTED: no queda ningún paso ejecutable.
- READY: ninguno de los dos.

# Citas
Todo paso lleva `source_quote` copiado literal del original. Si la cita no existe en el texto del original, el paso se rechaza.