# Plan: Corregir el sistema de borrado de pacientes

> Análisis del bug del "paciente fantasma" (CC 36280228)

---

## Diagnóstico: por qué el borrado no funciona

Hay **4 bugs encadenados** que se combinan para producir el fantasma. Ninguno es obvio solo — juntos se enmascaran entre sí.

---

### Bug #1 — La tabla `chat_history` no existe en ningún lugar (CRÍTICO)

**Archivo:** `backend/server.py` — todos los endpoints de historial  
**Líneas clave:** 407, 424, 445, 458, 570

La tabla `chat_history` es usada en 5 lugares del código (`guardar_historial`, `cargar_historial`, `listar_historial`, `eliminar_historial`, y `eliminar_paciente`), pero **nunca hay un `CREATE TABLE IF NOT EXISTS chat_history`** en ningún archivo del proyecto.

Consecuencia en el borrado (`eliminar_paciente`, línea 570):
```
conn.execute("DELETE FROM chat_history WHERE paciente_cc=?", (cc,))
→ sqlite3.OperationalError: no such table: chat_history
→ Exception no capturada → FastAPI devuelve HTTP 500
```

El código de borrado de archivos (líneas 558–565) SÍ corre antes del crash — así que los DOCX y PDFs sí se eliminan. Pero el endpoint termina en 500, no en 200.

**Fix requerido:** Agregar `CREATE TABLE IF NOT EXISTS chat_history` en la inicialización de la base de datos. El lugar correcto es `backend/task_db.py` (ya tiene `CREATE TABLE IF NOT EXISTS workflow_tasks`) o al comienzo de `server.py` justo después de abrir `workflow.db`.

Estructura necesaria de la tabla (inferida del uso en server.py):
```sql
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_cc TEXT NOT NULL,
    rol TEXT,
    contenido TEXT,
    accion TEXT,
    archivo TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_cc ON chat_history(paciente_cc);
```

---

### Bug #2 — El frontend no maneja el error 500 del borrado

**Archivo:** `dashboard/app/formatos/page.tsx`  
**Líneas:** 84–94

```ts
const eliminarPaciente = async (cc: string) => {
    await fetch(`${API}/api/pacientes/${cc}`, { method: "DELETE" });
    // ... refresca la lista
}
```

El `await fetch(...)` no verifica `response.ok`. Si el backend devuelve 500 (por el bug #1), el frontend igual cierra el modal y recarga la lista — que sigue mostrando al paciente porque el JSON no fue borrado (o fue recreado). El usuario cree que funcionó.

**Fix requerido:** Verificar `response.ok` antes de actualizar el estado. Si es false, mostrar mensaje de error visible (no solo console.error).

---

### Bug #3 — `eliminar_formatos` no limpia `workflow_audios`

**Archivo:** `backend/server.py`  
**Línea:** 531

```python
# eliminar_formatos (DELETE /api/pacientes/{cc}/formatos)
for d in [DOCS_DIR, PDFS_DIR, AUDIO_DIR]:  # ← FALTA WORKFLOW_AUDIOS_DIR
```

El endpoint de borrar SOLO formatos omite `WORKFLOW_AUDIOS_DIR`. Los audios `.m4a` del paciente sobreviven en `storage/workflow_audios/`. Esto NO es el mismo endpoint que `eliminar_paciente` (que sí incluye `WORKFLOW_AUDIOS_DIR` en línea 558), pero es confuso y deja archivos huérfanos.

**Fix requerido:** Agregar `WORKFLOW_AUDIOS_DIR` a la lista en línea 531.

---

### Bug #4 — Las tareas activas del workflow no se cancelan antes de borrar

**Archivo:** `backend/server.py`  
**Líneas:** 567–571

`eliminar_paciente` borra el registro de `workflow_tasks` en SQLite, pero si hay un `asyncio.Task` de Python **ya corriendo en memoria** para ese CC (por ejemplo, una transcripción o generación en curso), ese task sigue ejecutándose aunque el registro en DB esté eliminado. Cuando termina, recrea el JSON del paciente en `storage/data/`.

Esto explica por qué el JSON reaparece incluso cuando el borrado de archivos sí funcionó.

**Fix requerido:** Antes de borrar los archivos, consultar `task_db.listar_activos()` y cancelar cualquier tarea activa del CC. La lógica de cancelación ya existe en `POST /api/tasks/{task_id}/cancelar` — hay que invocarla internamente desde `eliminar_paciente`.

---

## Resumen de cambios a hacer

| # | Archivo | Línea(s) | Cambio |
|---|---------|----------|--------|
| 1 | `backend/task_db.py` | Al final del `CREATE TABLE` inicial | Agregar `CREATE TABLE IF NOT EXISTS chat_history` con índice por `paciente_cc` |
| 2 | `backend/server.py` | 570 | Envolver el bloque DB en `try/except` para que un error en chat_history no mate todo el endpoint |
| 3 | `backend/server.py` | Inicio de `eliminar_paciente` | Cancelar tareas activas del CC antes de borrar archivos |
| 4 | `backend/server.py` | 531 | Agregar `WORKFLOW_AUDIOS_DIR` a la lista de directorios en `eliminar_formatos` |
| 5 | `dashboard/app/formatos/page.tsx` | 87–93 | Verificar `response.ok` y mostrar error si el backend falla |

---

## Orden de implementación

1. **Primero: Bug #1** — Sin esto, todo lo demás falla antes de llegar al problema real. Una vez que `chat_history` existe, el endpoint deja de crashear y los bugs restantes se vuelven detectables.

2. **Segundo: Bug #4** — El más peligroso. Si hay un workflow corriendo, el borrado no sirve de nada aunque el código sea correcto.

3. **Tercero: Bug #2** — Una vez que el backend funciona bien, hay que asegurarse de que el frontend informe correctamente cuando algo sale mal.

4. **Cuarto: Bug #3** — Limpieza menor, baja urgencia.

---

## Verificación post-fix

Secuencia de prueba para confirmar que el borrado funciona:

1. Subir audio de prueba → esperar que aparezca CC 36280228 en la lista
2. Abrir `/formatos` → clic en el ícono de borrar → confirmar
3. Verificar respuesta HTTP: debe ser 200 con `{"ok": true, "eliminados": N}`
4. La lista de pacientes debe quedar vacía inmediatamente
5. Verificar en filesystem:
   ```bash
   ls storage/data/        # debe estar vacío
   ls storage/docs/        # sin archivos 36280228
   ls storage/workflow_audios/  # sin .m4a del CC
   ```
6. Subir el mismo audio nuevamente → debe crear un paciente nuevo limpio sin rastros del anterior

---

## Estado actual del fantasma (para limpiar manualmente mientras se hace el fix)

Archivos que quedaron del paciente CC 36280228 y deben borrarse a mano antes de la prueba:

```
storage/data/36280228-completo.json
storage/docs/analisis_36280228_1a609767.docx
storage/docs/citacion_36280228_1a609767.docx
storage/docs/medidas_36280228_1a609767.docx
storage/docs/recomendaciones_36280228_1a609767.docx
storage/docs/valoracion_36280228_1a609767.docx
storage/pdfs/analisis_36280228_1a609767.pdf
storage/pdfs/citacion_36280228_1a609767.pdf
storage/pdfs/medidas_36280228_1a609767.pdf
storage/pdfs/recomendaciones_36280228_1a609767.pdf
storage/pdfs/valoracion_36280228_1a609767.pdf
storage/workflow_audios/36280228_20260523_021904.m4a
storage/workflow_audios/36280228_20260523_023610.m4a
storage/workflow_audios/36280228_20260523_024950.m4a
```
