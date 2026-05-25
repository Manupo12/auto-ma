# PLAN_MEZCLA_PACIENTES.md — Diagnóstico Forense y Correcciones

**Creado:** 2026-05-25  
**Prioridad:** URGENTE — el sistema genera documentos con datos de otro paciente

---

## DIAGNÓSTICO FORENSE — Por qué Maribel salió como minero

El VOI generado para CC 36280228 (Maribel Puentes Medina) tenía:
- Empresa: ALCALDIA MUNICIPAL DE PITALITO ← correcto (del portal)
- Cargo: **Obrero de tratamiento roca** ← datos de Juan Carlos Durán (CC 1193143688)
- Diagnóstico: **Herida dedo mano derecha** ← datos de Juan Carlos
- Historia laboral: **BOLIVARIANA DE MINERALES** ← datos de Juan Carlos

### Bug 1 — `_tiene_cc` no encuentra VOIs porque la CC está dígito a dígito

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py`  
**Función:** `_tiene_cc(path, cc)`

Los formatos VOI de Medifolios tienen la fecha y el número de documento en una cuadrícula donde CADA CELDA tiene UN SOLO DÍGITO. Cuando `_leer_texto` une las celdas con `"\n"`, la CC queda:
```
3
6
2
8
0
2
2
8
```

Luego `contenido_limpio = contenido.replace(" ","")` — elimina espacios pero NO saltos de línea. Resultado: `"3\n6\n2\n8\n0\n2\n2\n8"`. La búsqueda `"36280228" in contenido_limpio` → **False siempre**.

**Los VOI y Cierre de Caso NUNCA se encuentran.** Solo se encuentran documentos tipo CR/CC donde la CC está en una celda completa.

### Bug 2 — El CR se encuentra pero sus datos críticos están CORTADOS

**VERIFICADO EMPÍRICAMENTE.** El CR tiene 7000 chars totales. `_leer_texto(path, max_chars=2000)` corta exactamente en el char 2000, justo antes de la tabla clínica:

```
char ~2000: "...DANIEL ALEXANDER MEDI" ← CORTE
char 2000+: TIPO DE SINIESTRO | Enfermedad Laboral
            FECHA DEL EVENTO  | 23/05/2025
            CARGO:            | Técnica administrativa
            SEGMENTO LESIONADO| Codos, muñeca y manos.
            ...
```

El LLM recibe el CR, pero el CR sin esa tabla es solo texto genérico de recomendaciones. **No tiene cargo, no tiene tipo de siniestro, no tiene diagnóstico, no tiene fecha del evento.** Para todos esos campos, el LLM solo tiene el audio de Maribel — y el audio de una consulta de fisioterapia no siempre reconstruye con precisión el historial laboral completo ni la historia clínica estructurada.

### Bug 3 — El siniestro 503375273 está en el JSON pero ignorado

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py`  
**Función:** `_formatear_portales(datos)`

```python
if pos.get("siniestros"):
    for s in pos["siniestros"][:2]:
        ...
```

`pos["siniestros"]` está vacío. Pero `pos["autorizaciones"]` tiene:
```json
{"numero": "36280228", "descripcion": "503375273", "estado": "23/05/2025"}
```

El siniestro correcto (503375273) y la fecha del evento (23/05/2025) están ahí pero `_formatear_portales` nunca los lee.

### Bug 4 — `leer_notas_crudas` lee solo 2000 chars por archivo

El CR de Maribel tiene la CC en la posición ~1889 de los 3000 chars del _check_, pero el **contenido** que se pasa al LLM se corta a 2000 chars. La descripción completa de las tareas, el tipo de siniestro, y las recomendaciones vienen después. El LLM recibe un CR truncado.

### Bug 5 — Campos clínicos del CR/notas no tienen prioridad en el prompt

El prompt le dice al LLM:
> "Datos de IDENTIDAD: COPIAR EXACTAMENTE del bloque 📋 DATOS VERIFICADOS PORTALES"

Pero **no le dice** que los datos clínicos del archivo CR (tipo siniestro, cargo, fecha evento, diagnóstico) también son fuente oficial. El LLM usa el audio para estos campos aunque el CR diga lo contrario.

---

## FIXES CONCRETOS

### FIX 1 — `_tiene_cc`: eliminar saltos de línea (no solo espacios)

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py`  
**Línea ~49**

```python
# ANTES:
contenido_limpio = contenido.replace(".","").replace("-","").replace("'","").replace(" ","")
return cc_norm in contenido_limpio

# DESPUÉS — también elimina saltos de línea y tabs:
contenido_limpio = (
    contenido
    .replace(".","").replace("-","").replace("'","")
    .replace(" ","").replace("\n","").replace("\r","").replace("\t","")
)
return cc_norm in contenido_limpio
```

**Por qué esto funciona:** La CC "36280228" en el VOI es "3\n6\n2\n8\n0\n2\n2\n8" antes de la limpieza. Al eliminar "\n", queda "36280228" y la búsqueda funciona.

**Aumentar también `max_chars` del contenido a 5000 para no truncar el CR:**

```python
# ANTES (línea ~110):
contenido_completo = _leer_texto(path)  # max_chars=2000 por defecto

# DESPUÉS:
contenido_completo = _leer_texto(path, max_chars=5000)
```

Y la detección de CC debe usar el mismo max:
```python
# ANTES (línea ~48):
contenido = _leer_texto(path, max_chars=3000)

# DESPUÉS:
contenido = _leer_texto(path, max_chars=5000)
```

---

### FIX 2 — Aumentar `max_chars` de `_leer_texto` a 8000

**Archivo:** `backend/workflow_steps/leer_notas_crudas.py`

```python
# ANTES (línea ~110):
contenido_completo = _leer_texto(path)  # max_chars=2000 por defecto

# DESPUÉS — leer el documento completo (docs de Sandra llegan a 7000+ chars):
contenido_completo = _leer_texto(path, max_chars=8000)
```

Con este cambio, el CR pasa de 2000 chars (solo texto genérico) a 7000 chars completos, y el LLM recibe:
- `TIPO DE SINIESTRO: Enfermedad Laboral`
- `FECHA DEL EVENTO: 23/05/2025`
- `CARGO: Técnica administrativa`
- `SEGMENTO LESIONADO: Codos, muñeca y manos`
- el concepto clínico completo de reincorporación

---

### FIX 3 — `_formatear_portales`: incluir siniestro de `autorizaciones`

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py`  
**Función:** `_formatear_portales(datos)`

Después del bloque `if pos.get("siniestros"):`, agregar:

```python
# Siniestro en tabla de autorizaciones (cuando Positiva no devuelve siniestros directos)
if not pos.get("siniestros") and pos.get("autorizaciones"):
    for aut in pos["autorizaciones"][:3]:
        # La tabla autorización tiene: CC | siniestro | fecha
        posible_sin = aut.get("descripcion","").strip()
        posible_fecha = aut.get("estado","").strip()
        if posible_sin and re.match(r'^\d{8,12}$', posible_sin):
            bloques.append(f"  Siniestro (Pos-aut): {posible_sin}")
            if re.match(r'\d{2}/\d{2}/\d{4}', posible_fecha):
                bloques.append(f"  Fecha evento (Pos-aut): {posible_fecha}")
            break

# Fecha evento de RHI
rhi = pos.get("rhi", {})
if rhi.get("fechas_encontradas"):
    fecha_rehab = rhi["fechas_encontradas"][0]
    if fecha_rehab not in str(bloques):  # no duplicar
        bloques.append(f"  Fecha (RHI): {fecha_rehab}")

# Fecha evento de rehab
rehab = pos.get("rehabilitacion", {})
if rehab.get("fechas_rehab"):
    fecha_rehab2 = rehab["fechas_rehab"][0]
    bloques.append(f"  Fecha evento (Rehab): {fecha_rehab2}")
```

También necesita importar `re` al inicio del módulo (verificar si ya está importado).

---

### FIX 4 — Prompt del LLM: los archivos CR/notas son fuente oficial

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py`  
**Variable:** `PROMPT_USUARIO_SINTESIS`

Después de la sección "REGLAS ESTRICTAS", agregar:

```
REGLAS PARA NOTAS DE ARCHIVO (📝 NOTAS CRUDAS):
- Los archivos CR_, VOI_, CC_ que aparecen en 📝 NOTAS CRUDAS son documentos OFICIALES generados por Sandra.
- Para los siguientes campos, si aparecen en las notas de archivo, SON AUTORITATIVOS (igual de confiables que el portal):
  * empresa.cargo → buscar "Nombre del cargo:", "CARGO:", "cargo asegurado"
  * siniestro.tipo_evento → buscar "TIPO DE SINIESTRO", "Enfermedad Laboral", "Accidente de Trabajo"
  * siniestro.fecha_evento → buscar "FECHA DEL EVENTO", "Fecha del evento"
  * siniestro.diagnostico_cie10 → buscar diagnósticos CIE-10 en notas clínicas
  * empresa.nombre → buscar el nombre de la empresa en el encabezado del CR
  * paciente.eps_ips → buscar "EPS - IPS*" en las notas
- Si el audio dice cargo X y el CR dice cargo Y, PREVALECE el CR (documento oficial).
- NO usar datos clínicos del audio si el audio fue marcado como sospechoso (ver advertencia al inicio).
```

---

### FIX 5 — `sintetizar_maestro`: extraer datos clave de las notas crudas antes de llamar al LLM

**Archivo:** `backend/workflow_steps/sintetizar_maestro.py`

Agregar función `_extraer_datos_notas(notas_crudas: list) -> dict` que parsea los archivos de notas antes de armar el contexto y los agrega al bloque de datos verificados:

```python
def _extraer_datos_notas(notas: list) -> dict:
    """
    Extrae campos estructurados de archivos CR_, CC_, VOI_ de Sandra.
    Estos documentos son autoritativos — igual que el portal.
    """
    datos = {}
    
    for nota in notas:
        nombre = nota.get("nombre","").upper()
        contenido = nota.get("contenido","")
        
        # Tipo siniestro
        tipo_match = re.search(r'TIPO\s*(?:DE\s*)?SINIESTRO\s*[\|:\s]+([^\n\|]{5,40})', contenido, re.IGNORECASE)
        if tipo_match and not datos.get("tipo_siniestro"):
            datos["tipo_siniestro"] = tipo_match.group(1).strip()
        
        # Fecha del evento
        fecha_match = re.search(r'FECHA\s*DEL\s*EVENTO\s*[\|:\s]+(\d{1,2}/\d{1,2}/\d{4})', contenido, re.IGNORECASE)
        if fecha_match and not datos.get("fecha_evento"):
            datos["fecha_evento"] = fecha_match.group(1).strip()
        
        # Cargo
        cargo_match = re.search(r'CARGO\s*[\|:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{5,60})', contenido, re.IGNORECASE)
        if cargo_match and not datos.get("cargo"):
            cargo = cargo_match.group(1).strip()
            if len(cargo) > 4 and cargo.upper() not in ("CARGO", "FUNCIONES"):
                datos["cargo"] = cargo
        
        # Segmento lesionado
        seg_match = re.search(r'SEGMENTO\s*LESIONADO\s*[\|:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ,\s]{5,80})', contenido, re.IGNORECASE)
        if seg_match and not datos.get("segmento"):
            datos["segmento"] = seg_match.group(1).strip()
        
        # Diagnóstico CIE-10
        cie10 = re.findall(r'([A-Z]\d{2,3}(?:\.\d)?)\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s,]{5,60})', contenido)
        if cie10 and not datos.get("diagnosticos"):
            datos["diagnosticos"] = [{"codigo": m[0], "descripcion": m[1].strip()} for m in cie10[:3]]
        
        # EPS
        eps_match = re.search(r'EPS\s*[-\s]*IPS\s*[\|:\*]+\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,40})', contenido, re.IGNORECASE)
        if eps_match and not datos.get("eps"):
            eps = eps_match.group(1).strip()
            if eps and eps.upper() not in ("EPS","IPS","ENTIDAD"):
                datos["eps"] = eps
        
        # AFP
        afp_match = re.search(r'AFP\s*[\|:\*]+\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,40})', contenido, re.IGNORECASE)
        if afp_match and not datos.get("afp"):
            afp = afp_match.group(1).strip()
            if afp and len(afp) > 3:
                datos["afp"] = afp
        
        # Siniestro en notas
        sin_match = re.search(r'(?:NO\.?\s*SINIESTRO|N[°º]?\s*SINIESTRO|siniestro)\s*[\|:\s]+(\d{8,12})', contenido, re.IGNORECASE)
        if sin_match and not datos.get("siniestro"):
            datos["siniestro"] = sin_match.group(1).strip()
    
    return datos
```

Y en `_componer_contexto`, antes de `_formatear_notas(notas_crudas)`, agregar:

```python
datos_de_notas = _extraer_datos_notas(notas_crudas)
if datos_de_notas:
    bloques_notas = ["📋 DATOS EXTRAÍDOS DE ARCHIVOS DE SANDRA (AUTORITATIVOS):"]
    if datos_de_notas.get("tipo_siniestro"):
        bloques_notas.append(f"  Tipo siniestro: {datos_de_notas['tipo_siniestro']}")
    if datos_de_notas.get("fecha_evento"):
        bloques_notas.append(f"  Fecha del evento: {datos_de_notas['fecha_evento']}")
    if datos_de_notas.get("cargo"):
        bloques_notas.append(f"  Cargo actual: {datos_de_notas['cargo']}")
    if datos_de_notas.get("segmento"):
        bloques_notas.append(f"  Segmento lesionado: {datos_de_notas['segmento']}")
    if datos_de_notas.get("diagnosticos"):
        for dx in datos_de_notas["diagnosticos"][:2]:
            bloques_notas.append(f"  Diagnóstico: {dx['codigo']} - {dx['descripcion']}")
    if datos_de_notas.get("eps"):
        bloques_notas.append(f"  EPS: {datos_de_notas['eps']}")
    if datos_de_notas.get("afp"):
        bloques_notas.append(f"  AFP: {datos_de_notas['afp']}")
    if datos_de_notas.get("siniestro"):
        bloques_notas.append(f"  Siniestro (notas): {datos_de_notas['siniestro']}")
    bloques.insert(2, "\n".join(bloques_notas))  # insertar después del audio, antes de portales
```

---

### FIX 6 — `generar_formatos`: portal siempre sobreescribe EPS, AFP, siniestro

**Archivo:** `backend/workflow_steps/generar_formatos.py`  
**Función:** `_merge_paciente_con_llm`

Ampliar la lista de campos que el portal siempre sobreescribe (no solo nombre/fecha_nacimiento):

```python
# ANTES — solo sobreescribe identidad básica
CAMPOS_PORTAL_PREVALECE = ["nombre", "cc", "fecha_nacimiento", "telefono", "direccion", "email"]

# DESPUÉS — también sobreescribe datos laborales verificados del portal
CAMPOS_PORTAL_PREVALECE = [
    "nombre", "cc", "fecha_nacimiento", "telefono", "direccion", "email",
    "eps_ips", "afp"
]
# Y para empresa/cargo: solo sobreescribir si portal tiene valor Y LLM no lo tiene
# (porque empresa puede venir correcta del audio también)
```

Y para el siniestro: si `datos_portales["positiva"]["autorizaciones"]` tiene un número de siniestro válido, usarlo:

```python
# En _merge_paciente_con_llm, al inicio del bloque de portales:
pos = datos_portales.get("positiva", {})

# Extraer siniestro de autorizaciones si no está en siniestros directos
if not pos.get("siniestros"):
    for aut in pos.get("autorizaciones", [])[:3]:
        posible_sin = str(aut.get("descripcion","")).strip()
        if re.match(r'^\d{8,12}$', posible_sin):
            if not datos_llm.get("siniestro", {}).get("id_siniestro") or \
               datos_llm["siniestro"]["id_siniestro"] == "[VERIFICAR EN PORTAL]":
                datos_llm.setdefault("siniestro", {})["id_siniestro"] = posible_sin
                # También capturar fecha del evento
                posible_fecha = str(aut.get("estado","")).strip()
                if re.match(r'\d{2}/\d{2}/\d{4}', posible_fecha):
                    if not datos_llm["siniestro"].get("fecha_evento"):
                        datos_llm["siniestro"]["fecha_evento"] = posible_fecha
            break
```

---

## Tabla de fixes

| Fix | Archivo | Cambio | Impacto |
|-----|---------|--------|---------|
| F-1 | `leer_notas_crudas.py` | Eliminar `\n` en `_tiene_cc` + max_chars=5000 | Los VOI de Sandra se ENCUENTRAN |
| F-2 | `leer_notas_crudas.py` | `max_chars` de 2000 → 8000 en `_leer_texto` | La tabla crítica del CR llega al LLM |
| F-3 | `sintetizar_maestro.py` | `_formatear_portales` lee `autorizaciones` | Siniestro 503375273 llega al LLM |
| F-4 | `sintetizar_maestro.py` | Prompt menciona notas como autoritativas | LLM usa CR para cargo/tipo/dx |
| F-5 | `sintetizar_maestro.py` | Pre-extraer campos de notas antes del LLM | LLM recibe datos estructurados de CR |
| F-6 | `generar_formatos.py` | Portal sobreescribe EPS/AFP + siniestro de autorizaciones | EPS "Sanitas", AFP "Colpensiones" correctos |

**Estimado OpenCode:** ~60 minutos  
**Ejecutar ANTES de cualquier nuevo test con audio.**

---

## Verificación post-fix

Para confirmar que funciona, correr el workflow de Maribel nuevamente. El documento generado debe tener:
- Siniestro: 503375273
- Fecha evento: 23/05/2025
- Tipo siniestro: Enfermedad Laboral
- Cargo: Técnica administrativa
- Diagnóstico: MG560 SINDROME DEL TUNEL CARPIANO BILATERAL / 771 EPICONDILITIS LATERAL BILATERAL
- EPS: Sanitas
- AFP: Colpensiones
- Historia laboral: COOTRANSLABOYANA LTDA (no BOLIVARIANA DE MINERALES)
