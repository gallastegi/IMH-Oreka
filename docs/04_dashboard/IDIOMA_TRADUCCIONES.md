# Idioma y traducciones

## Selector de idioma

La app muestra un selector compacto en la barra lateral:

```text
Idioma: Castellano / Euskera
```

La seleccion se guarda en `st.session_state["language"]` con codigos internos:

- `es`: Castellano
- `eu`: Euskera

La navegacion no guarda el texto visible traducido. Guarda claves internas
estables como `odoo`, `planning`, `operational_performance`, `analysis`,
`config` y `explore`, por lo que
cambiar de idioma no debe mover al usuario a otra pantalla.

## Archivo de traducciones

Las traducciones se guardan en:

```text
config/prc01_translations.csv
```

Columnas:

```text
key
context
text_es
text_eu
notes
active
updated_at
```

Si el archivo no existe, la app lo crea con una base inicial de claves para
navegacion, analisis, planificacion, informes y columnas visibles.

## Configuracion / Idioma

En Streamlit, `Configuracion / Idioma` permite:

- editar traducciones en castellano, euskera o ambos;
- activar/desactivar claves;
- guardar cambios en CSV;
- detectar claves base que falten y anadirlas sin borrar las existentes.

Los subapartados de Configuracion usan claves internas estables:
`management_classification`, `available_hours`, `workload` y `language`.

## Fallback

La resolucion de texto sigue este orden:

1. texto del idioma seleccionado;
2. `text_es`;
3. valor por defecto indicado por el codigo;
4. clave tecnica.

## Nombres internos y visuales

La traduccion solo afecta a la presentacion:

- etiquetas de app;
- titulos;
- botones;
- cabeceras visuales de tablas;
- secciones de informes;
- valores funcionales de la clasificacion de gestion.

No cambia:

- nombres internos de columnas;
- nombres de ficheros;
- datos originales de proyectos, tareas o personas;
- CSV tecnicos de salida.

## Meses

Los meses se traducen visualmente con claves `month.01` a `month.12`.

Ejemplos:

- `month.01`: `Enero` / `Urtarrila`
- `month.06`: `Junio` / `Ekaina`

Los selectores usan internamente el numero de mes, pero muestran `01 - Enero`
o `01 - Urtarrila` segun idioma.

## Columnas internas visibles

Las cabeceras tecnicas se traducen antes de mostrar tablas en pantalla.
Ejemplos:

- `hilabete_zk`: `N. mes` / `Hilabete zk.`
- `mes_label`: `Mes` / `Hilabetea`
- `available_hours_base`: `Horas base disponibles` / `Oinarrizko ordu erabilgarriak`
- `data`: `Fecha` / `Data`
- `grupo_gestion`: `Unidad destino + naturaleza` / `Helmuga unitatea + izaera`
- `unidad_destino_label`: `Unidad destino` / `Helmuga unitatea`
- `naturaleza_trabajo_label`: `Naturaleza del trabajo` / `Lanaren izaera`

Para nuevas columnas visibles, usar claves `column.<nombre_columna>`.

## Selector de grafico

Las etiquetas visuales del tipo de grafico se traducen con:

- `app.chart.monthly_label`: `Barras mensuales` / `Hileko barrak`
- `app.chart.pareto_label`: `Pareto` / `Pareto`

El valor interno sigue siendo `monthly` o `pareto`.

En Planificacion el selector usa tres valores internos estables:

- `monthly`
- `pareto`
- `person_load`

Las etiquetas visibles se traducen con:

- `planning.monthly_label`
- `planning.pareto_label`
- `planning.person_load_label`

La agrupacion se controla de forma independiente con `app.chart.group_by` y las
claves existentes de unidad destino, naturaleza, proyecto y persona.

En Rendimiento operativo se usan valores internos estables:

- vistas: `summary`, `planned_vs_actual`, `people_load`;
- graficos: `comparison`, `deviation`, `overconsumption_pareto`, `unplanned_actuals`;
- dimensiones: `project_name`, `person_name`, `month`, `department_name`, `grupo_gestion`.

Las etiquetas visibles se traducen con claves `operational.*` y columnas
`column.planned_hours`, `column.actual_hours`, `column.deviation_hours`,
`column.actual_hours_with_planning`, `column.actual_hours_without_planning`,
`column.occupation_planned_pct` y `column.occupation_actual_pct`.

## Conexion y descarga

La vista de conexion usa una unica accion principal traducida con:

- `odoo.connection.download_rebuild`

El resumen de ejecucion usa:

- `odoo.connection.updated_ok`
- `odoo.connection.records_downloaded`
- `odoo.connection.hours_downloaded`
- `odoo.connection.data_period`
- `odoo.connection.pending_classification`
- `odoo.connection.last_update`
- `odoo.connection.technical_details`
- `odoo.connection.connecting`
- `odoo.connection.downloading`
- `odoo.connection.transforming`
- `odoo.connection.rebuilding`
- `odoo.connection.connection_failed`
- `odoo.connection.download_failed`

Los detalles tecnicos se muestran plegados y no incluyen credenciales.

## Planificacion

El modulo `Planificacion` usa claves en el contexto `planning`, metricas y
columnas especificas. La fuente de datos no es una decision de usuario, por lo
que no existen claves activas para seleccionar origen.

Claves principales:

- `app.nav.planning`
- `planning.title`
- `planning.summary`
- `planning.monthly_view`
- `planning.pareto_view`
- `planning.person_load_view`
- `planning.monthly_label`
- `planning.pareto_label`
- `planning.person_load_label`
- `planning.person_dimension_fallback`
- `planning.show_people_without_planning`
- `planning.people_in_scope`
- `planning.people_with_planning`
- `planning.people_without_planning`
- `planning.person_coverage_pct`
- `planning.with_planning`
- `planning.without_planning`
- `planning.without_availability`
- `planning.no_people_in_scope`
- `planning.people_scope_summary`
- `planning.generate_reports`
- `planning.overloads`
- `planning.risk`
- `planning.ok`
- `planning.overload`
- `planning.data`
- `planning.monthly_title`
- `metric.planned_hours`
- `metric.people_overloaded`
- `metric.people_at_risk`
- `metric.total_occupation_pct`
- `column.planned_hours`
- `column.source_system`
- `column.source_model`
- `column.source_name`

Las claves antiguas de carga manual o seleccion de origen fueron retiradas de la
base activa.

## Claves legacy

Las claves de la clasificacion anterior por `grupo_actividad` pueden seguir en
el CSV con `active = FALSE` y nota `LEGACY`. No se usan en la UI actual.

## Anadir nuevas claves

Para nuevas pantallas o informes:

1. anadir la clave a la lista base `REQUIRED_TRANSLATIONS`;
2. entrar en `Configuracion / Idioma`;
3. pulsar `Detectar textos sin traducir`;
4. completar `text_es` y `text_eu`;
5. guardar.

Para metricas visibles usar claves `metric.*`. Para secciones de configuracion
usar `config.*`. Para textos de la vista Odoo usar `odoo.connection.*`. Para el
generador de informes usar `reports.generator.*`.
