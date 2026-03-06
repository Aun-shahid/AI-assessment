/** Service layer for communicating with the EduAssess backend. */

import { config } from "../config";

// ---------------------------------------------------------------------------
// Answer endpoint types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Session CRUD types
// ---------------------------------------------------------------------------

export interface SessionSummary {
  session_id: string;
  state: string;
  created_at: string;
  updated_at: string;
  last_message_preview: string | null;
}

export interface SessionListResponse {
  total: number;
  sessions: SessionSummary[];
}

export interface SessionMessage {
  role: string;
  content: string;
  timestamp: string;
}

export interface SessionDetailResponse {
  session_id: string;
  state: string;
  messages: SessionMessage[];
  identified_topics: string[];
  matched_los: Record<string, any>[];
  selected_los: Record<string, any>[];
  retrieved_chunks: Record<string, any>[];
  rejected_chunks: Record<string, any>[];
  generated_assessment: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateSessionResponse {
  session_id: string;
  state: string;
}

// ---------------------------------------------------------------------------
// Answer endpoint
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Session CRUD
// ---------------------------------------------------------------------------

/** List all sessions (paginated, most-recent first). */
export async function listSessions(
  skip = 0,
  limit = 50
): Promise<SessionListResponse> {
  const res = await fetch(
    `${config.backendUrl}/sessions/?skip=${skip}&limit=${limit}`
  );
  if (!res.ok) {
    throw new Error(`Backend error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

/** Load full session detail including all messages. */
export async function getSession(
  sessionId: string
): Promise<SessionDetailResponse> {
  const res = await fetch(`${config.backendUrl}/sessions/${sessionId}`);
  if (!res.ok) {
    throw new Error(`Backend error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

/** Create a new empty session. */
export async function createSession(): Promise<CreateSessionResponse> {
  const res = await fetch(`${config.backendUrl}/sessions/`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Backend error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

/** Delete a session by ID. */
export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${config.backendUrl}/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Backend error ${res.status}: ${await res.text()}`);
  }
}
