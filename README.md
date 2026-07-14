# Ruta Cero — Motor de Scoring de Riesgo

**Motor de scoring de riesgo delictivo para flotillas comerciales en Ciudad de México.**

Google Maps y Waze optimizan una sola variable: tiempo. Para flotillas comerciales en América Latina, la variable cara es el **riesgo** — robo de mercancía, robo de unidad, asalto al operador. Este proyecto convierte el riesgo en una dimensión de routing, igual que el tráfico.

**Estado actual:** Fase 0 — pipeline de ingesta FGJ-CDMX → PostGIS → scores estáticos por hexágono H3.

---

## Arquitectura (Fase 0)

```
CSV FGJ-CDMX (datos abiertos)
        │
        ▼
staging.incidentes_raw     ← datos crudos, sin transformar (todo texto)
        │
        │  transformación: limpieza → filtro geoespacial → filtro de delitos → deduplicación
        ▼
core.incidentes            ← tipos fuertes, geometría PostGIS, índice H3, constraints
        │
        ▼
Scores estáticos por hexágono H3 (~150 m)
        │
        ▼
API de mapa de calor (FastAPI)
```

### ¿Por qué dos capas (staging + core)?

**1. Auditabilidad.** El pipeline descarta ~5.94 % de los registros por coordenadas inválidas y excluye categorías de delito fuera del alcance del modelo. Con la capa de staging, los registros descartados siguen existiendo con su motivo de descarte: la pregunta "¿por qué este incidente no aparece en el mapa?" se responde con una query, no con una disculpa.

**2. Re-procesabilidad.**
<!-- TODO(Jesús): escribe este párrafo con tus palabras. Guía:
     - ¿Qué pasó cuando descubrimos que la deduplicación colapsaba registros con NaN?
     - ¿Qué habría costado corregirlo si los datos crudos ya no existieran en la base?
     - ¿Por qué importa que el portal de la FGJ modifique datos históricos retroactivamente? -->

**3. Idempotencia.**
<!-- TODO(Jesús): escribe este párrafo con tus palabras. Guía:
     - Define idempotencia en una línea.
     - El archivo fuente es un ACUMULADO: cada descarga trae otra vez todo lo anterior. ¿Qué evita que core se llene de duplicados al re-ingestar?
     - Menciona el mecanismo: hash determinístico + ON CONFLICT DO NOTHING. -->

---

## Decisiones de diseño (Fase 0 — exploración)

Cada decisión quedó documentada con su razón. Las más importantes:

### D1 — Fuente y ventana temporal
- **Fuente:** [Carpetas de investigación FGJ](https://datos.cdmx.gob.mx/dataset/carpetas-de-investigacion-fgj-de-la-ciudad-de-mexico), Portal de Datos Abiertos CDMX. Corte utilizado: acumulado a enero 2025.
- **Ventana:** `anio_hecho` 2023–2025 (2025 parcial: solo enero). Se usa la fecha del **hecho**, no la de denuncia: el score modela dónde *ocurren* los delitos, no dónde se denuncian.
- **¿Por qué 3 años?** Balance entre volumen estadístico y frescura: con 1 año, muchos hexágonos de ~150 m tendrían 0–2 incidentes y el score sería ruido; con más años, el score dejaría de representar el riesgo actual. El decaimiento temporal del scoring v1 pondera 2023 por debajo de 2025.

### D2 — Validación geoespacial
- Descarte: coordenadas nulas (27,751) + fuera del bounding box CDMX (1) = **5.94 %** del total (27,752 / 466,921).
- Hallazgo: cero registros con coordenadas (0, 0) — la basura geoespacial de esta fuente es casi exclusivamente nulos.
- Los descartados permanecen en staging con motivo; no se eliminan.

### D3 — Selección de delitos: dos familias de señal
El criterio: *¿este delito le puede ocurrir a la unidad, su carga o su operador, en tránsito o en parada operativa?*

- **Familia 1 — señal directa (peso primario):** delitos contra la unidad, la carga o el operador (robo de vehículo, robo a transportista, robo a repartidor, robo de accesorios/objetos del interior, robo de contenedores y mercancía, secuestro exprés, extorsión, etc.).
- **Familia 2 — violencia ambiental (peso menor):** delitos que no involucran vehículos pero señalan zonas donde una parada expone al operador (disparos de arma de fuego, portación de arma, lesiones intencionales por arma blanca/de fuego, homicidio doloso).

**Exclusiones documentadas:**
| Delito | Razón de exclusión |
|---|---|
| POSESIÓN DE VEHÍCULO ROBADO | Señal geográfica invertida: marca dónde se *recupera* el vehículo, no dónde se roba. |
| DAÑO EN PROPIEDAD AJENA INTENCIONAL A AUTOMÓVIL | Vandalismo a vehículo estacionado; el modelo cubre riesgo en tránsito y paradas operativas, no pernocta. |
| ROBO A NEGOCIO SIN VIOLENCIA | El riesgo pertenece al establecimiento, no a la flotilla que entrega. |
| DELITO DE BAJO IMPACTO (como categoría completa) | Cajón de sastre (86.5 % del dataset) dominado por delitos sin relación con flotillas; se rescataron subcategorías relevantes a nivel de columna `delito`. |

### D4 — Deduplicación: carpetas ≠ eventos
- **Llave natural:** `fecha_hecho + hora_hecho + delito + latitud + longitud`, empaquetada en un hash determinístico (columna `incidente_hash`, constraint UNIQUE).
- **Decisión:** múltiples carpetas del mismo hecho (p. ej., 5 víctimas de un mismo asalto) colapsan a **un evento de riesgo**: el score mide la probabilidad de que ocurra un incidente en el hexágono, no el número de víctimas. La severidad por víctimas queda como mejora futura.
- **Hallazgo empírico:** los duplicados aparentes eran 3,453, pero el 99.7 % era un artefacto: pandas trata `NaN == NaN` en `duplicated()`, haciendo colisionar registros sin coordenadas. Duplicados reales entre registros válidos: **12**.

### D5 — Orden del pipeline (no negociable)
```
staging → filtro geoespacial → deduplicación → filtro de delitos → core
```
La deduplicación va **después** del filtro geoespacial: deduplicar primero colapsaría incidentes reales distintos cuya diferencia vivía en la coordenada nula (ver D4).

---

## Limitaciones conocidas (v1)

- **Cifra negra:** la ENVIPE estima que la gran mayoría de los delitos en México no se denuncia, con variación fuerte por tipo de delito. El score se construye sobre delitos *denunciados*; se mitiga ponderando más los delitos con baja cifra negra (p. ej., robo de vehículo asegurado) y se documenta en la metadata de la API.
- **Sesgo de exposición:** el conteo bruto por zona refleja también densidad de actividad, no solo peligrosidad. El heatmap v1 reporta riesgo relativo entre hexágonos; la normalización por exposición (tránsito vehicular) queda para fases futuras.
- **Actualizaciones retroactivas de la fuente:** el portal puede modificar registros históricos; un registro corregido cambia de hash y se ingesta como evento nuevo, dejando huérfano al anterior. Caso marginal, aceptado y documentado para v1.

---

## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| Base de datos | PostgreSQL + PostGIS |
| Indexación espacial | H3 (Uber) |
| Exploración | pandas |
| API (próxima) | FastAPI |
| Calidad | pytest, GitHub Actions (próximo) |

## Roadmap

- [x] **Fase 0a — Exploración:** validación geoespacial, selección de delitos, llave de deduplicación, decisiones documentadas
- [ ] **Fase 0b — Pipeline:** DDL staging/core, ingesta idempotente, transformación
- [ ] **Fase 0c — Scoring v1:** score estático por hexágono H3 + decaimiento temporal
- [ ] **Fase 0d — API:** endpoint de mapa de calor
- [ ] **Fase 1:** scores dinámicos (hora/día) + routing tiempo-vs-riesgo con Valhalla
