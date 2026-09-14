# IMH Oreka

Plataforma corporativa de IMH Campus para analizar la actividad, planificar capacidad y equilibrar las cargas de trabajo de personas, departamentos y proyectos.

El alcance inicial es PRC-01 `Lan banaketa`: extraer horas reales y planificación desde Odoo, construir datasets clasificados y ofrecer análisis y planificación en Streamlit. Las horas reales proceden de `account.analytic.line.unit_amount` y la planificación de `project.forecast` o `project.task`, según la fuente disponible.

Este repositorio es el producto sucesor de ASMAOLA Next. El MVP original se conserva sin cambios en GitLab; consulta [la nota de migración](docs/00_contexto/MIGRACION_ASMAOLA_NEXT.md) para conocer la procedencia y las decisiones de compatibilidad.

## Estructura

```text
docs/                         Documentacion funcional y tecnica segura
config/                       Plantillas anonimas de configuracion PRC-01
scripts/00_connection/        Conexion y descubrimiento de bases Odoo
scripts/01_inventory/         Inventario de modelos y campos
scripts/02_extract/           Exportaciones directas desde Odoo a data/raw
scripts/03_transform/         Construccion de datasets PRC-01 en data/processed
scripts/04_quality_reports/   Informes de calidad y alcance en data/reports
scripts/99_legacy/            Scripts tecnicos compatibles conservados como referencia
src/imh_oreka/                Codigo comun reutilizable
apps/streamlit/               Dashboard Streamlit
data/raw/                     Exports directos de Odoo, ignorados por Git
data/processed/               Datasets transformados, ignorados por Git
data/reports/                 Informes generados, ignorados por Git
requirements/                 Dependencias por perfil
```

## Entorno

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\base.txt
python -m pip install -r requirements\dashboard.txt
```

## Configuracion

```powershell
Copy-Item .env.example .env
```

Edita `.env` localmente. No se versiona. Para PRC-01 puedes tomar como referencia `config/prc01_scope.example.env`.

La URL y la base de datos corporativas ya vienen configuradas. Solo debes completar el usuario y la contraseña localmente:

```text
ODOO_URL=https://odoo.imh.eus
ODOO_DB=imh
ODOO_USER=
ODOO_PASSWORD=
```

No incluyas credenciales, nombres de personas, exportaciones ni informes reales en Git. Usa archivos `config/*.local.csv` para valores privados.

## Extraccion anual de horas reales

```powershell
$env:ODOO_YEAR="2026"
$env:ODOO_DATE_FROM="2026-01-01"
$env:ODOO_DATE_TO="2027-01-01"
python scripts\02_extract\11_export_analytic_lines_range.py
```

Salida esperada: `data/raw/11_analytic_lines_2026-01-01_to_2027-01-01.csv`.

## Dataset anual PRC-01

```powershell
python scripts\03_transform\16_build_prc01_actuals_annual.py
```

Usa `config/prc01_activity_group_rules.csv` y genera datasets en `data/processed/`.

## Dashboard

```powershell
streamlit run apps\streamlit\prc01_horas_imputadas.py
```

El dashboard actual mantiene la logica existente y lee `data/processed/16_prc01_actuals_annual_detail.csv`.

## Aplicación Windows

Para construir la distribución ejecutable:

```powershell
.\build_windows.ps1
```

El resultado queda en `dist\IMH-Oreka\IMH-Oreka.exe`. La carpeta completa `dist\IMH-Oreka` es la aplicación distribuible: el ejecutable abre automáticamente el navegador, con la URL `https://odoo.imh.eus` y la base `imh` ya cargadas. Usuario y contraseña nunca se incorporan al ejecutable.

## Informes de planificación

Los paquetes HTML de planificación pueden incluir un informe por persona. Cada informe muestra, además del resumen y los gráficos, un desglose legible por proyecto con cada tarea concreta y sus horas asignadas en el periodo. El paquete también incorpora `project_task_assignments.csv` para poder revisar o reutilizar ese detalle.

## Validación

```powershell
$env:PYTHONPATH="src"
python -m pytest
```

Las credenciales, extracciones de Odoo y resultados generados permanecen fuera de Git.
