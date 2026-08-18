import React, { useState } from "react";
import { MessageSquare, Send, Info } from "lucide-react";

export function FollowUpPanel({ messages, onAsk, busy, starters, onCite }) {
  const [text, setText] = useState("");

  const submit = (e) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    onAsk(text.trim());
    setText("");
  };

  return (
    <div className="card p-6 flex flex-col" data-testid="followup-panel">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-forest" /> Ask about this record
      </h3>
      <p className="text-xs text-ink-soft mt-1" data-testid="followup-subtitle">
        Answers come from this patient's data only.
      </p>

      {messages.length === 0 && starters.length > 0 && (
        <div className="mt-4 space-y-2" data-testid="followup-starters">
          {starters.map((q, i) => (
            <button key={i} onClick={() => onAsk(q)} disabled={busy}
              data-testid={`starter-question-${i}`}
              className="btn-outline w-full !justify-start text-left text-xs !rounded-xl">
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="mt-4 space-y-3 max-h-[26rem] overflow-y-auto pr-1" data-testid="followup-messages">
        {messages.map((m, i) =>
          m.role === "doctor" ? (
            <div key={m.message_id || i} className="flex justify-end">
              <p className="bg-forest text-white text-sm rounded-2xl rounded-br-sm px-3.5 py-2 max-w-[85%]"
                data-testid={`followup-doctor-msg-${i}`}>
                {m.content}
              </p>
            </div>
          ) : m.refused ? (
            <div key={m.message_id || i} className="border border-line bg-sand rounded-2xl px-3.5 py-2.5 max-w-[92%]"
              data-testid={`followup-refusal-${i}`}>
              <span className="text-[10px] uppercase tracking-wider font-bold text-ink-soft flex items-center gap-1">
                <Info className="h-3 w-3" /> Out of scope
              </span>
              <p className="text-sm text-ink-soft mt-1">{m.refusal_reason}</p>
            </div>
          ) : (
            <div key={m.message_id || i} className="max-w-[92%]" data-testid={`followup-assistant-msg-${i}`}>
              <p className="bg-white border border-line text-sm rounded-2xl rounded-bl-sm px-3.5 py-2">{m.content}</p>
              {(m.cited_records || []).length === 0 ? (
                <p className="text-[10px] uppercase tracking-wider text-terracotta mt-1.5"
                  data-testid={`followup-no-citations-${i}`}>
                  No citations — unverified
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {m.cited_records.map((c, ci) => (
                    <button key={ci} onClick={() => onCite(c)} data-testid={`citation-chip-${i}-${ci}`}
                      className="text-[10px] px-2 py-1 rounded-full bg-sage/30 text-forest font-medium">
                      {c.collection} · {c.summary || c.id}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        )}
        {busy && (
          <div className="flex gap-1.5 items-center px-2" data-testid="followup-busy">
            <span className="typing-dot" />
            <span className="typing-dot" style={{ animationDelay: "0.15s" }} />
            <span className="typing-dot" style={{ animationDelay: "0.3s" }} />
          </div>
        )}
      </div>

      <form onSubmit={submit} className="mt-4 flex items-center gap-2">
        <input
          value={text} onChange={(e) => setText(e.target.value)} data-testid="followup-input"
          placeholder="Ask about a value, trend or dose…"
          className="flex-1 border border-line rounded-full px-4 py-2 text-sm bg-white outline-none focus:border-sage"
        />
        <button type="submit" disabled={busy} data-testid="followup-send-btn" className="btn-primary !px-3.5">
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
