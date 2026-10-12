---
name: pom-conventions
description: Documenta las convenciones del Page Object Model usadas en este proyecto. Úsala al crear o revisar cualquier Page Object nuevo.
---

# Convenciones de Page Objects

1. Una clase por pantalla o flujo (LoginPage, FormularioEmisionPage).
2. Los selectores van como atributos privados al inicio de la clase, nunca dentro de los métodos.
3. Cada método público representa una acción del usuario, no un paso técnico.
4. Las esperas son siempre explícitas, nunca con sleep.
