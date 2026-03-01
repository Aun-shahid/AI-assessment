/** Service layer for communicating with the EduAssess backend. */

import { config } from "../config";

export interface AnswerRequest {
  session_id?: string | null;
  message: string;
}

export interface AnswerResponse {
  session_id: string;
  response: string;
  state: string;
  data?: Record<string, any> | null;
}

/**
 * Send a user message to the /answer/ endpoint and return the agent's reply.
 */
export async function sendMessage(
  payload: AnswerRequest
): Promise<AnswerResponse> {
  const res = await fetch(`${config.backendUrl}/answer/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Backend error ${res.status}: ${errorBody}`);
  }

  return res.json();
}
