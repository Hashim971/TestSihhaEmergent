import React, { useState, useEffect, useRef, useCallback } from "react";
import { API } from "../lib/api";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { jsPDF } from "jspdf";
import { Send, FileText, Plus, MessageSquare } from "lucide-react";
import { ShareScreeningCard } from "../components/ShareScreeningCard";
import { TriageCard } from "../components/TriageCard";

export default function HealthChat() {
  const { activeProfile } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [lastReport, setLastReport] = useState(null);

  useEffect(() => {
    // Surface the newest screening report so it stays shareable after a page reload.
    api.get("/reports").then(({ data }) => setLastReport(data[0] || null)).catch(() => {});
  }, []);
  const endRef = useRef(null);

  const runTriage = async () => {
    if (!lastReport) return;
    try {
      const { data } = await api.post(`/reports/${lastReport.report_id}/triage`);
      setLastReport(data);
    } catch {
      toast.error("Could not check the urgency of this screening");
    }
  };

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const loadSessions = useCallback(async () => {
    const res = await api.get("/chat/sessions");
    setSessions(res.data);
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const openSession = async (sid) => {
    setSessionId(sid);
    const res = await api.get(`/chat/sessions/${sid}/messages`);
    setMessages(res.data);
  };

  const newSession = async () => {
    const res = await api.post("/chat/sessions", { profile_id: activeProfile.id });
    await loadSessions();
    openSession(res.data.chat_session_id);
  };

  const send = async () => {
    if (!input.trim() || streaming) return;
    let sid = sessionId;
    if (!sid) {
      const res = await api.post("/chat/sessions", { profile_id: activeProfile.id });
      sid = res.data.chat_session_id;
      setSessionId(sid);
      const msgs = await api.get(`/chat/sessions/${sid}/messages`);
      setMessages(msgs.data);
      loadSessions();
    }
    const text = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "", streaming: true }]);
    setStreaming(true);
    try {
      const resp = await fetch(`${API}/chat/sessions/${sid}/message`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.delta) {
            full += data.delta;
            setMessages((prev) => {
              const copy = [...prev];
              copy[copy.length - 1] = { role: "assistant", content: full, streaming: true };
              return copy;
            });
          }
          if (data.error) toast.error("AI error: " + data.error);
        }
      }
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content: full };
        return copy;
      });
    } catch (e) {
      toast.error("Failed to send message");
    } finally {
      setStreaming(false);
    }
  };

  const generateReport = async () => {
    if (!sessionId) return;
    setGeneratingReport(true);
    try {
      const res = await api.post(`/chat/sessions/${sessionId}/report`);
      setLastReport(res.data);
      downloadPdf(res.data.content);
      toast.success("Health screening report downloaded");
      loadSessions();
    } catch {
      toast.error("Report generation failed");
    } finally {
      setGeneratingReport(false);
    }
  };

  const downloadPdf = (content) => {
    const doc = new jsPDF();
    doc.setFontSize(22);
    doc.setTextColor(30, 63, 42);
    doc.text("HEALTH SCREENING REPORT", 105, 20, { align: "center" });
    doc.setFontSize(10);
    doc.setTextColor(100);
    doc.text(`Generated on: ${new Date().toLocaleString()} — Sihha AI`, 105, 28, { align: "center" });
    doc.setDrawColor(224, 109, 83);
    doc.setFillColor(252, 236, 232);
    doc.rect(20, 34, 170, 22, "FD");
    doc.setTextColor(224, 109, 83);
    doc.setFontSize(11);
    doc.text("IMPORTANT MEDICAL DISCLAIMER", 105, 41, { align: "center" });
    doc.setFontSize(8);
    doc.text("This report is for informational purposes only and is NOT a medical diagnosis. Review with a qualified healthcare provider.", 105, 48, { align: "center", maxWidth: 160 });
    doc.setTextColor(0);
    doc.setFontSize(10);
    const lines = doc.splitTextToSize(content, 170);
    let y = 66;
    lines.forEach((line) => {
      if (y > 275) { doc.addPage(); y = 20; }
      doc.text(line, 20, y);
      y += 5;
    });
    doc.save("sihha-health-screening-report.pdf");
  };

  return (
    <div className="space-y-6 fade-up">
      {lastReport && <TriageCard report={lastReport} onRetriage={runTriage} />}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6" data-testid="health-chat-page">
        <div className="lg:col-span-1 space-y-3">
        <button onClick={newSession} data-testid="new-screening-btn" className="btn-primary w-full justify-center">
          <Plus className="h-4 w-4" /> New Screening
        </button>
        {lastReport && <ShareScreeningCard report={lastReport} />}
        <div className="card p-3 space-y-1 max-h-[480px] overflow-y-auto" data-testid="chat-sessions-list">
          {sessions.length === 0 && <p className="text-sm text-ink-soft p-3">No screenings yet.</p>}
          {sessions.map((s) => (
            <button
              key={s.chat_session_id}
              onClick={() => openSession(s.chat_session_id)}
              data-testid={`chat-session-${s.chat_session_id}`}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm ${sessionId === s.chat_session_id ? "bg-forest text-white" : "hover:bg-sand"}`}
            >
              <span className="flex items-center gap-2">
                <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                {new Date(s.started_at).toLocaleDateString()} · {s.status}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="lg:col-span-3 card flex flex-col h-[640px]">
        <div className="border-b border-line px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">AI Health Screening</h2>
            <p className="text-xs text-ink-soft">Professional symptom assessment · not a diagnosis</p>
          </div>
          {sessionId && messages.length > 2 && (
            <button onClick={generateReport} disabled={generatingReport} data-testid="generate-report-btn" className="btn-outline">
              <FileText className="h-4 w-4" /> {generatingReport ? "Generating…" : "Download Report"}
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4" data-testid="chat-messages">
          {!sessionId && messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center gap-3">
              <MessageSquare className="h-10 w-10 text-sage" />
              <p className="text-ink-soft max-w-sm">Start a new screening or type below. The assistant will ask questions one at a time, just like a clinician.</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === "user" ? "bg-forest text-white rounded-br-md" : "bg-sand border border-line rounded-bl-md"
              }`}>
                {m.content}
                {m.streaming && m.content === "" && (
                  <span className="flex gap-1 py-1">
                    <span className="typing-dot" /><span className="typing-dot" style={{ animationDelay: "0.15s" }} /><span className="typing-dot" style={{ animationDelay: "0.3s" }} />
                  </span>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <div className="border-t border-line p-4 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Describe your symptoms…"
            disabled={streaming}
            data-testid="chat-input"
            className="flex-1 border border-line rounded-full px-5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest"
          />
          <button onClick={send} disabled={streaming || !input.trim()} data-testid="chat-send-btn" className="btn-primary !px-4">
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}