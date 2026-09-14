# Rendimiento operativo PRC-01

## Objetivo

El modulo `Rendimiento operativo` compara planificacion, ejecucion real y capacidad
sin introducir indicadores economicos. Responde a:

- como funciona globalmente el ambito seleccionado;
- donde aparecen desviaciones y trabajo sin planificacion;
- como se distribuyen planificacion, ejecucion y capacidad entre personas.

## Fuentes

El MVP usa exclusivamente datasets procesados:

- `data/processed/17_prc01_planning_detail.csv`
- `data/processed/16_prc01_actuals_annual_detail.csv`
- `data/processed/18_prc01_operational_performance_detail.csv`

La planificacion procede de `project.forecast`. Las horas reales proceden de
`account.analytic.line`. No se escribe en Odoo.

## Contrato de datos

El dataset operativo se construye con:

```powershell
python scripts\02_transform\24_build_prc01_operational_performance.py
```

El grano del CSV 18 es persona + proyecto + tarea + mes, preservando trazabilidad
mediante `source_planning_rows` y `source_actual_rows`.

Columnas principales:

- `planned_minutes`, `planned_hours`;
- `actual_minutes`, `actual_hours`;
- `actual_minutes_with_planning`;
- `actual_minutes_without_planning`;
- `planned_minutes_not_executed`;
- `deviation_minutes`, `deviation_hours`, `deviation_pct`;
- `planning_coverage_pct`;
- `planning_execution_pct`;
- `match_quality`, `match_status`;
- `unidad_destino`, `naturaleza_trabajo`, `grupo_gestion`.

Los calculos internos usan minutos cuando procede y se presentan en horas.

## Asociacion planificado-real

Cada linea real se asigna como maximo una vez. La prioridad es:

1. persona + proyecto + tarea + periodo;
2. persona + proyecto + periodo;
3. persona + tarea + periodo;
4. sin planificacion.

Si hay varios forecast candidatos con la misma prioridad, el sistema elige de
forma determinista el intervalo mas especifico y registra el conflicto en:

```text
data/reports/prc01_operational_match_conflicts.csv
```

Las horas reales sin planificacion se conservan como ejecucion real, no se
descartan ni se reparten artificialmente.

## Formulas

```text
desviacion = horas reales - horas planificadas
cobertura planificacion = horas reales con planificacion / horas reales
ejecucion planificacion = horas reales con planificacion / horas planificadas
planificacion no ejecutada = max(planificadas - reales con planificacion, 0)
sobreconsumo = max(reales - planificadas, 0)
```

La identidad principal es:

```text
reales con planificacion + reales sin planificacion = reales totales
```

## Filtros

El modulo reutiliza el patron de Planificacion y Analisis:

- Ano;
- Departamento;
- Grupo interno / subdepartamento;
- Inicio y fin de periodo;
- Unidad destino;
- Naturaleza del trabajo;
- Unidad destino + naturaleza;
- Persona;
- Proyecto y tarea en filtros avanzados.

La poblacion organizativa se deriva de la misma base usada por Analisis de
datos, y la disponibilidad se resuelve con `prc01_available_hours.csv` y
`prc01_person_workload.csv`.

## Vistas

### Resumen

Muestra KPI ejecutivos:

- horas planificadas;
- horas reales;
- desviacion;
- cobertura de planificacion;
- horas reales sin planificacion;
- planificacion no ejecutada;
- proyectos con sobreconsumo;
- proyectos, personas y tareas.

Incluye tablas de sobreconsumo y trabajo sin planificacion.

### Planificado vs real

Incluye selector de dimension y selector horizontal de visualizacion:

- Planificado vs real;
- Desviacion;
- Pareto de sobreconsumo;
- Horas sin planificacion.

Solo se renderiza una visualizacion cada vez.

### Personas y carga

Combina:

- horas disponibles;
- horas planificadas;
- horas reales;
- ocupacion planificada;
- ocupacion real;
- cobertura de planificacion;
- mix directo/indirecto basado en `naturaleza_trabajo`;
- estado de carga.

No contiene facturacion, margen ni rentabilidad por persona.

## Diagnosticos

El transformador genera:

- `data/reports/prc01_operational_performance_diagnostics.csv`
- `data/reports/prc01_operational_match_conflicts.csv`
- `data/reports/prc01_operational_unplanned_actuals.csv`
- `data/reports/prc01_operational_unexecuted_planning.csv`
- `data/reports/prc01_operational_overconsumption.csv`
- `data/reports/prc01_operational_people_coverage.csv`
- `data/reports/prc01_operational_pending_classification.csv`

## Informes

La UI incluye el expander `Generar informes de rendimiento operativo`. El informe
crea una carpeta en:

```text
data/reports/prc01_operational_performance_reports/
```

con HTML, CSV, metadata y ZIP.

## Limitaciones del MVP

- El dataset procesado de horas reales no conserva actualmente el ID original de
  `account.analytic.line`; el modulo operativo genera un identificador estable
  derivado para evitar duplicacion.
- Los estados de proyecto son reglas iniciales pendientes de validacion
  organizativa.
- No se implementan indicadores economicos.
