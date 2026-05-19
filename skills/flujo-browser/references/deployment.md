# Guía de Despliegue — Sistema RILO SAS

## Requisitos
- Docker (Hermes Agent corriendo)
- Python 3.11+ con pip
- Node.js 20+ con npm (para dashboard)

## Iniciar el sistema

### 1. Servidor FastAPI (backend)
```bash
cd /root/fisioterapia
pip install fastapi uvicorn python-multipart requests
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
# Verificar: curl http://localhost:8000/api/health
```

### 2. Dashboard Next.js
```bash
cd /root/fisioterapia/dashboard
npm run dev
# → http://localhost:3000
```

### 3. Endpoints disponibles
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /api/health | Health check |
| GET | /api/stats | Estadísticas |
| GET | /api/pacientes | Listar pacientes |
| GET | /api/pacientes/{cc} | Obtener paciente |
| GET | /api/pacientes/{cc}/formatos | Formatos del paciente |
| POST | /api/pacientes/{cc}/generar | Generar formatos |
| POST | /api/pacientes/{cc}/formatos/{fmt}/corregir | Corregir formato |
| POST | /api/chat | Chat con Tomy |
| POST | /api/upload-audio | Subir audio → Deepgram |
| GET | /api/download/{filename} | Descargar archivo |

### 4. Tests
```bash
cd /root/fisioterapia
python backend/custody.py
python backend/orquestador.py --datos storage/data/juan_duran.json --solo-validar
```

### 5. Claude Code (auditoría)
```bash
cd /root/fisioterapia && claude
```
