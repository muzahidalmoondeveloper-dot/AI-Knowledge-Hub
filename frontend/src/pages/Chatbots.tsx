import { useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Plus, Search } from "lucide-react";

import { api } from "../api";
import type { Row } from "../types";
import { useWorkspace } from "../context";
import { Editor, Empty, Heading } from "../components/ui";
import type { Field } from "../components/ui";
import { BotCard } from "../components/BotCard";

export function Chatbots() {
  const { bots, models, kbs, reload, notify } = useWorkspace();
  const [editing, setEditing] = useState<Row | "new" | null>(null),
    [filter, setFilter] = useState("");
  const initial: Record<string, any> | null =
    editing === "new"
      ? {
          name: "",
          description: "",
          model_id: models.find((m) => m.is_default)?.id || models[0]?.id || "",
          knowledge_base_id: null,
          fallback_model_id: null,
          enabled: true,
          strict_rag: true,
          allow_cloud: false,
          streaming: true,
          top_k: 5,
          score_threshold: 0.35,
          temperature: 0.2,
          max_tokens: 1024,
          timeout: 90,
        }
      : editing;
  const fields: Field[] = [
    { key: "name", label: "Chatbot name", required: true, max: 100 },
    { key: "description", label: "Description", type: "textarea", max: 2000 },
    {
      key: "model_id",
      label: "Chat model",
      required: true,
      options: models.map((m) => ({ value: m.id, label: m.name })),
    },
    {
      key: "knowledge_base_id",
      label: "Knowledge base",
      options: kbs.map((k) => ({ value: k.id, label: k.name })),
    },
    {
      key: "fallback_model_id",
      label: "Fallback model (optional)",
      options: models.map((m) => ({ value: m.id, label: m.name })),
    },
    ...[
      ["enabled", "Chatbot enabled"],
      ["strict_rag", "Strict RAG: verified evidence quotes only"],
      ["allow_cloud", "Allow cloud processing of questions and evidence"],
      ["streaming", "Enable streaming"],
    ].map(([key, label]) => ({ key, label, type: "checkbox" })),
    {
      key: "top_k",
      label: "Retrieval passages",
      type: "number",
      min: 1,
      max: 20,
    },
    {
      key: "score_threshold",
      label: "Minimum cosine similarity",
      type: "number",
      min: 0,
      max: 1,
      step: 0.05,
    },
    {
      key: "temperature",
      label: "Temperature",
      type: "number",
      min: 0,
      max: 2,
      step: 0.1,
    },
    {
      key: "max_tokens",
      label: "Maximum output tokens",
      type: "number",
      min: 32,
      max: 32768,
    },
    {
      key: "timeout",
      label: "Model timeout (seconds)",
      type: "number",
      min: 5,
      max: 300,
    },
  ];
  return (
    <div className="page">
      <Heading
        title="Your chatbots"
        description="Give every part of your knowledge its own assistant."
      >
        <button
          className="button primary"
          disabled={!models.length}
          onClick={() => setEditing("new")}
        >
          <Plus size={16} />
          Create chatbot
        </button>
      </Heading>
      {!models.length && (
        <div className="notice">
          Connect a provider and register a chat model first.{" "}
          <Link to="/providers">Configure AI providers →</Link>
        </div>
      )}
      <div className="toolbar">
        <div className="search">
          <Search size={16} />
          <input
            aria-label="Search chatbots"
            placeholder="Search your chatbots…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <span>{bots.length} assistants</span>
      </div>
      {bots.length ? (
        <div className="bot-grid">
          {bots
            .filter((b) => b.name.toLowerCase().includes(filter.toLowerCase()))
            .map((bot) => (
              <BotCard
                key={bot.id}
                bot={bot}
                onEdit={() => setEditing(bot)}
                onDelete={async () => {
                  if (
                    window.confirm(`Delete ${bot.name} and its conversations?`)
                  )
                    try {
                      await api(`/chatbots/${bot.id}`, "DELETE");
                      await reload();
                      notify("Chatbot deleted");
                    } catch (e) {
                      notify((e as Error).message);
                    }
                }}
              />
            ))}
        </div>
      ) : (
        <Empty
          icon={Bot}
          title="An assistant for every idea"
          text="Create your first chatbot to start a grounded conversation."
        />
      )}
      {editing && initial && (
        <Editor
          title={editing === "new" ? "Create chatbot" : "Chatbot settings"}
          initial={Object.fromEntries(
            fields.map((f) => [f.key, initial[f.key]]),
          )}
          fields={fields}
          onClose={() => setEditing(null)}
          onSave={async (values) => {
            await api(
              editing === "new" ? "/chatbots" : `/chatbots/${editing.id}`,
              editing === "new" ? "POST" : "PUT",
              values,
            );
            await reload();
            notify("Chatbot saved");
          }}
        />
      )}
    </div>
  );
}
