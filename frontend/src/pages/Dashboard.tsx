import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Check,
  Database,
  FileText,
  MessageSquare,
  Plus,
  Settings2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { api } from "../api";

import { useWorkspace } from "../context";
import { Badge, ErrorText, Heading, useLoad } from "../components/ui";

import { BotCard } from "../components/BotCard";

export function Dashboard() {
  const { user, bots, kbs, models, providers } = useWorkspace();
  const { data, error } = useLoad("/analytics");
  const configured = providers.some((p) => p.enabled);
  return (
    <div className="page">
      <Heading
        eyebrow="YOUR WORKSPACE, AT A GLANCE"
        title={`Welcome back, ${user.email.split("@")[0]}`}
        description="Turn what you know into something you can talk to."
      >
        <Link className="button primary" to="/chatbots">
          <Plus size={16} />
          Create chatbot
        </Link>
      </Heading>
      <ErrorText text={error} />
      <div className="hero">
        <div>
          <Badge tone="blue">
            <Sparkles size={12} />
            KNOWLEDGE MEETS INTELLIGENCE
          </Badge>
          <h2>
            A home for your knowledge.
            <br />A voice for your ideas.
          </h2>
          <p>
            Connect your documents. Choose your model. Build an
            <br className="desktop" /> assistant that answers with context and
            clarity.
          </p>
          <Link
            to={configured ? "/knowledge" : "/providers"}
            className="button dark"
          >
            {configured ? "Explore your knowledge" : "Connect your first model"}
            <ArrowRight size={16} />
          </Link>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="art-file art-file-one">
            <FileText />
            <i />
            <i />
            <i />
          </div>
          <div className="art-file art-file-two">
            <BookOpen />
            <i />
            <i />
          </div>
          <div className="art-core">
            <Sparkles size={43} />
          </div>
          <span className="art-dot dot-one" />
          <span className="art-dot dot-two" />
          <div className="art-label">
            <span />
            Grounded in your knowledge
          </div>
        </div>
      </div>
      <div className="stats">
        {[
          [
            Bot,
            "Chatbots",
            data?.chatbots ?? bots.length,
            "Your specialized assistants",
          ],
          [
            FileText,
            "Documents",
            data?.documents ?? "—",
            "Connected to your knowledge",
          ],
          [
            MessageSquare,
            "Conversations",
            data?.conversations ?? "—",
            "Ideas explored together",
          ],
          [
            Database,
            "AI models",
            models.length,
            "Ready for your next question",
          ],
        ].map(([Icon, name, value, detail]) => {
          const I = Icon as typeof Bot;
          return (
            <div className="stat" key={String(name)}>
              <div>
                <span>{String(name)}</span>
                <I size={18} />
              </div>
              <strong>{String(value)}</strong>
              <small>{String(detail)}</small>
            </div>
          );
        })}
      </div>
      <section className="section">
        <div className="section-heading">
          <div>
            <h2>
              Your chatbots <span className="count">{bots.length}</span>
            </h2>
            <p>Purpose-built assistants, powered by your knowledge.</p>
          </div>
          <Link to="/chatbots" className="text-link">
            View all chatbots
            <ArrowRight size={15} />
          </Link>
        </div>
        {bots.length ? (
          <div className="bot-grid">
            {bots.slice(0, 3).map((bot) => (
              <BotCard key={bot.id} bot={bot} />
            ))}
          </div>
        ) : (
          <div className="onboarding">
            <div className="onboarding-icon">
              <Bot size={30} />
            </div>
            <div>
              <h3>Meet your first AI assistant</h3>
              <p>Create a chatbot and give your knowledge a place to shine.</p>
            </div>
            <Link className="button" to="/chatbots">
              <Plus size={16} />
              Create chatbot
            </Link>
          </div>
        )}
      </section>
      <div className="bottom-grid">
        <section className="panel">
          <div className="section-heading">
            <h2>Build in three steps</h2>
            <Badge>GET STARTED</Badge>
          </div>
          {[
            [
              Settings2,
              "Connect a model",
              "Use Ollama locally or choose a cloud provider.",
              "/providers",
              configured,
            ],
            [
              BookOpen,
              "Add your knowledge",
              "Create a knowledge base and upload documents.",
              "/knowledge",
              kbs.length > 0,
            ],
            [
              MessageSquare,
              "Start a conversation",
              "Ask questions and explore grounded answers.",
              "/chat",
              (data?.conversations ?? 0) > 0,
            ],
          ].map(([Icon, name, text, path, done], i) => {
            const I = Icon as typeof Bot;
            return (
              <Link to={String(path)} className="step" key={String(name)}>
                <span className={done ? "step-number done" : "step-number"}>
                  {done ? <Check size={15} /> : i + 1}
                </span>
                <div>
                  <strong>{String(name)}</strong>
                  <p>{String(text)}</p>
                </div>
                <I size={18} />
              </Link>
            );
          })}
        </section>
        <section className="panel insight">
          <span className="insight-icon">
            <ShieldCheck size={24} />
          </span>
          <p className="eyebrow">BUILT FOR TRUST</p>
          <h2>
            Your data stays
            <br />
            in your hands.
          </h2>
          <p>
            Run models on your own machine. Keep private knowledge local. Choose
            when cloud processing is allowed.
          </p>
          <Link to="/providers" className="text-link">
            Manage AI providers
            <ArrowRight size={15} />
          </Link>
        </section>
      </div>
      <footer>
        AI Knowledge Hub <span>Built for curious minds.</span>
        <span>FastAPI · LangGraph · PostgreSQL</span>
      </footer>
    </div>
  );
}
