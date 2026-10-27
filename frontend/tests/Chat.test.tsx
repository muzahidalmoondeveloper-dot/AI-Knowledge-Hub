import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Chat } from "../src/pages/Chat";
import { Context } from "../src/context";
import { api, streamChat } from "../src/api";

vi.mock("../src/api", () => ({
  api: vi.fn(),
  streamChat: vi.fn(),
  request: vi.fn(),
  setToken: vi.fn(),
}));
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("keeps the first streamed response when creating and navigating to a conversation", async () => {
  const conversation = {
    id: "new-conversation",
    name: "",
    title: "New conversation",
    chatbot_id: "bot-1",
    updated_at: new Date().toISOString(),
  };
  let created = false;
  vi.mocked(api).mockImplementation(async (path, method) => {
    if (path === "/conversations" && method === "POST") {
      created = true;
      return conversation;
    }
    if (path === "/conversations") return created ? [conversation] : [];
    if (path.endsWith("/messages")) return [];
    return null;
  });
  vi.mocked(streamChat).mockImplementation(
    async (_id, _content, _signal, onEvent) => {
      onEvent({ type: "start" });
      await new Promise((resolve) => setTimeout(resolve, 20));
      onEvent({
        type: "token",
        text: "**Employees receive twenty days of leave.**",
      });
      onEvent({ type: "done", sources: [] });
    },
  );
  const workspace = {
    user: { id: "owner", email: "owner@example.com", role: "user" },
    bots: [
      {
        id: "bot-1",
        name: "Policy assistant",
        strict_rag: true,
        allow_cloud: false,
      },
    ],
    kbs: [],
    models: [],
    providers: [],
    embeddings: [],
    reload: async () => {},
    notify: vi.fn(),
  };
  render(
    <Context.Provider value={workspace}>
      <MemoryRouter initialEntries={["/chat"]}>
        <Routes>
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:id" element={<Chat />} />
        </Routes>
      </MemoryRouter>
    </Context.Provider>,
  );
  const user = userEvent.setup();
  await user.type(
    screen.getByLabelText("Your message"),
    "How much annual leave?",
  );
  await user.click(screen.getByTitle("Send message"));
  await waitFor(() =>
    expect(
      screen.getByText("Employees receive twenty days of leave."),
    ).toBeTruthy(),
  );
  expect(screen.getByText("How much annual leave?")).toBeTruthy();
  expect(
    screen.getByText("Employees receive twenty days of leave.").tagName,
  ).toBe("STRONG");
  expect(streamChat).toHaveBeenCalledWith(
    "new-conversation",
    "How much annual leave?",
    expect.any(AbortSignal),
    expect.any(Function),
  );
});
