import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  FileText,
  MessageSquare,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
import { api, streamChat } from "../api";
import type { Message, Row } from "../types";
import { useWorkspace } from "../context";
import { Badge, ErrorText } from "../components/ui";
import { MessageMarkdown } from "../components/MessageMarkdown";

export function Chat() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { bots, notify } = useWorkspace();
  const [conversations, setConversations] = useState<Row[]>([]),
    [messages, setMessages] = useState<Message[]>([]),
    [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [showHistory, setShowHistory] = useState(false),
    [conversationDetails, setConversationDetails] = useState<Row | null>(null),
    [hasOlderMessages, setHasOlderMessages] = useState(false),
    [hasOlderConversations, setHasOlderConversations] = useState(false),
    [error, setError] = useState(""),
    [botId, setBotId] = useState(
      new URLSearchParams(location.search).get("bot") || "",
    );
  const abort = useRef<AbortController | null>(null),
    bottom = useRef<HTMLDivElement>(null),
    pendingConversation = useRef<string | null>(null);
  const conversation =
    conversations.find((c) => c.id === id) ||
    (conversationDetails?.id === id ? conversationDetails : null);
  const bot =
    bots.find((b) => b.id === (conversation?.chatbot_id || botId)) || bots[0];
  async function loadConversations() {
    try {
      const rows = await api("/conversations");
      setConversations(rows);
      setHasOlderConversations(rows.length === 50);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    loadConversations();
    return () => abort.current?.abort();
  }, []);
  useEffect(() => {
    if (pendingConversation.current === id) {
      pendingConversation.current = null;
      return;
    }
    let active = true;
    setMessages([]);
    setHasOlderMessages(false);
    setError("");
    if (id)
      Promise.all([
        api(`/conversations/${id}/messages?latest=true`),
        api(`/conversations/${id}`),
      ])
        .then(([data, details]) => {
          if (active) {
            setMessages(data);
            setHasOlderMessages(data.length === 100);
            setConversationDetails(details);
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [id]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  async function newConversation() {
    if (!bot) return;
    const c = await api("/conversations", "POST", {
      chatbot_id: bot.id,
      title: "New conversation",
    });
    await loadConversations();
    pendingConversation.current = c.id;
    navigate(`/chat/${c.id}`);
    return c.id;
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || !bot || busy) return;
    const content = question.trim();
    setBusy(true);
    setError("");
    setQuestion("");
    let cid = id;
    try {
      if (!cid) {
        cid = await newConversation();
      }
      const temporary = crypto.randomUUID();
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "user",
          content,
          status: "complete",
          sources: [],
        },
        {
          id: temporary,
          role: "assistant",
          content: "",
          status: "generating",
          sources: [],
        },
      ]);
      abort.current = new AbortController();
      await streamChat(cid!, content, abort.current.signal, (event) => {
        if (event.type === "error") throw new Error(event.message);
        setMessages((previous) =>
          previous.map((m) =>
            m.id === temporary
              ? {
                  ...m,
                  content:
                    event.type === "token" ? m.content + event.text : m.content,
                  status: event.type === "done" ? "complete" : m.status,
                  sources: event.type === "done" ? event.sources : m.sources,
                }
              : m,
          ),
        );
      });
      await loadConversations();
    } catch (e) {
      setError(
        (e as Error).name === "AbortError"
          ? "Generation stopped. Partial text is marked interrupted."
          : (e as Error).message,
      );
      setMessages((previous) =>
        previous.map((m) =>
          m.status === "generating" ? { ...m, status: "interrupted" } : m,
        ),
      );
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }
  return (
    <div className={`chat-page ${showHistory ? "show-history" : ""}`}>
      <aside className="conversation-sidebar">
        <div className="section-heading">
          <h2>Conversations</h2>
          <MessageSquare size={18} />
        </div>
        <button
          className="button"
          disabled={busy}
          onClick={() => {
            navigate("/chat");
            setMessages([]);
          }}
        >
          <Plus size={16} />
          New conversation
        </button>
        <div className="conversation-list">
          {conversations.map((c) => (
            <div
              className={`conversation-item ${c.id === id ? "selected" : ""}`}
              key={c.id}
            >
              <button
                disabled={busy}
                onClick={() => {
                  navigate(`/chat/${c.id}`);
                  setShowHistory(false);
                }}
              >
                <MessageSquare size={15} />
                <span>
                  {c.title}
                  <small>{new Date(c.updated_at).toLocaleDateString()}</small>
                </span>
              </button>
              <button
                className="icon-button danger"
                disabled={busy}
                title="Delete conversation"
                onClick={async () => {
                  if (confirm("Delete this conversation?"))
                    try {
                      await api(`/conversations/${c.id}`, "DELETE");
                      await loadConversations();
                      if (c.id === id) navigate("/chat");
                    } catch (e) {
                      notify((e as Error).message);
                    }
                }}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
          {!conversations.length && (
            <p className="quiet-empty">Your conversations will live here.</p>
          )}
          {hasOlderConversations && (
            <button
              className="text-button"
              disabled={busy}
              onClick={async () => {
                try {
                  const rows = await api(
                    `/conversations?offset=${conversations.length}`,
                  );
                  setConversations((previous) => [...previous, ...rows]);
                  setHasOlderConversations(rows.length === 50);
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Load older conversations
            </button>
          )}
        </div>
      </aside>
      <section className="chat-main">
        <div className="chat-header">
          <button
            className="icon-button mobile-history"
            aria-label="Toggle conversation history"
            aria-expanded={showHistory}
            onClick={() => setShowHistory(!showHistory)}
          >
            <MessageSquare size={18} />
          </button>
          <span className="bot-icon">
            <Bot size={22} />
          </span>
          <div>
            {id ? (
              <h3>{bot?.name || "Assistant"}</h3>
            ) : (
              <select
                aria-label="Choose chatbot"
                value={bot?.id || ""}
                disabled={busy}
                onChange={(e) => setBotId(e.target.value)}
              >
                {bots.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            )}
            <small>
              {bot?.strict_rag
                ? "Strict RAG · Verified evidence extracts"
                : "General mode · Model knowledge enabled"}
            </small>
          </div>
          <Badge tone={bot?.allow_cloud ? "blue" : "green"}>
            {bot?.allow_cloud ? "Cloud permitted" : "Local only"}
          </Badge>
        </div>
        <div className="messages">
          {hasOlderMessages && (
            <button
              className="button"
              disabled={busy}
              onClick={async () => {
                try {
                  const rows = await api(
                    `/conversations/${id}/messages?latest=true&offset=${messages.length}`,
                  );
                  setMessages((previous) => [...rows, ...previous]);
                  setHasOlderMessages(rows.length === 100);
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Load earlier messages
            </button>
          )}
          {!messages.length && (
            <div className="chat-welcome">
              <span className="welcome-icon">
                <Sparkles size={35} />
              </span>
              <p className="eyebrow">YOUR KNOWLEDGE, IN CONVERSATION</p>
              <h2>What would you like to explore?</h2>
              <p>
                Ask about your documents. Follow your curiosity.
                <br />
                Every good answer starts with a question.
              </p>
              {!bots.length && (
                <Link className="button primary" to="/chatbots">
                  Create your first chatbot
                  <ArrowRight size={15} />
                </Link>
              )}
            </div>
          )}
          {messages.map((m) => (
            <article className={`message ${m.role}`} key={m.id}>
              <span className={m.role === "user" ? "user-avatar" : "bot-icon"}>
                {m.role === "user" ? "Y" : <Sparkles size={18} />}
              </span>
              <div className="message-body">
                <strong>
                  {m.role === "user" ? "You" : bot?.name || "Assistant"}
                </strong>
                {m.content ? (
                  m.role === "assistant" ? (
                    <MessageMarkdown content={m.content} />
                  ) : (
                    <div className="extract-text">{m.content}</div>
                  )
                ) : (
                  <span className="thinking">Searching and thinking…</span>
                )}
                {m.status !== "complete" && (
                  <small className="message-status">{m.status}</small>
                )}
                {!!m.sources?.length && (
                  <div className="sources">
                    <span className="eyebrow">
                      {bot?.strict_rag
                        ? "VERIFIED SOURCES"
                        : "RETRIEVED CONTEXT"}
                    </span>
                    {m.sources.map((s, i) => (
                      <details key={s.source_id + i}>
                        <summary>
                          <FileText size={14} />
                          <strong>
                            [{i + 1}] {s.title}
                          </strong>
                          {s.page && <span>Page {s.page}</span>}
                        </summary>
                        <blockquote>{s.excerpt}</blockquote>
                        <small>
                          Similarity {s.score.toFixed(2)} · Chunk{" "}
                          {s.source_id.slice(0, 8)}
                        </small>
                      </details>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
          <div ref={bottom} />
        </div>
        <div className="composer-area">
          <ErrorText text={error} />
          <form className="composer" onSubmit={send}>
            <textarea
              aria-label="Your message"
              rows={2}
              placeholder="Ask a question about your knowledge…"
              maxLength={12000}
              value={question}
              disabled={!bot}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!busy) send(e);
                }
              }}
            />
            <div className="composer-bottom">
              <span>
                <ShieldCheck size={13} />{" "}
                {bot?.strict_rag
                  ? "Evidence checked before display"
                  : "General AI answers may be inaccurate"}
              </span>
              {busy ? (
                <button
                  type="button"
                  className="send-button"
                  title="Stop generation"
                  onClick={() => abort.current?.abort()}
                >
                  <Square size={15} />
                </button>
              ) : (
                <button
                  className="send-button"
                  disabled={!bot || !question.trim()}
                  title="Send message"
                >
                  <Send size={17} />
                </button>
              )}
            </div>
          </form>
          <small className="chat-disclaimer">
            {bot?.strict_rag
              ? "Strict answers quote your documents. Relevance still needs your judgment."
              : "Review important answers against their original sources."}
          </small>
        </div>
      </section>
    </div>
  );
}
