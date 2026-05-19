# Next.js Upload Bypass — Técnica para archivos > 4MB

## Problema
Next.js App Router impone un límite de ~4MB en el body de las peticiones a route handlers.
Los audios de iPhone (M4A) fácilmente superan este límite → la subida falla sin error claro.

El `experimental.serverActions.bodySizeLimit` solo afecta a Server Actions, NO a route handlers.

## Solución: Bypass directo a FastAPI

En lugar de pasar por el proxy de Next.js (`/api/upload-audio`), el frontend llama
directamente al backend:

```tsx
// ❌ MAL — pasa por Next.js, límite 4MB
const res = await fetch("/api/upload-audio", {
  method: "POST",
  body: formData,
});

// ✅ BIEN — directo a FastAPI, sin límite artificial
const res = await fetch("http://localhost:8000/api/upload-audio", {
  method: "POST",
  body: formData,
});
```

## Bonus: Validación robusta de tipos de archivo

Los archivos M4A del iPhone a veces tienen:
- `file.type === ""` (navegador no reconoce el MIME)
- Extensión en mayúsculas `.M4A`

Validación robusta:

```tsx
const ext = file.name.split('.').pop()?.toLowerCase() || '';
const tipos = ['m4a', 'mp3', 'wav', 'mp4', 'aac', 'ogg', 'flac'];
const esAudio = file.type.startsWith('audio/') || 
                file.type.startsWith('video/') ||
                tipos.some(t => file.name.toLowerCase().endsWith('.' + t)) ||
                tipos.some(t => ext === t);
```

## Archivos afectados
- `dashboard/app/subir-audio/page.tsx` — ya corregido (Mayo 2026)
