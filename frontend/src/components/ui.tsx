import React, { useEffect, useRef, useState } from "react";
import { BookOpen, Bot, Check, X } from "lucide-react";
import { api } from "../api";

export function Heading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}

export function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function Empty({
  icon: Icon = BookOpen,
  title,
  text,
  children,
}: {
  icon?: typeof Bot;
  title: string;
  text: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span>
        <Icon size={28} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}

export function ErrorText({ text }: { text: string }) {
  return text ? (
    <p role="alert" className="error">
      {text}
    </p>
  ) : null;
}

export function useLoad(path: string) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  const load = async () => {
    try {
      setData(await api(path));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    setData(null);
    load();
  }, [path]);
  return { data, error, load };
}

export type Field = {
  key: string;
  label: string;
  type?: string;
  options?: { value: string; label: string }[];
  hint?: string;
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
};

export function Editor({
  title,
  description,
  initial,
  fields,
  onSave,
  onClose,
}: {
  title: string;
  description?: string;
  initial: Record<string, any>;
  fields: Field[];
  onSave: (data: any) => Promise<void>;
  onClose: () => void;
}) {
  const [values, setValues] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const first = useRef<HTMLDivElement>(null);
  useEffect(() => {
    first.current
      ?.querySelector("input,select,textarea")
      ?.setAttribute("autofocus", "");
    const focus = first.current?.querySelector<HTMLElement>(
      "input,select,textarea",
    );
    focus?.focus();
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={first}
        onKeyDown={(e) => {
          if (e.key === "Escape" && !busy) onClose();
        }}
      >
        <div className="modal-header">
          <div>
            <h2>{title}</h2>
            <p>{description || "Make this workspace your own."}</p>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            disabled={busy}
            title="Close"
          >
            <X size={20} />
          </button>
        </div>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await onSave(values);
              onClose();
            } catch (error) {
              setError((error as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="form-fields">
            {fields.map((field) => (
              <label
                key={field.key}
                className={field.type === "checkbox" ? "checkbox-field" : ""}
              >
                <span>{field.label}</span>
                {field.type === "checkbox" ? (
                  <input
                    type="checkbox"
                    checked={!!values[field.key]}
                    onChange={(e) =>
                      setValues({ ...values, [field.key]: e.target.checked })
                    }
                  />
                ) : field.options ? (
                  <select
                    value={values[field.key] || ""}
                    required={field.required}
                    onChange={(e) =>
                      setValues({
                        ...values,
                        [field.key]: e.target.value || null,
                      })
                    }
                  >
                    <option value="">Select…</option>
                    {field.options.map((o) => (
                      <option value={o.value} key={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                ) : field.type === "textarea" ? (
                  <textarea
                    required={field.required}
                    rows={3}
                    maxLength={field.max}
                    value={values[field.key] ?? ""}
                    onChange={(e) =>
                      setValues({ ...values, [field.key]: e.target.value })
                    }
                  />
                ) : (
                  <input
                    type={field.type || "text"}
                    autoComplete={
                      field.type === "password" ? "new-password" : "off"
                    }
                    required={field.required}
                    min={field.min}
                    max={field.max}
                    maxLength={field.type === "number" ? undefined : field.max}
                    step={field.step}
                    value={values[field.key] ?? ""}
                    onChange={(e) =>
                      setValues({
                        ...values,
                        [field.key]:
                          field.type === "number"
                            ? e.target.value === ""
                              ? null
                              : Number(e.target.value)
                            : e.target.value,
                      })
                    }
                  />
                )}{" "}
                {field.hint && <small>{field.hint}</small>}
              </label>
            ))}
          </div>
          <ErrorText text={error} />
          <div className="modal-footer">
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={onClose}
            >
              Cancel
            </button>
            <button className="button primary" disabled={busy}>
              {busy ? "Saving…" : "Save changes"}
              <Check size={15} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
