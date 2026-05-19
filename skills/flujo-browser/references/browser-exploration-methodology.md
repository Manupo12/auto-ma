# Metodología de Exploración de Portales

Técnicas y patrones descubiertos durante 7 pasadas de exploración de Medifolios y ARL Positiva.

## Principio fundamental

> El usuario (hijo/a de Sandra, técnico) espera exploración EXHAUSTIVA. 4, 5, 6 pasadas hasta que no quede NADA sin tocar. Si dice "ve más allá", "itera", es FRUSTRACIÓN: hay elementos importantes no descubiertos.

## Orden de exploración (prioridad)

1. Menús laterales (sidebar, accordions expandibles)
2. Dropdowns () con sub-ítems
3. Tabs/pestañas dentro de secciones
4. Secciones ocultas (display:none, collapse)
5. Iframes con src=about:blank (se cargan al activar)
6. Paneles laterales derechos (popup panels)
7. Botones pequeños con íconos (sin texto)
8. Formularios con campos disabled (se activan al cargar paciente)

## Técnicas de extracción masiva con JS

### Volcar toda la estructura de la página
```javascript
var result = {};
result.dropdowns = {};
document.querySelectorAll('.dropdown-menu, [class*="dropdown"]').forEach(function(dd) {
    var items = [];
    dd.querySelectorAll('a, li, [role="menuitem"]').forEach(function(item) {
        items.push(item.textContent.trim().substring(0, 50));
    });
    if (items.length > 0) result.dropdowns[name] = items;
});
// Repetir para accordions, tabs, sections, buttons, iframes
JSON.stringify(result);
```

### Cargar paciente en Medifolios (JS agresivo)
```javascript
var docField = document.getElementById('numero_id');
docField.value = '55162801';  // CC de Sandra
docField.dispatchEvent(new Event('input', {bubbles: true}));
docField.dispatchEvent(new Event('change', {bubbles: true}));
docField.blur();
docField.focus();
docField.blur();
// También disparar Enter
docField.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}));
```

### Extraer datos de formulario Medifolios
```javascript
var d = {};
['numero_id','nombre1','nombre2','apellido1','apellido2',
 'fecha_nacimiento','telefono','direccion','email'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) d[id] = el.value || el.textContent?.trim();
});
// Comboboxes: acceder a options[selectedIndex].text
JSON.stringify(d);
```

### Buscar siniestro en campo observaciones
```python
import re
match = re.search(r'NO\.?\s*SINIESTRO\s*(\d+)', observaciones, re.IGNORECASE)
siniestro = match.group(1) if match else None
```

### Seleccionar profesional en Agenda Citas Medifolios
```javascript
var select = document.querySelector('select');
select.value = '168-0';  // SANDRA PATRICIA POLANIA - TODOS LOS PUNTOS
select.dispatchEvent(new Event('change', {bubbles: true}));
```

### Hacer visible un panel oculto
```javascript
var panel = document.getElementById('div_panel_lateral_historia');
panel.setAttribute('style', 'display: block !important; visibility: visible !important;');
```

## Pacientes de prueba que funcionan

| Portal | CC | Nombre | Notas |
|--------|-----|--------|-------|
| Medifolios | 55162801 | SANDRA PATRICIA POLANIA OSORIO | La propia Sandra, carga OK |
| Medifolios | 36169589 | NUBIA MARIA RIVERA SUAREZ | Tiene siniestro 503401505 |
| Positiva | 1193143688 | JUAN CARLOS DURAN NARVAEZ | 2 siniestros, S611 |

## Pitfalls

1. **Sesión expira en 5-15 min** — si snapshot devuelve "(empty page)", re-login inmediato
2. **Popup "Cambia tu contraseña"** en Medifolios cada login — cerrar con button "Close"
3. **NUNCA usar Enter en campo de búsqueda** sin antes dispatchEvent — el evento nativo no se dispara
4. **El siniestro NO está en Pacientes** — está en Agenda Citas → popup → Observaciones
5. **El campo `numero_id` acepta valor pero no dispara búsqueda** — requiere blur + focus + Enter vía dispatchEvent
6. **Los comboboxes en modo "disabled"** tienen datos pero no se pueden leer con `.value` — usar `.textContent`
