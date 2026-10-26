import React, { useState } from "react";

import { ArrowRight, Database, FileText, Sparkles } from "lucide-react";

import { api, setToken } from "../api";
import type { User } from "../types";

export function Auth({ onLogin }: { onLogin: (u: User) => void }) {
  const [register, setRegister] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(event.currentTarget);
    const data = { email: f.get("email"), password: f.get("password") };
    try {
      if (register) await api("/auth/register", "POST", data);
      const result = await api("/auth/login", "POST", data);
      setToken(result.access_token);
      onLogin(result.user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth">
      <div className="auth-story">
        <span className="brand-icon">
          <Database />
        </span>
        <p className="eyebrow">AI KNOWLEDGE HUB</p>
        <h1>
          Your knowledge.
          <br />A conversation away.
        </h1>
        <p>
          Build thoughtful AI assistants, grounded in the information that
          matters to you.
        </p>
        <div className="auth-diagram">
          <FileText />
          <span>Knowledge</span>
          <ArrowRight />
          <Sparkles />
          <span>Intelligence</span>
        </div>
        <small>Local models. Clear sources. Your control.</small>
      </div>
      <div className="auth-form">
        <h2>{register ? "Create your workspace" : "Welcome back"}</h2>
        <p className="muted">
          {register
            ? "Start building with your own knowledge."
            : "Sign in to your AI workspace."}
        </p>
        <form onSubmit={submit}>
          <label>
            Email address
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              minLength={10}
              maxLength={128}
              autoComplete={register ? "new-password" : "current-password"}
              required
            />
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary" disabled={busy}>
            {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
            <ArrowRight size={16} />
          </button>
        </form>
        <p>
          {register ? "Already have an account?" : "New to Knowledge Hub?"}{" "}
          <button
            className="text-button"
            onClick={() => {
              setRegister(!register);
              setError("");
            }}
          >
            {register ? "Sign in" : "Create an account"}
          </button>
        </p>
      </div>
    </div>
  );
}
