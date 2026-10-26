import { useState } from "react";

import {
  ArrowRight,
  Bot,
  Database,
  Plus,
  Settings2,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { api } from "../api";
import type { Row } from "../types";
import { useWorkspace } from "../context";
import { Badge, Editor, Empty, Heading } from "../components/ui";
import type { Field } from "../components/ui";

export function Providers() {
  const { providers, models, embeddings, user, reload, notify } =
    useWorkspace();
  const [editor, setEditor] = useState<{ type: string; row?: Row } | null>(
      null,
    ),
    [tab, setTab] = useState("providers");
  const admin = user.role === "admin";
  const options = providers.map((p) => ({ value: p.id, label: p.name }));
  const providerFields: Field[] = [
    { key: "name", label: "Provider name", required: true, max: 100 },
    {
      key: "kind",
      label: "Adapter",
      required: true,
      options: [
        "ollama",
        "openai",
        "anthropic",
        "google",
        "groq",
        "lmstudio",
        "vllm",
        "openai_compatible",
      ].map((p) => ({ value: p, label: p })),
    },
    {
      key: "base_url",
      label: "API base URL",
      required: true,
      hint: "Exact origin must be allowed in the backend .env.",
    },
    {
      key: "api_key",
      label: "API key",
      type: "password",
      hint: "Leave blank when editing to retain the stored key. Secrets are encrypted and never returned.",
    },
    { key: "enabled", label: "Provider enabled", type: "checkbox" },
    {
      key: "is_local",
      label: "Local server (loopback only)",
      type: "checkbox",
    },
  ];
  const modelFields: Field[] = [
    { key: "provider_id", label: "Provider", required: true, options },
    { key: "name", label: "Exact model name", required: true, max: 150 },
    ...[
      ["temperature", "Supports temperature"],
      ["max_tokens", "Supports output token limit"],
      ["streaming", "Supports streaming"],
      ["is_default", "Default chat model"],
    ].map(([key, label]) => ({ key, label, type: "checkbox" })),
    {
      key: "input_cost_per_million",
      label: "Input cost per million tokens (optional)",
      type: "number",
      min: 0,
      step: 0.001,
    },
    {
      key: "output_cost_per_million",
      label: "Output cost per million tokens (optional)",
      type: "number",
      min: 0,
      step: 0.001,
    },
  ];
  const embeddingFields: Field[] = [
    { key: "name", label: "Exact embedding model name", required: true },
    {
      key: "kind",
      label: "Embedding adapter",
      required: true,
      options: ["ollama", "openai", "huggingface"].map((k) => ({
        value: k,
        label: k,
      })),
    },
    { key: "provider_id", label: "Provider (omit for Hugging Face)", options },
    {
      key: "dimensions",
      label: "Vector dimensions",
      type: "number",
      required: true,
      min: 1,
      max: 16000,
      hint: "nomic-embed-text: 768. Test before creating a knowledge base.",
    },
    {
      key: "version",
      label: "Embedding version",
      required: true,
      hint: "Immutable configuration. Register a new version when the model changes.",
    },
  ];
  let fields: Field[] = [],
    initial: Record<string, any> = {};
  if (editor?.type === "provider") {
    fields = providerFields;
    initial = editor.row
      ? {
          ...Object.fromEntries(fields.map((f) => [f.key, editor.row![f.key]])),
          api_key: "",
        }
      : {
          name: "Local Ollama",
          kind: "ollama",
          base_url: "http://localhost:11434",
          api_key: "",
          enabled: true,
          is_local: true,
        };
  }
  if (editor?.type === "model") {
    fields = modelFields;
    initial = editor.row
      ? { ...editor.row, ...editor.row.capabilities }
      : {
          provider_id: providers[0]?.id || "",
          name: "",
          temperature: true,
          max_tokens: true,
          streaming: true,
          is_default: !models.length,
          input_cost_per_million: null,
          output_cost_per_million: null,
        };
  }
  if (editor?.type === "embedding") {
    fields = embeddingFields;
    initial = {
      name: "nomic-embed-text",
      kind: "ollama",
      provider_id: providers.find((p) => p.kind === "ollama")?.id || null,
      dimensions: 768,
      version: "v1",
    };
  }
  return (
    <div className="page">
      <Heading
        title="AI providers"
        description="The intelligence behind your workspace. Local or cloud, you choose."
      >
        {admin && (
          <button
            className="button primary"
            onClick={() =>
              setEditor({
                type:
                  tab === "models"
                    ? "model"
                    : tab === "embeddings"
                      ? "embedding"
                      : "provider",
              })
            }
          >
            <Plus size={16} />
            Add{" "}
            {tab === "models"
              ? "model"
              : tab === "embeddings"
                ? "embedding model"
                : "provider"}
          </button>
        )}
      </Heading>
      {!admin && (
        <div className="notice">
          Provider credentials and model definitions are managed by your
          administrator.
        </div>
      )}
      <div className="tabs">
        {[
          ["providers", "Providers", providers.length],
          ["models", "Chat models", models.length],
          ["embeddings", "Embedding models", embeddings.length],
        ].map(([value, label, count]) => (
          <button
            key={String(value)}
            className={tab === value ? "active" : ""}
            onClick={() => setTab(String(value))}
          >
            {label}
            <span className="count">{count}</span>
          </button>
        ))}
      </div>
      {tab === "providers" && (
        <div className="provider-grid">
          {providers.map((p) => (
            <article key={p.id} className="panel provider-card">
              <div className="card-top">
                <span className="provider-icon">
                  <Database size={25} />
                </span>
                <Badge tone={p.enabled ? "green" : ""}>
                  {p.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
              <h2>{p.name}</h2>
              <p>
                {p.kind} ·{" "}
                {p.is_local ? "Local processing" : "Cloud processing"}
              </p>
              <code>{p.base_url}</code>
              <div className="provider-details">
                <span>
                  {models.filter((m) => m.provider_id === p.id).length} chat
                  models
                </span>
                <span>
                  {p.has_secret ? "Credential configured" : "No credential"}
                </span>
              </div>
              {admin && (
                <div className="card-footer">
                  <button
                    className="text-button"
                    onClick={async () => {
                      notify("Testing provider…");
                      try {
                        const result = await api(
                          `/providers/${p.id}/test`,
                          "POST",
                        );
                        notify(
                          result.ok
                            ? "Provider connected successfully"
                            : "Provider returned no content",
                        );
                      } catch (e) {
                        notify((e as Error).message);
                      }
                    }}
                  >
                    Test connection
                    <ArrowRight size={14} />
                  </button>
                  <button
                    className="icon-button"
                    title="Edit provider"
                    onClick={() => setEditor({ type: "provider", row: p })}
                  >
                    <Settings2 size={16} />
                  </button>
                  <button
                    className="icon-button danger"
                    title="Delete provider"
                    onClick={async () => {
                      if (
                        confirm(
                          `Delete ${p.name}? Remove dependent models first.`,
                        )
                      )
                        try {
                          await api(`/providers/${p.id}`, "DELETE");
                          await reload();
                        } catch (e) {
                          notify((e as Error).message);
                        }
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              )}
            </article>
          ))}
          {!providers.length && (
            <Empty
              icon={Database}
              title="Choose your intelligence"
              text="Start with Ollama on your computer, or connect a supported cloud provider."
            />
          )}
        </div>
      )}
      {tab === "models" && (
        <section className="panel">
          <div className="section-heading">
            <h2>Chat model registry</h2>
            <Badge>PROVIDER AGNOSTIC</Badge>
          </div>
          {models.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Provider</th>
                    <th>Capabilities</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <strong>{m.name}</strong>
                        {m.is_default && <Badge tone="blue">Default</Badge>}
                      </td>
                      <td>
                        {providers.find((p) => p.id === m.provider_id)?.name}
                      </td>
                      <td>
                        {Object.entries(m.capabilities)
                          .filter(([, v]) => v)
                          .map(([k]) => k)
                          .join(", ")}
                      </td>
                      <td>
                        {admin && (
                          <div className="row">
                            <button
                              className="text-button"
                              onClick={() =>
                                setEditor({ type: "model", row: m })
                              }
                            >
                              Edit
                            </button>
                            <button
                              className="icon-button danger"
                              title="Delete model"
                              onClick={async () => {
                                if (confirm(`Delete model ${m.name}?`))
                                  try {
                                    await api(`/models/${m.id}`, "DELETE");
                                    await reload();
                                  } catch (e) {
                                    notify((e as Error).message);
                                  }
                              }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              icon={Bot}
              title="Register a chat model"
              text="Use the exact model name from your provider. Model weights are managed outside this dashboard."
            />
          )}
        </section>
      )}
      {tab === "embeddings" && (
        <section className="panel">
          <div className="section-heading">
            <h2>Embedding configurations</h2>
            <Badge>IMMUTABLE VERSIONS</Badge>
          </div>
          {embeddings.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Adapter</th>
                    <th>Dimensions</th>
                    <th>Version</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {embeddings.map((e) => (
                    <tr key={e.id}>
                      <td>
                        <strong>{e.name}</strong>
                      </td>
                      <td>{e.kind}</td>
                      <td>{e.dimensions}</td>
                      <td>{e.version}</td>
                      <td>
                        {admin && (
                          <button
                            className="text-button"
                            onClick={async () => {
                              notify("Testing embedding model…");
                              try {
                                await api(
                                  `/embedding-models/${e.id}/test`,
                                  "POST",
                                );
                                notify("Embedding dimensions verified");
                              } catch (e) {
                                notify((e as Error).message);
                              }
                            }}
                          >
                            Test model
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              icon={Database}
              title="Give knowledge a searchable shape"
              text="Register an embedding model separately from your chat model."
            />
          )}
        </section>
      )}
      <div className="notice">
        <ShieldCheck size={18} />
        <span>
          Local processing is the default. Cloud use requires permission on both
          the chatbot and its knowledge base.
        </span>
      </div>
      {editor && (
        <Editor
          title={`Configure ${editor.type}`}
          fields={fields}
          initial={Object.fromEntries(
            fields.map((f) => [
              f.key,
              initial[f.key] ?? (f.type === "checkbox" ? false : null),
            ]),
          )}
          onClose={() => setEditor(null)}
          onSave={async (values) => {
            let payload = { ...values };
            if (editor.type === "provider" && editor.row && !payload.api_key)
              delete payload.api_key;
            if (editor.type === "model") {
              payload.capabilities = {
                temperature: payload.temperature,
                max_tokens: payload.max_tokens,
                streaming: payload.streaming,
              };
              delete payload.temperature;
              delete payload.max_tokens;
              delete payload.streaming;
            }
            const path =
              editor.type === "provider"
                ? "/providers"
                : editor.type === "model"
                  ? "/models"
                  : "/embedding-models";
            await api(
              path + (editor.row ? `/${editor.row.id}` : ""),
              editor.row ? "PUT" : "POST",
              payload,
            );
            await reload();
            notify("Configuration saved");
          }}
        />
      )}
    </div>
  );
}
