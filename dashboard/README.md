# RILO Dashboard — Rehabilitación Integral Laboral y Ocupacional SAS

Dashboard web para Sandra Patricia Polania Osorio, conectado al sistema de automatización de documentos clínicos ARL Positiva.

## Stack
- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **Lucide React** (iconos)

## Páginas
| Ruta | Descripción |
|------|-------------|
| `/` | Dashboard principal con estadísticas |
| `/pacientes` | Búsqueda y visualización de pacientes |
| `/formatos` | Lista de 7 formatos clínicos, filtros por estado |
| `/chat` | Chat con Tomy (Hermes Agent) — corregir docs, buscar info |
| `/subir-audio` | Subir audio de cita → Deepgram → transcripción |

## API Routes (conexión con Hermes)
| Ruta | Método | Descripción |
|------|--------|-------------|
| `/api/chat` | POST | Envía mensaje a Hermes Agent |
| `/api/upload-audio` | POST | Sube audio para transcripción con Deepgram |
| `/api/hermes/*` | * | Proxy rewrite a Hermes (localhost:8000) |

## Cómo ejecutar

```bash
cd /root/fisioterapia/dashboard
npm run dev
# → http://localhost:3000
```

## Conexión con Hermes
El dashboard se conecta al backend de Hermes Agent mediante:
- API Routes de Next.js → proxy a `http://localhost:8000`
- Variables de entorno en `.env.local`:
  ```
  NEXT_PUBLIC_HERMES_API=http://localhost:8000/api
  ```

## Personalización
Este es un template base. Para personalizar:
1. Edita los componentes en `components/`
2. Modifica las páginas en `app/`
3. Conecta las API routes reales en `app/api/`
4. Añade más páginas según necesites

## Estructura
```
dashboard/
├── app/
│   ├── layout.tsx          # Layout principal con sidebar
│   ├── page.tsx            # Dashboard home
│   ├── globals.css         # Estilos globales + Tailwind
│   ├── pacientes/page.tsx  # Búsqueda de pacientes
│   ├── formatos/page.tsx   # Lista de formatos
│   ├── chat/page.tsx       # Chat con Tomy
│   ├── subir-audio/page.tsx # Upload + transcripción
│   └── api/
│       ├── chat/route.ts   # Proxy chat → Hermes
│       └── upload-audio/route.ts # Proxy upload → Hermes
├── components/
│   └── Sidebar.tsx         # Barra lateral de navegación
├── lib/
│   └── hermes.ts           # Cliente API para Hermes
├── public/                 # Archivos estáticos
├── package.json
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

## Próximos pasos
- [ ] Conectar pacientes reales desde el backend
- [ ] Mostrar documentos generados (DOCX/PDF)
- [ ] Vista previa de formatos
- [ ] Historial de actividad
- [ ] Notificaciones en tiempo real
- [ ] Autenticación de usuario
