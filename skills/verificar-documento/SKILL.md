---
name: verificar-documento
description: Sistema QA multi-capa (10 capas) para documentos ARL Positiva. Compara generado vs ejemplo en estructura, dimensiones, contenido textual, formato, alineación, fuentes, bordes, imágenes, firmas y reglas ARL. Incluye auto-fix engine con sugerencias de corrección.
triggers:
  - "verificar documento"
  - "comparar con ejemplo"
  - "revisar formato"
  - "validar documento"
  - "control de calidad"
  - "auditar documento"
  - "qa documento"
  - "quality assurance"
  - "check documento"
---

# QA Maestro — Sistema de Verificación Multi-Capa

## ⚡ EJECUCIÓN RÁPIDA

```bash
python3 scripts/qa_maestro.py <generado.docx> <ejemplo.docx> --auto-fix
```

## 🏗️ ARQUITECTURA DE 10 CAPAS

```
                    ┌─────────────────────────────┐
                    │  DOC GENERADO  +  EJEMPLO   │
                    └─────────────┬───────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    │                             │                             │
    ▼                             ▼                             ▼
┌────────┐                  ┌──────────┐                 ┌──────────┐
│CAPA 0  │  Pre-vuelo       │CAPA 1    │  Estructura    │CAPA 2    │
│JSON    │  Datos correctos │XML       │  Tablas, filas │Dimension │
│        │  Fechas formato  │          │  gridSpan      │Anchos    │
│        │  Sin "/" en texto│          │  vMerge        │Desborde  │
└────────┘                  └──────────┘                 └──────────┘
    │                             │                             │
    ▼                             ▼                             ▼
┌────────┐                  ┌──────────┐                 ┌──────────┐
│CAPA 3  │  Texto exacto    │CAPA 4    │  Formato       │CAPA 5    │
│Texto   │  celda×celda     │Estilos   │  Bold, size    │Reglas    │
│        │  Mayúsculas      │          │  Colores       │ARL       │
│        │  Label→número    │          │  Hipervínculos │Firmas    │
└────────┘                  └──────────┘                 └──────────┘
    │                             │                             │
    ▼                             ▼                             ▼
┌────────┐                  ┌──────────┐                 ┌──────────┐
│CAPA 6  │  Alineación      │CAPA 7    │  Bordes        │CAPA 8    │
│Alineac.│  Fuentes         │Bordes    │  top/bottom    │Imágenes  │
│Fuentes │  Interlineado    │          │  left/right    │Firmas    │
│        │  Sangrías        │          │  Grosor        │Posición  │
└────────┘                  └──────────┘                 └──────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │  CAPA 9      │
                          │  Reglas      │
                          │  Formato     │
                          │  Específicas │
                          └──────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
              ┌───────────┐              ┌───────────┐
              │  REPORTE  │              │ AUTO-FIX  │
              │  UNIFICADO│              │ ENGINE    │
              └───────────┘              └───────────┘
```

## 🚀 USO

```bash
# Verificación completa
python3 scripts/qa_maestro.py generado.docx ejemplo.docx --auto-fix

# Con datos JSON para pre-validación
python3 scripts/qa_maestro.py generado.docx ejemplo.docx --datos paciente.json

# Con formato específico
python3 scripts/qa_maestro.py generado.docx ejemplo.docx --formato 1
```

## 📊 TIPOS DE ERROR QUE DETECTA

| Tipo | Capa | Descripción |
|------|------|-------------|
| `LABEL_REEMPLAZADO_POR_NUMERO` | 3 | ⚠️ CRÍTICO: Celda label ("Día") reemplazada por número ("5") |
| `LABEL_FECHA_REEMPLAZADO` | 3 | ⚠️ CRÍTICO: Label de fecha destruido por dígito |
| `CELDA_ANGOSTA` | 2 | ⚠️ CRÍTICO: Celda demasiado angosta → desborde vertical |
| `EXPLOSION_PAGINAS` | 5,9 | ⚠️ CRÍTICO: Documento mucho más grande que el ejemplo |
| `TEXTO_DUPLICADO` | 3 | Texto pegado por hyperlinks residuales |
| `MAYUSCULAS` | 3 | "X" vs "x", mayúsculas incorrectas |
| `SEPARADOR_SLASH` | 3 | " / " donde debe haber saltos de línea |
| `NOMBRE_TRUNCADO` | 3 | Nombre incompleto (falta "OSORIO") |
| `BOLD_INCORRECTO` | 4 | Negrita donde el ejemplo no la tiene |
| `FONT_SIZE` | 4 | Tamaño de fuente incorrecto |
| `FONDO_AMARILLO` | 4 | Sombreado amarillo heredado de plantilla |
| `TEXTO_AZUL` | 4 | Texto azul por hyperlink residual |
| `HYPERLINKS_RESIDUALES` | 4 | Hipervínculos no eliminados |
| `VINYETAS_VACIAS` | 4,9 | Párrafos con bullet sin texto |
| `NUMERO_PARRAFOS` | 4 | Distinto número de párrafos |
| `ALINEACION` | 6 | Alineación de párrafo incorrecta |
| `FUENTE` | 6 | Nombre de fuente distinto al ejemplo |
| `INTERLINEADO` | 6 | Interlineado diferente |
| `SANGRIA` | 6 | Sangría izquierda diferente |
| `BORDE` | 7 | Bordes de celda incorrectos |
| `NUM_IMAGENES` | 8 | Número de imágenes distinto |
| `IMAGEN_FALTANTE` | 8 | Falta la firma |
| `FIRMA_FALTANTE` | 9 | Firmas ARL no encontradas |
| `FECHA_MAL_FORMATO` | 0 | Fecha sin formato DD/MM/AAAA |

## 🔧 AUTO-FIX ENGINE

El sistema mapea cada tipo de error a una causa raíz y una solución concreta:

```
❌ T0 F8 C1: 'Día' → '4' (LABEL_REEMPLAZADO_POR_NUMERO)
   🔧 Causa: _poner_fecha_celdas escribe en celda label
   🔧 Fix:   Usar acceso directo doc.tables[0].rows[9].cells[1]
   🔧 Archivo: backend/doc_generator.py
```

## 📁 ARCHIVOS DEL SISTEMA

| Archivo | Descripción |
|---------|-------------|
| `scripts/qa_maestro.py` | 🆕 **Orquestador central**: ejecuta las 10 capas |
| `scripts/analizar_ejemplo.py` | Extrae el MOLDE completo del ejemplo (Runs, fuentes, colores) |
| `scripts/verificar_profundo.py` | Comparación exhaustiva multi-capa |
| `scripts/verificar_capa3_texto.py` | 🆕 CAPA 3 mejorada: 10 tipos de error textual |
| `scripts/verificar.py` | CAPA 1: Estructura XML |
| `scripts/verificar_capa2.py` | CAPA 2: Dimensiones y desborde |
| `scripts/qa_completo.py` | QA unificado inline (versión ligera) |
| `references/errores-comunes.md` | Catálogo de patrones de error conocidos |

## 🔗 Skills relacionadas

- **`generar-documento`** — El generador que esta skill verifica. Catálogo de 20+ pitfalls con fixes.
- **`generar-documento/references/bugs-valoracion-desempeno.md`** — 10 errores Formato 7.
- **`flujo-browser`** — Extracción de portales, dashboard chat, verificación de datos.

## 🆕 PROTOCOLO DE VERIFICACIÓN CONTRA PORTALES (Mayo 2026)

ANTES de verificar el documento generado, los DATOS deben verificarse contra los portales.
Esta skill cubre la verificación de CONTENIDO (datos correctos una vez extraídos).

### Marcas de verificación (obligatorio mostrar en cada dato)

| Marca | Significado | Cuándo usarla |
|-------|-------------|---------------|
| ✅ | VERIFICADO | Dato confirmado en Medifolios Y Positiva |
| ⚠️ | PENDIENTE | Falta verificar en al menos un portal |
| ❌ | DISCREPANCIA | El paciente dijo algo diferente a lo que registra el portal |
| 👤 | DATO DEL PACIENTE | Solo fuente oral, no verificable en portales |

### Cruce de siniestro (dato crítico)
- El siniestro viene de DOS fuentes: Medifolios (Agenda) y Positiva (SINIESTROS)
- AMBOS DEBEN COINCIDIR. Si no → 🚨 ALERTA, prevalece POSITIVA.
- NUNCA generar un formato sin siniestro verificado

### CC colombiana
- Limpiar formato antiguo: `12'130.558` → `12130558`
- `re.sub(r"['. ]", "", cc)`

## 🆕 Pitfalls QA 2026-05-16

- **chr(10) vs "\n"**: `replace(" / ", "\n")` rompe sintaxis Python. Usar `chr(10)`.
- **_buscar_y_reemplazar en filas fecha**: Celda angosta de dígito vs celda ancha de texto → explosión páginas.
- **_reemplazar_celda_entera con label**: Buscar por CONTENIDO CLÍNICO, no por texto del label.