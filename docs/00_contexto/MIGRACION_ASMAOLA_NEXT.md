# Migración de ASMAOLA Next a IMH Oreka

## Procedencia

IMH Oreka se creó como producto independiente a partir del MVP ASMAOLA Next del repositorio `https://gitlab.com/EHiNA/odoo_bi`.

- Commit de referencia del MVP: `d72188b`.
- Repositorio del producto: `https://github.com/gallastegi/IMH-Oreka`.
- Fecha de migración: 2026-09-14.

El repositorio de GitLab continúa siendo el MVP/legacy y no se modifica desde este proyecto.

## Decisiones de migración

- La marca visible pasa a ser **IMH Oreka**.
- El paquete Python cambia de `asmaola_next` a `imh_oreka`.
- Se conservan los identificadores PRC-01 porque describen el proceso de negocio, no la marca.
- Se conservan literalmente los nombres de proyectos y tareas procedentes de Odoo, aunque contengan “ASMAOLA”, para no alterar datos históricos ni reglas de clasificación.
- Los logs, auditorías personales, configuraciones reales y documentos históricos del MVP no se migran al repositorio nuevo. Permanecen exclusivamente en el GitLab legacy.
- `scripts/99_legacy/` conserva únicamente utilidades técnicas que no contienen datos ni credenciales.
- Los secretos y datos generados siguen excluidos del control de versiones.

## Saneamiento para GitHub

Antes de publicar se reconstruyó el historial de `main` desde una raíz limpia. El repositorio nuevo sólo contiene plantillas ficticias; no incluye commits anteriores con datos de Odoo, nombres de personas, proyectos reales ni logs operativos.

## Compatibilidad

No se mantiene un alias Python para `asmaola_next`: los consumidores deben importar `imh_oreka`. Esta ruptura deliberada evita que código nuevo dependa accidentalmente del nombre del MVP.
