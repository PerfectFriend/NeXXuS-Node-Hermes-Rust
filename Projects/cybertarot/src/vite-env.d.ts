
/// <reference types="vite/client" />

interface ImportMeta {
  readonly env: {
    readonly VITE_API_URL: string | undefined;
    readonly VITE_OLLAMA_URL: string | undefined;
    // Add more if needed
  };
}