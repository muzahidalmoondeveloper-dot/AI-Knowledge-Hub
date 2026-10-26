import { Link } from "react-router-dom";
import { Activity, ArrowRight } from "lucide-react";

import { api } from "../api";
import type { Row } from "../types";
import { useWorkspace } from "../context";
import { Badge, Empty, ErrorText, Heading, useLoad } from "../components/ui";

export function Analytics() {
  const { data, error } = useLoad("/analytics");
  const { models } = useWorkspace();
  const byModel: Record<string, number> = {};
  for (const u of data?.recent_usage || [])
    byModel[u.model_id || "No model"] =
      (byModel[u.model_id || "No model"] || 0) + 1;
  return (
    <div className="page">
      <Heading
        title="Workspace analytics"
        description="Understand how your knowledge is being put to work."
      />
      <ErrorText text={error} />
      <div className="stats">
        {[
          ["Responses", data?.responses ?? "—"],
          [
            "Input tokens",
            data?.input_tokens?.toLocaleString() ?? "Unavailable",
          ],
          [
            "Output tokens",
            data?.output_tokens?.toLocaleString() ?? "Unavailable",
          ],
          [
            "Average response",
            data?.average_latency_ms
              ? `${(data.average_latency_ms / 1000).toFixed(1)}s`
              : "—",
          ],
        ].map(([name, value]) => (
          <div className="stat" key={name}>
            <div>
              <span>{name}</span>
              <Activity size={17} />
            </div>
            <strong>{value}</strong>
            <small>Across your workspace</small>
          </div>
        ))}
      </div>
      <div className="bottom-grid">
        <section className="panel">
          <h2>Model usage</h2>
          <p className="muted">Most recent 100 successful responses</p>
          {Object.entries(byModel).map(([id, count]) => (
            <div className="usage-bar" key={id}>
              <div className="row spread">
                <strong>
                  {models.find((m) => m.id === id)?.name ||
                    "No generation / unavailable model"}
                </strong>
                <span>{count}</span>
              </div>
              <div>
                <span
                  style={{
                    width: `${(count / Math.max(1, data?.recent_usage.length)) * 100}%`,
                  }}
                />
              </div>
            </div>
          ))}
          {!Object.keys(byModel).length && (
            <Empty
              icon={Activity}
              title="Your story is just beginning"
              text="Usage appears here after your first successful chat."
            />
          )}
        </section>
        <section className="panel insight">
          <p className="eyebrow">APPROXIMATE MODEL COST</p>
          <h2 className="cost">
            {data?.approximate_cost == null
              ? "Unavailable"
              : `$${data.approximate_cost.toFixed(4)}`}
          </h2>
          <p>
            Calculated only where token usage and administrator-configured model
            prices are available. Missing usage is not counted as zero.
          </p>
          <Link to="/providers" className="text-link">
            Configure model pricing
            <ArrowRight size={15} />
          </Link>
        </section>
      </div>
      <section className="panel section">
        <div className="section-heading">
          <h2>Recent activity</h2>
          <Badge>LAST 100 RESPONSES</Badge>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Model</th>
                <th>Input tokens</th>
                <th>Output tokens</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {data?.recent_usage.map((u: Row) => (
                <tr key={u.id}>
                  <td>{new Date(u.created_at).toLocaleString()}</td>
                  <td>
                    {models.find((m) => m.id === u.model_id)?.name ||
                      "No model invoked"}
                  </td>
                  <td>{u.input_tokens ?? "—"}</td>
                  <td>{u.output_tokens ?? "—"}</td>
                  <td>{(u.latency_ms / 1000).toFixed(2)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!data?.recent_usage.length && (
          <p className="quiet-empty">No recorded activity yet.</p>
        )}
      </section>
    </div>
  );
}
