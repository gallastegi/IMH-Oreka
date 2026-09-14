Podemos gerenerar un modulo de subida de carga de trabajo desde un excel.
    Proyecto
    Tarea
    Persona
    Horas planificadas
Y se añaden a proyectos ya creados. Esto va a facilitar mucho la planificacion




Sumar una gestion de areas de conocimiento en tareas y capacidades de personal de esta forma la accion de replanificar tareas se peude automatizar


## PRC-01 - Rendimiento operativo

MVP implementado como modulo separado de lectura y analisis:

- compara planificacion (`project.forecast`) y horas reales (`account.analytic.line`);
- conserva horas reales sin planificacion;
- calcula desviacion, cobertura, ejecucion, planificacion no ejecutada y ocupacion;
- no incluye datos economicos ni KPIs de facturacion/margen;
- deja preparada la arquitectura para un futuro rendimiento economico con fuentes especificas.

Comandos:

```powershell
python scripts\02_transform\24_build_prc01_operational_performance.py
streamlit run apps\streamlit\prc01_horas_imputadas.py
```
