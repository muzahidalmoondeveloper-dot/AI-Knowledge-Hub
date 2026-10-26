import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { api, refresh, setToken } from "./api";
import type { Row, User } from "./types";
import "./style.css";

import { Context } from "./context";
import { Auth } from "./pages/Auth";
import { Dashboard } from "./pages/Dashboard";
import { Chatbots } from "./pages/Chatbots";
import { Knowledge } from "./pages/Knowledge";
import { Providers } from "./pages/Providers";
import { Prompts } from "./pages/Prompts";
import { Chat } from "./pages/Chat";
import { Analytics } from "./pages/Analytics";

function App() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [bots, setBots] = useState<Row[]>([]),
    [kbs, setKbs] = useState<Row[]>([]),
    [models, setModels] = useState<Row[]>([]),
    [providers, setProviders] = useState<Row[]>([]),
    [embeddings, setEmbeddings] = useState<Row[]>([]);
  const [toast, setToast] = useState("");
  async function reload() {
    const data = await Promise.all(
      [
        "/chatbots",
        "/knowledge-bases",
        "/models",
        "/providers",
        "/embedding-models",
      ].map((p) => api(p)),
    );
    setBots(data[0]);
    setKbs(data[1]);
    setModels(data[2]);
    setProviders(data[3]);
    setEmbeddings(data[4]);
  }
  useEffect(() => {
    (async () => {
      try {
        if (await refresh()) setUser(await api("/auth/me"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);
  useEffect(() => {
    if (user) reload().catch((e) => setError(e.message));
  }, [user]);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  async function logout() {
    try {
      await api("/auth/logout", "POST");
      setToken("");
      setUser(null);
    } catch (e) {
      setToast((e as Error).message);
    }
  }
  if (loading)
    return (
      <div className="boot">
        <Sparkles size={32} />
        <p>Opening your workspace…</p>
      </div>
    );
  if (!user) return <Auth onLogin={setUser} />;
  return (
    <Context.Provider
      value={{
        user,
        bots,
        kbs,
        models,
        providers,
        embeddings,
        reload,
        notify: setToast,
      }}
    >
      <div className="shell">
        <aside className="sidebar">
          <Link className="brand" to="/">
            <span className="brand-icon">
              <Database size={21} />
            </span>
            <span>
              Knowledge<span className="brand-light">Hub</span>
              <small>YOUR AI WORKSPACE</small>
            </span>
          </Link>
          <div className="workspace-select">
            <span className="workspace-avatar">P</span>
            <span>
              Personal workspace<small>Local development</small>
            </span>
            <ChevronDown size={14} />
          </div>
          <p className="nav-label">WORKSPACE</p>
          <nav>
            {[
              ["/", LayoutDashboard, "Overview"],
              ["/chatbots", Bot, "Chatbots"],
              ["/knowledge", BookOpen, "Knowledge bases"],
              ["/chat", MessageSquare, "Playground"],
              ["/analytics", Activity, "Analytics"],
            ].map(([path, Icon, label]) => {
              const I = Icon as typeof Bot;
              return (
                <NavLink
                  key={String(path)}
                  to={String(path)}
                  end={path === "/"}
                >
                  <I size={18} />
                  <span>{String(label)}</span>
                  {label === "Chatbots" && <em>{bots.length}</em>}
                </NavLink>
              );
            })}
          </nav>
          <p className="nav-label">CONFIGURATION</p>
          <nav>
            <NavLink to="/providers">
              <Settings2 size={18} />
              AI providers
              <span className="nav-dot" />
            </NavLink>
          </nav>
          <div className="sidebar-bottom">
            <div className="local-note">
              <ShieldCheck size={18} />
              <strong>Private by design</strong>
              <p>Cloud processing requires explicit permission.</p>
            </div>
            <a
              className="help"
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
            >
              <CircleHelp size={17} />
              API documentation
              <ArrowRight size={14} />
            </a>
            <div className="profile">
              <span className="user-avatar">{user.email[0].toUpperCase()}</span>
              <div>
                <strong>{user.email.split("@")[0]}</strong>
                <small>
                  {user.role === "admin" ? "Administrator" : "Workspace member"}
                </small>
              </div>
              <button className="icon-button" onClick={logout} title="Sign out">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </aside>
        <main>
          <header className="topbar">
            <span>
              <span className="muted">Workspace</span>
              <span className="slash">/</span>AI Knowledge Hub
            </span>
            <div className="topbar-right">
              <span className="environment">
                <i />
                Development
              </span>
              <span className="user-avatar small">
                {user.email[0].toUpperCase()}
              </span>
            </div>
          </header>
          {error && (
            <div role="alert" className="error banner">
              {error}
              <button
                onClick={() =>
                  reload()
                    .then(() => setError(""))
                    .catch((e) => setError(e.message))
                }
              >
                Retry
              </button>
            </div>
          )}
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chatbots" element={<Chatbots />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/providers" element={<Providers />} />
            <Route path="/prompts/:id" element={<Prompts />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:id" element={<Chat />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
      {toast && (
        <div role="status" className="toast">
          <Check size={16} />
          {toast}
          <button className="icon-button" onClick={() => setToast("")}>
            <X size={14} />
          </button>
        </div>
      )}
    </Context.Provider>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
