import { NextRequest, NextResponse } from "next/server";

/**
 * API Route para enviar mensajes a Hermes Agent.
 * El dashboard envía el mensaje aquí, y esta ruta lo reenvía al backend de Hermes.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { mensaje, paciente_cc } = body;

    // Reenviar a Hermes Agent (corre en localhost)
    const hermesResponse = await fetch("http://localhost:8000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje, paciente_cc }),
    });

    if (!hermesResponse.ok) {
      throw new Error(`Hermes respondió ${hermesResponse.status}`);
    }

    const data = await hermesResponse.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error en chat API:", error);
    return NextResponse.json(
      { error: "Error al comunicarse con el asistente" },
      { status: 500 }
    );
  }
}
