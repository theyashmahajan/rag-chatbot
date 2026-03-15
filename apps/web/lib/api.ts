export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers = new Headers(options.headers || {});
  if (!isFormData) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  // Some endpoints (e.g., DELETE) intentionally return 204 with empty body.
  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json() as Promise<T>;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}
