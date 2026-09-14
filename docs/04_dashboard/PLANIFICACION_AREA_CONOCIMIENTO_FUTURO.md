# Área de Conocimiento en Planificación

Esta fase no implementa la capa de área de conocimiento. Queda documentada para una evolución posterior del módulo `Planificación`.

## Objetivo futuro

La capa de área de conocimiento permitirá cruzar carga, disponibilidad y capacidades técnicas. Servirá para detectar qué personas pueden asumir tareas cuando otra persona esté saturada.

## Modelo sugerido

```text
Persona -> áreas de conocimiento que domina
Tarea/proyecto -> áreas de conocimiento requeridas
Planificación -> carga + disponibilidad + conocimiento
```

## Asociación persona-área

Cada persona podrá tener una o varias áreas de conocimiento, con un nivel o prioridad si se requiere. Ejemplos:

- visión artificial,
- automatización,
- diseño mecánico,
- datos,
- electrónica,
- gestión de proyecto.

## Asociación tarea-área

Cada tarea o proyecto podrá declarar las áreas requeridas. Esto permitirá comparar la demanda futura con la capacidad real del equipo.

## Uso para redistribución de carga

Ejemplo futuro:

Si una persona está sobrecargada en visión artificial, el sistema podrá sugerir otras personas con área de conocimiento visión artificial y disponibilidad suficiente.

## Estado actual

No hay UI, filtros ni lógica operativa de área de conocimiento en esta iteración. El módulo actual solo prepara la base conceptual.
