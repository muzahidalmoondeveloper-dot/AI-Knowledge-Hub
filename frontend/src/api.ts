let accessToken = "";
let refreshPromise: Promise<boolean> | null = null;
export function setToken(token: string) {
  accessToken = token;
}
export async function refresh(): Promise<boolean> {
  if (!refreshPromise)
    refreshPromise = fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    })
      .then(async (r) => {
        if (!r.ok) return false;
        setToken((await r.json()).access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  return refreshPromise;
}
export async function request(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body)
    headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response = await fetch("/api/v1" + path, {
    ...options,
    headers,
    credentials: "include",
  });
  if (
    response.status === 401 &&
    retry &&
    !path.startsWith("/auth/") &&
    (await refresh())
  )
    return request(path, options, false);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error?.message || "Request failed. Please try again.");
  }
  return response;
}
export async function api(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<any> {
  const response = await request(path, {
    method,
    body:
      data instanceof FormData
        ? data
        : data === undefined
          ? undefined
          : JSON.stringify(data),
  });
  return response.status === 204 ? null : response.json();
}
export async function streamChat(
  id: string,
  content: string,
  signal: AbortSignal,
  onEvent: (event: any) => void,
) {
  const response = await request(`/conversations/${id}/stream`, {
    method: "POST",
    body: JSON.stringify({ content }),
    signal,
  });
  if (!response.body) throw new Error("Streaming is unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "",
    doneEvent = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((l) => l.startsWith("data: "))
          .map((l) => l.slice(6))
          .join("\n");
        if (data) {
          const event = JSON.parse(data);
          if (event.type === "done") doneEvent = true;
          onEvent(event);
        }
      }
      if (done) break;
    }
    if (!doneEvent)
      throw new Error(
        "Response interrupted. Reopen the conversation to check its status.",
      );
  } finally {
    reader.releaseLock();
  }
}
