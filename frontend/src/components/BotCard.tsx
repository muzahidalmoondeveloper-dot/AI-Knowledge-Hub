import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Database,
  Settings2,
  Trash2,
} from "lucide-react";

import { api } from "../api";
import type { Row } from "../types";
import { useWorkspace } from "../context";
import { Badge } from "../components/ui";

export function BotCard({
  bot,
  onEdit,
  onDelete,
}: {
  bot: Row;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  const { models, kbs } = useWorkspace();
  const model = models.find((m) => m.id === bot.model_id),
    kb = kbs.find((k) => k.id === bot.knowledge_base_id);
  return (
    <article className="bot-card">
      <div className="card-top">
        <span className="bot-icon">
          <Bot size={22} />
        </span>
        <Badge tone={bot.enabled ? "green" : ""}>
          <i />
          {bot.enabled ? "Active" : "Disabled"}
        </Badge>
        {onEdit && (
          <button className="icon-button" onClick={onEdit} title="Edit chatbot">
            <Settings2 size={17} />
          </button>
        )}
      </div>
      <h3>{bot.name}</h3>
      <p>{bot.description || "An assistant grounded in your knowledge."}</p>
      <div className="bot-meta">
        <span>
          <Database size={13} />
          {model?.name || "Model unavailable"}
        </span>
        <span>
          <BookOpen size={13} />
          {kb?.name || "No knowledge base"}
        </span>
      </div>
      <div className="card-footer">
        <Link to={`/chat?bot=${bot.id}`} className="text-link">
          Open chat
          <ArrowRight size={14} />
        </Link>
        <Link to={`/prompts/${bot.id}`} className="subtle-link">
          Instructions
        </Link>
        {onDelete && (
          <button
            className="icon-button danger"
            title="Delete chatbot"
            onClick={onDelete}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </article>
  );
}
