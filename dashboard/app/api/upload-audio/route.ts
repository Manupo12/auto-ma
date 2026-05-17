import { NextRequest, NextResponse } from "next/server";

/**
 * API Route para subir audio y enviarlo a Deepgram vía Hermes.
 * El dashboard envía el archivo aquí, y esta ruta lo reenvía al backend de Hermes.
 */
export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const audio = formData.get("audio") as File;
    const paciente_cc = formData.get("paciente_cc") as string;

    if (!audio || !paciente_cc) {
      return NextResponse.json(
        { error: "Faltan datos: audio y paciente_cc son requeridos" },
        { status: 400 }
      );
    }

    // Reenviar a Hermes Agent
    const backendFormData = new FormData();
    backendFormData.append("audio", audio);
    backendFormData.append("paciente_cc", paciente_cc);

    const hermesResponse = await fetch("http://localhost:8000/api/upload-audio", {
      method: "POST",
      body: backendFormData,
    });

    if (!hermesResponse.ok) {
      throw new Error(`Hermes respondió ${hermesResponse.status}`);
    }

    const data = await hermesResponse.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error en upload API:", error);
    return NextResponse.json(
      { error: "Error al procesar el audio" },
      { status: 500 }
    );
  }
}
