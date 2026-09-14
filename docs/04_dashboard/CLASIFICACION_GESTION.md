# Clasificacion de gestion PRC-01

## Objetivo

La clasificacion de gestion es la clasificacion principal del analisis PRC-01. Sustituye visualmente a la clasificacion anterior por `grupo_actividad` y se basa en:

- `unidad_destino`: unidad, departamento o funcion a la que se imputan las horas.
- `naturaleza_trabajo`: forma en la que computan las horas.
- `grupo_gestion`: combinacion visual de ambas dimensiones.

Esta capa sirve para analizar carga, productividad y rentabilidad por unidad destino y por trabajo directo, indirecto o no aplicable.

## Unidad destino

Las unidades se configuran en:

```text
config/prc01_management_units.csv
```

Valores iniciales:

- `ingeniaritza`
- `lanerako_prestakuntza`
- `incress`
- `proiektu_zerbitzu_teknikoak`
- `ekoizpena`
- `komertziala_marketina`
- `pertsonak_antolaketa`
- `gobernantza_barne_kudeaketa`
- `pendiente`

## Naturaleza del trabajo

Las naturalezas se configuran en:

```text
config/prc01_work_natures.csv
```

Valores iniciales:

- `directo`
- `indirecto`
- `no_aplica`
- `pendiente`

## Grupo de gestion

`grupo_gestion` se calcula en la app:

```python
grupo_gestion = unidad_destino_label + " ? " + naturaleza_trabajo_label
```

Ejemplos:

- `INGENIARITZA ? Directo`
- `PROIEKTUAK ETA ZERBITZU TEKNIKOAK ? Indirecto`
- `PERTSONAK ETA ANTOLAKETA ? No aplica`

## Relacion con la clasificacion anterior

La clasificacion anterior por `grupo_actividad` queda obsoleta para la UI, los filtros y los informes de usuario.

No se borra a lo bruto: la app puede conservar `grupo_actividad` o `grupo_actividad_original` como campo legacy interno para compatibilidad y auditoria. No debe mostrarse como dimension funcional actual.

## Reglas

Las reglas se configuran en:

```text
config/prc01_management_classification_rules.csv
```

Cada regla puede buscar texto en:

- proyecto,
- tarea,
- departamento,
- persona.

La app aplica reglas activas por prioridad ascendente. Si no hay coincidencia, asigna:

```text
unidad_destino = pendiente
naturaleza_trabajo = pendiente
classification_status = pendiente
```

## Edicion desde Streamlit

En la app:

```text
Configuracion > Clasificacion de gestion
```

se pueden editar:

- unidades destino,
- naturalezas de trabajo,
- reglas de clasificacion,
- verificacion proyectos/tareas.

Al guardar se actualiza el CSV local, se limpia cache y se recalcula la capa de gestion.

Las tablas permiten anadir filas nuevas. Al guardar:

- se eliminan filas vacias,
- se generan claves si faltan a partir de la etiqueta,
- se validan duplicados,
- se normaliza `active`,
- se actualiza `updated_at`.

En reglas, si `rule_id` esta vacio se genera el siguiente identificador `R###`. Si falta `priority`, se asigna al final. Las columnas `unidad_destino` y `naturaleza_trabajo` se validan contra los CSV de unidades y naturalezas.

## Colores

Los graficos usan una paleta estable por `unidad_destino`:

- cada unidad tiene un color base,
- `directo` usa un tono mas oscuro,
- `indirecto` usa el color base,
- `no_aplica` usa un tono mas claro,
- `pendiente` usa gris.

Esto permite identificar visualmente las barras de la misma unidad aunque cambie la naturaleza del trabajo.

## Verificacion proyectos/tareas

En:

```text
Configuracion > Clasificacion de gestion > Verificacion proyectos/tareas
```

se muestra una tabla agrupada por proyecto, tarea y departamento con:

- horas,
- numero de lineas,
- numero de personas,
- unidad destino,
- naturaleza,
- grupo de gestion,
- regla aplicada,
- estado de clasificacion.

La tabla permite filtrar por:

- todos / pendientes / clasificados,
- unidad destino,
- naturaleza,
- regla aplicada,
- busqueda de texto en proyecto, tarea, departamento, regla o grupo.

Tambien se puede descargar como CSV. La app genera automaticamente:

```text
data/reports/prc01_management_classification_review.csv
```

## Ejemplos

Ingenieria:

- proyectos o procesos de ingenieria docente directa: `ingeniaritza + directo`.
- preparacion, tutoria o correccion de ingenieria: `ingeniaritza + indirecto`.

Fabricacion avanzada / servicios tecnicos:

- tareas de desarrollo tecnico: `proiektu_zerbitzu_teknikoak + directo`.
- tareas de gestion tecnica: `proiektu_zerbitzu_teknikoak + indirecto`.

## Diagnostico

La app genera:

```text
data/reports/prc01_management_classification_diagnostics.csv
data/reports/prc01_management_classification_pending.csv
data/reports/prc01_management_classification_review.csv
```

El primer fichero resume filas clasificadas y pendientes. El segundo agrupa pendientes por proyecto, tarea, departamento, persona y horas. El tercero permite revisar la clasificacion aplicada por proyecto/tarea.

## Uso futuro

Esta clasificacion deja preparada la app para cruzar horas con datos economicos y calcular productividad o rentabilidad por unidad destino y naturaleza del trabajo.
