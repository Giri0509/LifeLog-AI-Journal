/** Credentialed requests with bounded waits and no automatic mutation retries. */
export async function apiFetch(input: string, options?: RequestInit): Promise<Response> {
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
  const url = input.replace("http://localhost:8000", apiBase);
  const timeout = AbortSignal.timeout(90000);
  const signal = options?.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  try {
    const response = await fetch(url, { ...options, signal, credentials: "include" });
    if (response.status === 401 && !url.includes("/api/auth/")) {
      window.dispatchEvent(new Event("lifelog-session-expired"));
    }
    return response;
  } catch (error) {
    if (options?.signal?.aborted) throw error;
    throw new Error(timeout.aborted || (error instanceof Error && error.name === "TimeoutError")
      ? "The request timed out. Check whether your changes were saved before retrying."
      : "Unable to reach the server. Check your connection and try again.", { cause: error });
  }
}

export async function responseError(response: Response, fallback: string): Promise<Error> {
  const data = await response.json().catch(() => null);
  if (typeof data?.detail === "string") return new Error(data.detail);
  if (Array.isArray(data?.detail)) {
    const messages = data.detail.map((item: { msg?: unknown }) => typeof item.msg === "string" ? item.msg : "").filter(Boolean);
    if (messages.length) return new Error(messages.join(" ").slice(0, 1000));
  }
  return new Error(fallback);
}

