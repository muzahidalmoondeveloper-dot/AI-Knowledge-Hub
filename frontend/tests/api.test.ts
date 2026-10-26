import { afterEach, describe, expect, it, vi } from "vitest";
import { api, setToken, streamChat } from "../src/api";

afterEach(() => {
  vi.unstubAllGlobals();
  setToken("");
});

function sseResponse(frames: string) {
  const bytes = new TextEncoder().encode(frames);
  return new Response(
    new ReadableStream({
      start(controller) {
        // Split inside arbitrary UTF-8 characters and SSE frame boundaries.
        for (let i = 0; i < bytes.length; i += 3)
          controller.enqueue(bytes.slice(i, i + 3));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream" } },
  );
}

describe("authenticated API and streaming", () => {
  it("preserves Bengali text across byte boundaries and requires a completion event", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        sseResponse(
          'data: {"type":"token","text":"বাংলা উত্তর"}\n\ndata: {"type":"done","sources":[]}\n\n',
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    setToken("memory-only-token");
    const events: any[] = [];
    await streamChat(
      "conversation",
      "প্রশ্ন",
      new AbortController().signal,
      (event) => events.push(event),
    );
    expect(events.map((e) => e.type)).toEqual(["token", "done"]);
    expect(events[0].text).toBe("বাংলা উত্তর");
    expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe(
      "Bearer memory-only-token",
    );
    expect(fetcher.mock.calls[0][1].credentials).toBe("include");
  });
  it("rejects an incomplete stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse('data: {"type":"token","text":"partial"}\n\n'),
        ),
    );
    await expect(
      streamChat("id", "question", new AbortController().signal, () => {}),
    ).rejects.toThrow("Response interrupted");
  });
  it("refreshes an expired access token and retries once", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(Response.json({ access_token: "rotated-access" }))
      .mockResolvedValueOnce(Response.json([{ id: "owned" }]));
    vi.stubGlobal("fetch", fetcher);
    setToken("expired");
    expect(await api("/chatbots")).toEqual([{ id: "owned" }]);
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/auth/refresh");
    expect(fetcher.mock.calls[2][1].headers.get("Authorization")).toBe(
      "Bearer rotated-access",
    );
  });
  it("surfaces safe structured API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { error: { code: "not_found", message: "Resource not found" } },
            { status: 404 },
          ),
        ),
    );
    await expect(api("/chatbots/missing")).rejects.toThrow(
      "Resource not found",
    );
  });
});
