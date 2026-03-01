/** Application configuration – values come from Vite env variables. */

/// <reference types="vite/client" />

export const config = {
  /** Base URL of the FastAPI backend (no trailing slash). */
  backendUrl: import.meta.env.VITE_BACKEND_URL || "http://localhost:8000",
};
