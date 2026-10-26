import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Check, MessageSquare } from "lucide-react";

import { api } from "../api";
import type { Row } from "../types";
import { useWorkspace } from "../context";
import { Badge, Empty, ErrorText, Heading, useLoad } from "../components/ui";

export function Prompts() {
  const { id } = useParams();
  const { bots, reload, notify } = useWorkspace();
  const bot = bots.find((b) => b.id === id);
  const { data: versions, error, load } = useLoad(`/chatbots/${id}/prompts`);
  const [content, setContent] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (bot) setContent(bot.system_prompt);
  }, [bot?.id, bot?.system_prompt]);
  if (!bot)
    return (
      <div className="page">
        <Empty
          title="Chatbot unavailable"
          text="Choose an assistant from your chatbot list."
        />
      </div>
    );
  return (
    <div className="page">
      <Heading
        title="Shape your assistant"
        description={`Instructions for ${bot.name}. Changes apply to the next message.`}
      >
        <Link className="button" to={`/chat?bot=${id}`}>
          <MessageSquare size={15} />
          Test in playground
        </Link>
      </Heading>
      <ErrorText text={error} />
      <div className="prompt-layout">
        <section className="panel">
          <div className="section-heading">
            <h2>System instructions</h2>
            <Badge tone="blue">DYNAMIC PROMPT</Badge>
          </div>
          <p className="muted">
            Define identity, language, tone, knowledge policy and business
            rules.
          </p>
          <label className="sr-only" htmlFor="prompt">
            System instructions
          </label>
          <textarea
            id="prompt"
            className="prompt-editor"
            maxLength={16000}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <div className="row spread">
            <small>{content.length.toLocaleString()} / 16,000 characters</small>
            <button
              className="button primary"
              disabled={busy || !content.trim()}
              onClick={async () => {
                setBusy(true);
                try {
                  await api(`/chatbots/${id}/prompt`, "PUT", { content });
                  await reload();
                  await load();
                  notify("Prompt version saved");
                } catch (e) {
                  notify((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Saving…" : "Save instructions"}
              <Check size={15} />
            </button>
          </div>
          <div className="notice small-notice">
            Application security and strict RAG validation apply independently
            of these instructions.
          </div>
        </section>
        <section className="panel version-panel">
          <h2>Version history</h2>
          <p className="muted">Every save creates a new revision.</p>
          {versions?.map((v: Row, i: number) => (
            <div className="version" key={v.id}>
              <div className="row spread">
                <strong>
                  {i === 0
                    ? "Current version"
                    : `Revision ${versions.length - i}`}
                </strong>
                {i === 0 && <Badge tone="green">Live</Badge>}
              </div>
              <small>{new Date(v.created_at).toLocaleString()}</small>
              <details>
                <summary>View instructions</summary>
                <p>{v.content}</p>
              </details>
              {i > 0 && (
                <button
                  className="text-button"
                  onClick={async () => {
                    try {
                      await api(
                        `/chatbots/${id}/prompts/${v.id}/restore`,
                        "POST",
                      );
                      await reload();
                      await load();
                      notify("Previous prompt restored as a new version");
                    } catch (e) {
                      notify((e as Error).message);
                    }
                  }}
                >
                  Restore this version
                </button>
              )}
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
