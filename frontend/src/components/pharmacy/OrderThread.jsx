import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageCircle, Send } from "lucide-react";
import { api } from "../../lib/api";

export function OrderThread({ base, me, testid, unread = 0 }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) api.get(`${base}/messages`).then(({ data }) => setMessages((m) => {
      const ids = new Set(data.map((x) => x.message_id));
      return [...data, ...m.filter((x) => !ids.has(x.message_id))];
    })).catch(() => {});
  }, [open, base]);

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post(`${base}/messages`, { text });
      setMessages((m) => (m.some((x) => x.message_id === data.message_id) ? m : [...m, data]));
      setText("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Message not sent");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4" data-testid={testid}>
      <button onClick={() => setOpen(!open)} className="text-xs font-semibold text-forest inline-flex items-center gap-1.5" data-testid={`${testid}-toggle`}>
        <MessageCircle className="h-3.5 w-3.5" /> {open ? "Hide messages" : "Messages"}
        {unread > 0 && !open && <span className="ms-1 px-1.5 rounded-full bg-terracotta text-white text-[10px]">{unread}</span>}
      </button>
      {open && (
        <div className="mt-2 border border-line rounded-xl p-3 bg-sand/50 space-y-2">
          {messages.length === 0 && <p className="text-xs text-ink-soft">No messages yet.</p>}
          {messages.map((m) => (
            <div key={m.message_id} className={`flex ${m.sender === me ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${m.sender === me ? "bg-forest text-white" : "bg-white border border-line"}`}>
                <p>{m.text}</p>
                <p className={`text-[10px] mt-0.5 ${m.sender === me ? "text-white/70" : "text-ink-soft"}`}>{m.sender_name} · {new Date(m.created_at).toLocaleString()}</p>
              </div>
            </div>
          ))}
          <form onSubmit={send} className="flex gap-2 pt-1">
            <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Write a message"
              className="flex-1 border border-line rounded-full px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest" data-testid={`${testid}-input`} />
            <button type="submit" disabled={busy} className="btn-primary !py-2 !px-3" data-testid={`${testid}-send`}><Send className="h-4 w-4 rtl:rotate-180" /></button>
          </form>
        </div>
      )}
    </div>
  );
}
