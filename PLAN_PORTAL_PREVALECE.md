# RILO SAS — Plan: El Portal Siempre Gana

> Bug raíz: `_merge_paciente_con_llm` solo llena campos VACÍOS.
> Si el LLM genera un dato incorrecto (nombre, fecha, teléfono), el portal no lo corrige.
> Este plan lo arregla de una vez.

---

## El bug central explicado en 3 líneas

```python
# ACTUAL — solo llena si el campo está vacío:
if not datos_llm["paciente"].get("nombre"):
    datos_llm["paciente"]["nombre"] = medi["nombre"]  # nunca se ejecuta

# CORRECTO — siempre usar portal para datos de identidad:
if medi.get("nombre"):
    datos_llm["paciente"]["nombre"] = medi["nombre"]  # siempre se ejecuta
```

El LLM generó `"nombre": "MARIBEL FUENTES MEDINA"` (error de transcripción de audio).
Medifolios tiene `"nombre": "MARIBEL PUENTES MEDINA"` (correcto, sacado del sistema de salud).
La función de merge vio que nombre no estaba vacío → dejó el dato incorrecto del LLM.
El documento salió con "FUENTES" en lugar de "PUENTES".

**Lo mismo ocurre con:**
- `fecha_nacimiento` → no está ni en la lista de campos que el merge procesa
- `apellido1`, `apellido2` → combinados en "nombre" solo si estaba vacío
- `dominancia` → solo viene del audio, puede mal transcribirse

---

## FIX PRINCIPAL — `generar_formatos.py`: reescribir `_merge_paciente_con_llm`

**Archivo:** `backend/workflow_steps/generar_formatos.py` líneas 38–88

**Lógica actual (rota):** Portal como fallback cuando LLM no tiene el dato.
**Lógica correcta:** Portal como FUENTE OFICIAL que sobreescribe siempre.

```python
def _merge_paciente_con_llm(datos_llm: dict, cc: str) -> dict:
    """
    Mezcla: portal SOBREESCRIBE datos de identidad del LLM.
    Solo los datos clínicos de evaluación (que no están en portales) se dejan del LLM.
    """
    json_paciente = _cargar_json_paciente(cc)
    if not json_paciente or json_paciente.get("_vacio"):
        return datos_llm

    medi = json_paciente.get("medifolios", {})
    pos = json_paciente.get("positiva", {})

    pac = datos_llm.setdefault("paciente", {})

    # ── CAMPOS DE IDENTIDAD: SIEMPRE usar portal ──────────────────────────────
    # El LLM transcribe del audio y puede equivocarse. El portal (Medifolios)
    # extrae del sistema oficial de salud. Sin excepciones: portal gana.

    # Nombre completo — construir desde partes o usar campo combinado
    nombre_portal = (
        " ".join(filter(None, [
            medi.get("nombre1", ""), medi.get("nombre2", ""),
            medi.get("apellido1", ""), medi.get("apellido2", "")
        ])).strip()
        or medi.get("nombre", "")
    )
    if nombre_portal:
        pac["nombre"] = nombre_portal  # SOBREESCRIBE siempre

    # CC — siempre correcto (es el input del usuario al iniciar el workflow)
    pac["documento"] = medi.get("numero_id", "") or cc

    # Fecha de nacimiento — solo en Medifolios, no en audio
    if medi.get("fecha_nacimiento"):
        pac["fecha_nacimiento"] = medi["fecha_nacimiento"]  # SOBREESCRIBE

    # Campos de contacto — portal es más preciso que el audio
    for campo_portal, campo_pac in [
        ("telefono", "telefono"),
        ("direccion", "direccion"),
        ("email", "email"),
        ("edad", "edad"),
    ]:
        if medi.get(campo_portal):
            pac[campo_pac] = medi[campo_portal]  # SOBREESCRIBE

    # EPS/AFP — de Medifolios cuando estén (ver también fix N-1 en PLAN_PERFECCIONAMIENTO)
    for campo_portal, campo_pac in [
        ("eps_ips", "eps_ips"), ("slct_eps_paciente", "eps_ips"),
        ("afp", "afp"),         ("slct_afp_paciente", "afp"),
    ]:
        if medi.get(campo_portal) and not pac.get(campo_pac):
            pac[campo_pac] = medi[campo_portal]

    # ── EMPRESA: portal cuando disponible ─────────────────────────────────────
    emp = datos_llm.setdefault("empresa", {})
    empresa_portal = (
        medi.get("empresa") or medi.get("slct_empresa_paciente") or
        (pos.get("datos_asegurado") or {}).get("empresa") or
        json_paciente.get("empresa", {}).get("nombre", "")
    )
    if empresa_portal and empresa_portal not in ("Usuario Acciones", "[VERIFICAR]"):
        emp["nombre"] = empresa_portal  # SOBREESCRIBE

    # NIT solo si Positiva lo tiene
    nit_portal = (pos.get("datos_asegurado") or {}).get("nit", "")
    if nit_portal:
        emp["nit"] = nit_portal

    # ── SINIESTRO: solo portal-oficial, no [VERIFICAR] ────────────────────────
    sin = datos_llm.setdefault("siniestro", {})
    siniestro_portal = ""
    if medi.get("siniestro_medi") and medi["siniestro_medi"] != "[VERIFICAR]":
        siniestro_portal = medi["siniestro_medi"]
    elif pos.get("siniestro_id"):
        siniestro_portal = pos["siniestro_id"]
    elif (pos.get("siniestros") or []):
        siniestro_portal = pos["siniestros"][0].get("id", "")
    if siniestro_portal:
        sin["id_siniestro"] = siniestro_portal  # SOBREESCRIBE si portal lo tiene

    return datos_llm
```

**Impacto directo de este único fix:**
- `nombre`: "MARIBEL FUENTES MEDINA" → "MARIBEL PUENTES MEDINA" ✓
- `fecha_nacimiento`: hallucination del LLM → "1971-03-02" (de Medifolios) ✓
- `telefono`, `direccion`, `email`: siempre de portal ✓
- `CC`: siempre correcto ✓

---

## FIX 2 — `sintetizar_maestro.py`: incluir `fecha_nacimiento` y nombre completo en el contexto del LLM

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` líneas 36–49

Actualmente `_formatear_portales` no pasa `fecha_nacimiento` al LLM. Y el nombre se construye como `nombre1 + apellido1` (sin apellido2). El LLM no sabe el nombre completo ni la fecha de nacimiento, por eso los inventa del audio.

**Aunque el fix principal (FIX 1) ya sobreescribe después, es mejor que el LLM vea los datos correctos desde el inicio** para que el resto del contenido clínico (que SÍ depende de la identidad) sea coherente.

```python
def _formatear_portales(datos: dict) -> str:
    ...
    if medi:
        # Nombre completo con todos los apellidos
        nombre = (
            " ".join(filter(None, [
                medi.get("nombre1",""), medi.get("nombre2",""),
                medi.get("apellido1",""), medi.get("apellido2","")
            ])).strip()
            or medi.get("nombre", "")
        )
        if nombre: bloques.append(f"  Paciente: {nombre}")
        
        # NUEVO: incluir fecha de nacimiento
        if medi.get("fecha_nacimiento"):
            bloques.append(f"  Fecha nacimiento: {medi['fecha_nacimiento']}")
        
        if medi.get("telefono"): bloques.append(f"  Teléfono: {medi['telefono']}")
        if medi.get("direccion"): bloques.append(f"  Dirección: {medi['direccion']}")
        if medi.get("email"):    bloques.append(f"  Email: {medi['email']}")
        if medi.get("eps_ips") or medi.get("slct_eps_paciente"):
            bloques.append(f"  EPS: {medi.get('eps_ips') or medi.get('slct_eps_paciente','')}")
        if medi.get("afp") or medi.get("slct_afp_paciente"):
            bloques.append(f"  AFP: {medi.get('afp') or medi.get('slct_afp_paciente','')}")
        if medi.get("empresa") or medi.get("slct_empresa_paciente"):
            bloques.append(f"  Empresa (Medi): {medi.get('empresa') or medi.get('slct_empresa_paciente','')}")
        if medi.get("siniestro_medi") and medi["siniestro_medi"] != "[VERIFICAR]":
            bloques.append(f"  Siniestro (Medi): {medi['siniestro_medi']}")
    ...
```

---

## FIX 3 — `sintetizar_maestro.py`: reforzar regla "portal gana" en el prompt y separar campos

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` líneas 100–136 (`PROMPT_USUARIO_SINTESIS`)

Añadir a la estructura JSON esperada el campo `fecha_nacimiento` en paciente, y reforzar las reglas:

```python
PROMPT_USUARIO_SINTESIS = """...
```json
{
  "paciente": {
    "documento": "...",
    "nombre": "...",
    "fecha_nacimiento": "YYYY-MM-DD o DD/MM/YYYY tal como aparece en el portal",
    "edad": "...",
    "telefono": "...",
    ...
  },
  ...
}
```

REGLAS (estrictas):
- Datos de IDENTIDAD (nombre, CC, fecha nacimiento, teléfono, dirección): COPIAR EXACTAMENTE del bloque
  📋 DATOS VERIFICADOS PORTALES. Si el audio dice algo diferente, IGNORAR el audio para estos campos.
- Nombre del paciente: usar el nombre EXACTO del portal, no el del audio. Nunca cambies apellidos.
- Si el portal tiene "PUENTES" como apellido, el JSON debe decir "PUENTES", nunca "FUENTES" ni variantes.
- Proceso productivo y tareas críticas: SOLO del cargo ACTUAL (empresa.cargo). Si el audio menciona
  trabajos anteriores, NO ponerlos en tareas_criticas. Ponerlos en apreciacion_trabajador como historial.
- Dominancia (lateralidad): extraer del audio con cuidado. Si no está claro, poner "[VERIFICAR: derecha o izquierda]".
...
"""
```

---

## FIX 4 — `sintetizar_maestro.py`: validar nombre del LLM contra portal antes de retornar

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py` línea 206 (después de parsear el JSON clínico)

Añadir validación post-síntesis para detectar apellidos incorrectos:

```python
# Después de parsear datos_clinicos con éxito (línea 206+):

# Validar que el nombre del paciente no contradice el portal
if datos_portales:
    medi_portales = datos_portales.get("medifolios", {})
    apellido_portal = medi_portales.get("apellido1", "").strip().upper()
    nombre_llm = (datos_clinicos.get("paciente", {}).get("nombre") or "").upper()
    
    if apellido_portal and apellido_portal not in nombre_llm:
        # El apellido del portal no está en el nombre del LLM → error de transcripción
        _log(f"ADVERTENCIA: apellido portal '{apellido_portal}' no encontrado en nombre LLM '{nombre_llm}'")
        # Corregir automáticamente
        nombre_portal = (
            " ".join(filter(None, [
                medi_portales.get("nombre1",""), medi_portales.get("nombre2",""),
                medi_portales.get("apellido1",""), medi_portales.get("apellido2","")
            ])).strip()
        )
        if nombre_portal:
            datos_clinicos["paciente"]["nombre"] = nombre_portal
            datos_clinicos.setdefault("_meta", {}).setdefault("correcciones_portal", []).append(
                f"nombre: LLM={nombre_llm} → portal={nombre_portal}"
            )
```

---

## FIX 5 — Advertir en el documento cuando datos clínicos críticos no se pudieron verificar

**Archivo:** `backend/workflow_steps/generar_formatos.py`

Cuando Positiva está vacío y hay campos clínicos no verificados (diagnóstico, tipo evento, fecha siniestro), añadir un campo `_advertencias_documento` que el doc_generator puede mostrar:

```python
def ejecutar(datos_clinicos: dict, task_id: str, verificaciones: list = None) -> dict:
    ...
    cc = datos_clinicos.get("paciente", {}).get("documento", "")
    if cc:
        datos_clinicos = _merge_paciente_con_llm(datos_clinicos, cc)
    
    # Detectar campos críticos sin verificar
    advertencias = []
    if datos_clinicos.get("siniestro", {}).get("id_siniestro", "").startswith("["):
        advertencias.append("Siniestro no verificado en portal — confirmar número con Sandra")
    if not datos_clinicos.get("siniestro", {}).get("fecha_evento"):
        advertencias.append("Fecha del evento no disponible — completar manualmente")
    if not datos_clinicos.get("siniestro", {}).get("diagnostico_cie10") or \
       "[FALTA" in str(datos_clinicos.get("siniestro", {}).get("diagnostico_cie10", "")):
        advertencias.append("Diagnóstico CIE-10 no verificado — completar desde Positiva")
    
    if advertencias:
        datos_clinicos["_advertencias_documento"] = advertencias
        _log(f"Advertencias en generación: {advertencias}")
    
    return generar_todos(datos_clinicos, task_id)
```

---

## FIX 6 — `verificar_portales.py`: log explícito cuando síntesis contradice portal en campos de identidad

**Archivo:** `backend/workflow_steps/verificar_portales.py` líneas 145–182

Actualmente la verificación marca "discrepancia" pero no actúa. Añadir corrección automática para campos de identidad:

```python
# En ejecutar(), después de calcular verificaciones:
for v in verificaciones:
    if v["estado"] == "discrepancia" and v["campo"] in ("nombre", "documento", "telefono", "direccion"):
        # Para campos de identidad, el portal SIEMPRE gana → corregir en datos_enriquecidos
        _set_nested(datos_enriquecidos, f"paciente.{v['campo']}", v["portal"])
        v["estado"] = "corregido_por_portal"
        v["nota"] = f"Auto-corregido: LLM={v['sintesis']} → Portal={v['portal']}"
        _log(f"Auto-corrección identidad: {v['campo']} '{v['sintesis']}' → '{v['portal']}'")
```

---

## Tabla de resumen

| # | Fix | Archivo | Impacto | Tiempo |
|---|-----|---------|---------|--------|
| **1** | `_merge_paciente_con_llm`: SIEMPRE sobreescribir con portal | `generar_formatos.py` | **CRÍTICO** | 20 min |
| **2** | `_formatear_portales`: incluir fecha_nacimiento, nombre completo, EPS/AFP/empresa | `sintetizar_maestro.py` | **Alto** | 10 min |
| **3** | Prompt síntesis: regla estricta portal gana + separar historial de cargo actual | `sintetizar_maestro.py` | **Alto** | 10 min |
| **4** | Validar apellido del LLM contra portal post-síntesis | `sintetizar_maestro.py` | **Alto** | 10 min |
| **5** | Advertencias en generación cuando campos críticos sin verificar | `generar_formatos.py` | **Medio** | 10 min |
| **6** | Verificar portales: auto-corregir identidad donde hay discrepancia | `verificar_portales.py` | **Medio** | 10 min |

**Total estimado: ~70 minutos de trabajo de OpenCode.**

---

## Qué cambia concretamente para Maribel (CC 36280228)

| Campo | Antes (incorrecto) | Después (correcto) | Fuente |
|-------|-------------------|--------------------|--------|
| nombre | MARIBEL FUENTES MEDINA | MARIBEL PUENTES MEDINA | Medifolios |
| fecha_nacimiento | dato incorrecto del audio | 1971-03-02 | Medifolios |
| telefono | posible error | 3138827687 | Medifolios |
| direccion | posible error | CONJUTO RESERVA LOS LAGOS APTO 507 TORRE 1 | Medifolios |
| empresa | "Pitarentos" | "Alcaldía Municipal de Pitalito" | Portal + Notas |
| dominancia | izquierda (error audio) | [VERIFICAR: derecha o izquierda] | No verificable automáticamente — Sandra confirma |

---

## El caso de la dominancia (izquierda/derecha)

La lateralidad **no está en ningún portal** (Medifolios y Positiva no la registran). Solo viene del audio.
Si Deepgram transcribió "derecha" como "izquierda", no hay manera automática de corregirlo.

**Solución:** Cuando el LLM no puede confirmar la lateralidad de múltiples fuentes, ponerla como `[VERIFICAR: derecha o izquierda]` en lugar de adivinar. Sandra la completa en 5 segundos revisando el documento.

Esto es mejor que un documento que pone con seguridad el lado equivocado.

---

## Orden de ejecución respecto a los otros planes

```
1. PLAN_PERFECCIONAMIENTO.md   → Arregla bugs raíz Playwright (extracción portales)
2. PLAN_DATOS_CORRECTOS.md     → Arregla que Positiva extrae datos y notas del workspace se leen
3. PLAN_PORTAL_PREVALECE.md    → Garantiza que lo que sí extrae el portal SIEMPRE reemplaza al LLM
```

Los tres son necesarios. Este plan (#3) es el más fácil y más impactante **a corto plazo**:
incluso con portales parciales (como el estado actual de Positiva), el nombre, fecha de nacimiento,
teléfono y dirección de Medifolios siempre serán correctos en los documentos generados.

---

*Plan Portal Prevalece — 2026-05-24 — Bug raíz: merge llena vacíos en lugar de sobreescribir*
