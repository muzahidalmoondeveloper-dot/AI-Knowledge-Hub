import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDownToLine,
  BookOpen,
  FileText,
  Plus,
  Settings2,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";

import { api, request } from "../api";
import type { Row } from "../types";
import { useWorkspace } from "../context";
import { Badge, Editor, Empty, ErrorText, Heading } from "../components/ui";
import type { Field } from "../components/ui";

export function Knowledge() {
  const { kbs, embeddings, reload, notify } = useWorkspace();
  const [selected, setSelected] = useState(""),
    [editing, setEditing] = useState<Row | "new" | null>(null),
    [documents, setDocuments] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const kb = kbs.find((k) => k.id === selected) || kbs[0];
  const input = useRef<HTMLInputElement>(null);
  async function loadDocuments() {
    if (kb)
      try {
        setDocuments(await api(`/knowledge-bases/${kb.id}/documents`));
        setError("");
      } catch (e) {
        setError((e as Error).message);
      }
  }
  useEffect(() => {
    setDocuments([]);
    loadDocuments();
    const timer = setInterval(loadDocuments, 4000);
    return () => clearInterval(timer);
  }, [kb?.id]);
  async function upload(file?: File, document?: Row) {
    if (!file || !kb) return;
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      await api(
        document
          ? `/documents/${document.id}`
          : `/knowledge-bases/${kb.id}/documents`,
        document ? "PUT" : "POST",
        data,
      );
      await loadDocuments();
      notify("Document queued for processing");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  const fields: Field[] = [
    { key: "name", label: "Knowledge base name", required: true, max: 100 },
    {
      key: "embedding_id",
      label: "Embedding configuration",
      required: true,
      options: embeddings.map((e) => ({
        value: e.id,
        label: `${e.name} · ${e.dimensions} dimensions · ${e.version}`,
      })),
    },
    {
      key: "chunk_size",
      label: "Chunk size (characters)",
      type: "number",
      min: 100,
      max: 5000,
    },
    {
      key: "chunk_overlap",
      label: "Chunk overlap (characters)",
      type: "number",
      min: 0,
      max: 4999,
    },
    {
      key: "allow_cloud",
      label: "Allow cloud processing of this knowledge",
      type: "checkbox",
      hint: "Applies to embeddings and chat. Keep off for private local processing.",
    },
  ];
  return (
    <div className="page">
      <Heading
        title="Knowledge bases"
        description="A reliable foundation for every answer."
      >
        <button
          className="button primary"
          disabled={!embeddings.length}
          onClick={() => setEditing("new")}
        >
          <Plus size={16} />
          New knowledge base
        </button>
      </Heading>
      {!embeddings.length && (
        <div className="notice">
          Register an embedding model in{" "}
          <Link to="/providers">AI providers</Link> before creating a knowledge
          base.
        </div>
      )}
      <ErrorText text={error} />
      {kbs.length ? (
        <div className="knowledge-layout">
          <aside className="kb-list">
            {kbs.map((k) => (
              <button
                key={k.id}
                onClick={() => setSelected(k.id)}
                className={kb?.id === k.id ? "selected" : ""}
              >
                <BookOpen size={17} />
                <span>
                  {k.name}
                  <small>
                    {k.allow_cloud
                      ? "Cloud processing allowed"
                      : "Local processing only"}
                  </small>
                </span>
              </button>
            ))}
          </aside>
          <section className="panel documents-panel">
            <div className="section-heading">
              <div>
                <h2>{kb.name}</h2>
                <p>
                  {embeddings.find((e) => e.id === kb.embedding_id)?.name} ·
                  Index generation {kb.generation}
                </p>
              </div>
              <div className="row">
                <button
                  className="icon-button"
                  title="Reconfigure and reindex"
                  onClick={() => setEditing(kb)}
                >
                  <Settings2 size={18} />
                </button>
                <button
                  className="icon-button danger"
                  title="Delete knowledge base"
                  onClick={async () => {
                    if (confirm(`Delete ${kb.name} and all its documents?`))
                      try {
                        await api(`/knowledge-bases/${kb.id}`, "DELETE");
                        await reload();
                      } catch (e) {
                        notify((e as Error).message);
                      }
                  }}
                >
                  <Trash2 size={17} />
                </button>
              </div>
            </div>
            <div
              className="upload-zone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (!busy) upload(e.dataTransfer.files[0]);
              }}
            >
              <span className="upload-icon">
                <Upload size={23} />
              </span>
              <h3>
                {busy ? "Uploading document…" : "Bring your knowledge in"}
              </h3>
              <p>Drop a document here, or browse your files</p>
              <small>PDF, DOCX, TXT, Markdown · up to 20 MB</small>
              <input
                type="file"
                ref={input}
                className="sr-only"
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => upload(e.target.files?.[0])}
              />
              <button
                className="button"
                disabled={busy}
                onClick={() => input.current?.click()}
              >
                <Plus size={15} />
                Choose document
              </button>
            </div>
            <div className="section-heading compact">
              <h3>
                Documents <span className="count">{documents.length}</span>
              </h3>
              <span className="muted">Status refreshes automatically</span>
            </div>
            {documents.length ? (
              <div className="document-list">
                {documents.map((d) => (
                  <div className="document-row" key={d.id}>
                    <span className="file-icon">
                      <FileText size={20} />
                    </span>
                    <div className="document-name">
                      <strong>{d.filename}</strong>
                      <small>
                        {(d.size / 1024).toFixed(1)} KB
                        {d.error && ` · ${d.error}`}
                      </small>
                    </div>
                    <Badge
                      tone={
                        d.status === "ready"
                          ? "green"
                          : d.status === "failed"
                            ? "red"
                            : "blue"
                      }
                    >
                      {d.status}
                    </Badge>
                    <button
                      title="Download"
                      className="icon-button"
                      onClick={async () => {
                        try {
                          const response = await request(
                            `/documents/${d.id}/download`,
                          );
                          const url = URL.createObjectURL(
                            await response.blob(),
                          );
                          const link = document.createElement("a");
                          link.href = url;
                          link.download = d.filename;
                          link.click();
                          setTimeout(() => URL.revokeObjectURL(url), 1000);
                        } catch (e) {
                          notify((e as Error).message);
                        }
                      }}
                    >
                      <ArrowDownToLine size={15} />
                    </button>
                    <button
                      className="text-button"
                      onClick={async () => {
                        try {
                          await api(`/documents/${d.id}/reindex`, "POST");
                          await loadDocuments();
                        } catch (e) {
                          notify((e as Error).message);
                        }
                      }}
                    >
                      Reindex
                    </button>
                    <label className="text-button replace">
                      Replace
                      <input
                        type="file"
                        accept=".pdf,.docx,.txt,.md"
                        onChange={(e) => upload(e.target.files?.[0], d)}
                      />
                    </label>
                    <button
                      className="icon-button danger"
                      title="Delete document"
                      onClick={async () => {
                        if (confirm(`Delete ${d.filename}?`))
                          try {
                            await api(`/documents/${d.id}`, "DELETE");
                            await loadDocuments();
                          } catch (e) {
                            notify((e as Error).message);
                          }
                      }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="quiet-empty">
                No documents yet. Your first upload starts the story.
              </p>
            )}
            <div className="notice small-notice">
              <ShieldCheck size={16} />
              Only ready documents are searchable. Run the document worker to
              process queued files.
            </div>
          </section>
        </div>
      ) : (
        <Empty
          title="Make room for your knowledge"
          text="Keep related documents together in a dedicated knowledge base."
        />
      )}
      {editing && (
        <Editor
          title={
            editing === "new"
              ? "Create knowledge base"
              : "Reconfigure and reindex"
          }
          description={
            editing === "new"
              ? "Choose a stable embedding space for these documents."
              : "Saving queues every document again. Old vectors become unavailable immediately."
          }
          initial={
            editing === "new"
              ? {
                  name: "",
                  embedding_id: embeddings[0]?.id || "",
                  chunk_size: 1000,
                  chunk_overlap: 150,
                  allow_cloud: false,
                }
              : Object.fromEntries(fields.map((f) => [f.key, editing[f.key]]))
          }
          fields={fields}
          onClose={() => setEditing(null)}
          onSave={async (values) => {
            await api(
              editing === "new"
                ? "/knowledge-bases"
                : `/knowledge-bases/${editing.id}/reindex`,
              "POST",
              values,
            );
            await reload();
            await loadDocuments();
            notify("Knowledge base saved");
          }}
        />
      )}
    </div>
  );
}
