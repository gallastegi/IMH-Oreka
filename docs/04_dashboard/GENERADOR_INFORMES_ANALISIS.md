# Generador de informes de Analisis de datos

## Ubicacion

El generador esta en Streamlit, dentro de `Analisis de datos`, en el expander cerrado `Generar informes`.

## Tipos de informe

- `Mensual`: genera el informe para un mes concreto.
- `Anual`: usa enero-diciembre del ano seleccionado.
- `Entre meses`: permite elegir mes inicio y mes fin, ambos incluidos.

## Nivel de desglose

- `Solo vista actual`: genera un informe para el filtro aplicado en pantalla.
- `Vista actual + subniveles`: genera el informe global y subinformes por subdepartamento/departamento y persona cuando aplica.

Si el filtro actual contiene una sola persona, se genera solo el informe de esa persona.

## Clasificacion usada

Los informes usan la clasificacion de gestion:

- `unidad_destino`
- `naturaleza_trabajo`
- `grupo_gestion = unidad_destino + " ? " + naturaleza_trabajo`

La clasificacion anterior por `grupo_actividad` queda obsoleta y no se muestra en HTML ni en los CSV de usuario.

## Contenido generado

Cada informe HTML incluye:

- Cabecera con fecha, ano, periodo, alcance y filtros.
- Filtros aplicados en formato humano dentro de un bloque plegable.
- Resumen ejecutivo de horas imputadas, disponibles, diferencia y ocupacion.
- Grafico mensual por grupo de gestion con linea roja de horas disponibles.
- Grafico mensual por proyecto con Top N + Otros y linea roja de horas disponibles.
- Pareto por grupo de gestion.
- Pareto por proyecto con barras horizontales para leer nombres largos.
- Tabla de horas por unidad destino.
- Tabla de horas por naturaleza del trabajo.
- Tabla de horas por unidad destino + naturaleza.
- Tabla de horas por proyecto.
- Tabla proyecto x grupo de gestion.
- Detalle resumido, limitado a Top 500 filas si es necesario.

Los graficos incluyen hover simplificado con formato `Nombre | Horas: 1.234,50`.

## Idioma de generacion

El informe se genera en el idioma seleccionado en la barra lateral de Streamlit:

- Castellano (`es`)
- Euskera (`eu`)

Los textos visibles de secciones, cabeceras y valores funcionales se traducen usando `config/prc01_translations.csv`. Los nombres originales de proyectos, tareas y personas no se traducen.

## Archivos de salida

Cada generacion crea una carpeta:

```text
data/reports/prc01_analysis_reports/report_YYYYMMDD_HHMMSS/
```

Dentro se generan:

- `index.html`
- `department_global.html`
- `data_summary.csv`
- `project_hours.csv`
- `management_group_hours.csv`
- `unit_hours.csv`
- `work_nature_hours.csv`
- `project_management_matrix.csv`
- `metadata.json`
- HTML de subinformes cuando aplica.
- `prc01_analysis_report_YYYYMMDD_HHMMSS.zip`

El ZIP puede descargarse desde Streamlit con `Descargar informe ZIP`.

## Limitaciones actuales

- La salida prioritaria es HTML, CSV y JSON; PDF queda fuera de esta iteracion.
- El periodo del informe se aplica sobre los datos ya filtrados en pantalla.
- Los graficos Plotly se incrustan en HTML para poder abrir el informe sin Streamlit.
- Los CSV tecnicos mantienen nombres internos de columnas para no romper procesos posteriores.

## Informes de planificación por persona

El generador de planificación crea subinformes `person_<nombre>.html` cuando se solicita la vista actual con subniveles. Cada informe personal incluye una sección **Tareas asignadas por proyecto**: agrupa las tareas bajo su proyecto, muestra las horas asignadas a cada tarea en el periodo y presenta el total del proyecto.

El paquete incluye también `project_task_assignments.csv`, con las columnas persona, proyecto, tarea y horas asignadas. En el CSV del paquete global se mantienen todas las personas para conservar la trazabilidad completa.
