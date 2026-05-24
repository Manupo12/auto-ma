"""
Paso 1 del workflow: transcribir audio con Deepgram nova-2.

Si el audio dura >30 min, se divide en chunks de 25 min con ffmpeg
y cada chunk se transcribe por separado. Resultados se concatenan
manteniendo timestamps relativos.
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def _log(msg: str):
    print(f"[TRANSCRIBIR {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _calcular_duracion_s(audio_path: Path) -> float:
    """Duración en segundos. Fallback a 0 si ffprobe no disponible."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(result.stdout.strip())
    except FileNotFoundError:
        _log("ffprobe no disponible - asumiendo audio largo (3600s)")
        return 3600.0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        _log("ffprobe error - asumiendo audio corto")
        return 0.0


def _necesita_chunking(duracion_s: float) -> bool:
    chunk_dur = int(os.getenv("AUDIO_CHUNK_DURATION_S", "1500"))
    return duracion_s > chunk_dur


def _dividir_en_chunks(audio_path: Path, chunk_dur_s: int, output_dir: Path) -> List[Path]:
    """Divide audio en chunks .wav de chunk_dur_s segundos. Retorna lista ordenada."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = output_dir / f"{audio_path.stem}_chunk_%03d.wav"
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-f", "segment", "-segment_time", str(chunk_dur_s),
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-loglevel", "error",
        str(output_pattern), "-y"
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    chunks = sorted(output_dir.glob(f"{audio_path.stem}_chunk_*.wav"))
    return chunks


def transcribir_audio_largo(audio_path: str, paciente_cc: str) -> Dict:
    """
    Transcribe audio. Si dura más de AUDIO_CHUNK_DURATION_S, chunkea con ffmpeg.
    Retorna dict {texto, segmentos, duracion, confianza_global, chunks_procesados, warnings}.
    """
    from backend.flujo_audio import transcribir_audio

    audio = Path(audio_path)
    if not audio.exists():
        raise FileNotFoundError(f"Audio no existe: {audio_path}")

    duracion = _calcular_duracion_s(audio)
    _log(f"Audio: {audio.name} ({duracion:.0f}s = {duracion/60:.1f} min)")

    warnings = []
    if not _necesita_chunking(duracion):
        _log("Sin chunking — un solo Deepgram")
        resultado = transcribir_audio(str(audio))
        texto = resultado.get("texto", "")
        confianza = resultado.get("confianza", 0)

        if not texto or not texto.strip():
            warnings.append("Transcripcion vacia - audio posiblemente en silencio")
            _log("WARNING: transcripcion vacia")

        if confianza < 0.4:
            warnings.append(f"Confianza muy baja del audio: {confianza:.2f}")
        elif confianza < 0.6:
            warnings.append(f"Confianza baja del audio: {confianza:.2f}")

        return {
            "ok": True,
            "texto": texto,
            "segmentos": resultado.get("segmentos", []),
            "duracion": duracion,
            "confianza_global": confianza,
            "chunks_procesados": 1,
            "warnings": warnings,
        }

    chunk_dur = int(os.getenv("AUDIO_CHUNK_DURATION_S", "1500"))
    temp_dir = Path(os.getenv("AUDIO_TEMP_DIR", "./storage/audios_temp")) / paciente_cc
    chunks = _dividir_en_chunks(audio, chunk_dur, temp_dir)
    _log(f"Chunks: {len(chunks)} de {chunk_dur}s c/u")

    textos = []
    chunk_resultados = []
    segmentos_global = []
    confianzas = []
    offset = 0.0

    for i, chunk_path in enumerate(chunks):
        _log(f"Chunk {i+1}/{len(chunks)}: {chunk_path.name}")
        try:
            r = transcribir_audio(str(chunk_path))
            texto_chunk = r.get("texto", "")

            if not texto_chunk or not texto_chunk.strip():
                _log(f"Chunk {i+1}: transcripcion vacia")
                warnings.append(f"Chunk {i+1}: transcripcion vacia")

            conf_chunk = r.get("confianza", 0)
            if conf_chunk < 0.4:
                warnings.append(f"Chunk {i+1}: confianza muy baja ({conf_chunk:.2f})")

            textos.append(texto_chunk)
            confianzas.append(conf_chunk)
            chunk_resultados.append({"ok": True})
            for seg in r["segmentos"]:
                segmentos_global.append({
                    **seg,
                    "inicio": seg["inicio"] + offset,
                    "fin": seg["fin"] + offset,
                })
            offset += r.get("duracion", chunk_dur)
        except Exception as e:
            _log(f"Chunk {i+1} fallo: {e}")
            chunk_resultados.append({"ok": False, "error": str(e)})
            confianzas.append(0.0)
            warnings.append(f"Chunk {i+1} no se pudo transcribir: {e}")

    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        _log(f"No se pudo eliminar temp {temp_dir}: {e}")

    confianza_global = sum(confianzas) / len(confianzas) if confianzas else 0
    if confianza_global < 0.4:
        warnings.append(f"Confianza global muy baja: {confianza_global:.2f}")
    elif confianza_global < 0.6:
        warnings.append(f"Confianza global baja: {confianza_global:.2f}")

    fallidos = sum(1 for r in chunk_resultados if not r.get("ok"))
    if len(chunks) > 0 and fallidos / len(chunks) > 0.2:
        warnings.append(f"{fallidos}/{len(chunks)} chunks fallaron")

    fallidos = sum(1 for r in chunk_resultados if not r.get("ok"))
    todos_fallaron = len(chunks) > 0 and fallidos == len(chunks)

    resultado = {
        "texto": "\n".join(textos),
        "segmentos": segmentos_global,
        "duracion": duracion,
        "confianza_global": confianza_global,
        "chunks_procesados": len(chunks),
        "warnings": warnings,
    }

    if todos_fallaron:
        resultado["ok"] = False
        resultado["error"] = f"Todos los {len(chunks)} chunks fallaron"
    elif fallidos > 0:
        resultado["ok"] = True
        resultado["error"] = f"{fallidos}/{len(chunks)} chunks fallaron"
    else:
        resultado["ok"] = True

    return resultado


def ejecutar(audio_path: str, paciente_cc: str) -> Dict:
    """Punto de entrada para workflow_runner."""
    return transcribir_audio_largo(audio_path, paciente_cc)
