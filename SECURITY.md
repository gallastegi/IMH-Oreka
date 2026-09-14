# Seguridad de datos

IMH Oreka procesa datos internos de planificación y actividad. El repositorio contiene exclusivamente código y plantillas ficticias.

No se deben versionar:

- credenciales, tokens, certificados o archivos `.env`;
- URLs y nombres de bases de datos internas;
- exportaciones de Odoo o datasets derivados;
- nombres, identificadores o cargas reales de personas;
- nombres y tareas de proyectos reales;
- informes, logs o resultados de auditoría.

Guarda los valores privados en `.env`, `config/*.local.csv` o las carpetas ignoradas bajo `data/`. Antes de compartir cambios, revisa `git status` y ejecuta la suite de pruebas.
