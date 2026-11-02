import React, { useState, useEffect, useRef, useCallback } from "react";
import { API } from "../lib/api";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { jsPDF } from "jspdf";
import { Send, FileText, Plus, MessageSquare } from "lucide-react";
import { ShareScreeningCard } from "../components/ShareScreeningCard";
import { TriageCard } from "../components/TriageCard";
import { ChatPhotoPicker, ChatPhotoPreview } from "../components/ChatPhoto";

const CHAT_KEY = "sihha:chat-session";

export default function HealthChat() {
  const { activeProfile } = useAuth();
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [photo, setPhoto] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [opening, setOpening] = useState(false);
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

  useEffect(() => {
    const box = endRef.current?.parentElement;
    if (box) box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const loadSessions = useCallback(async () => {
    const res = await api.get("/chat/sessions");
    setSessions(res.data);
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const openReq = useRef(0);
  const openSession = async (sid) => {
    const req = ++openReq.current;
    setSessionId(sid);
    setMessages([]);
    sessionStorage.setItem(CHAT_KEY, sid);
    setOpening(true);
    try {
      const res = await api.get(`/chat/sessions/${sid}/messages`);
      if (req === openReq.current) setMessages(res.data);
    } finally {
      if (req === openReq.current) setOpening(false);
    }
  };

  useEffect(() => {
    // Reopen the conversation the patient was in, so a reload or navigation never blanks the chat.
    api.get("/chat/sessions").then(({ data }) => {
      if (openReq.current > 0) return;
      const saved = sessionStorage.getItem(CHAT_KEY);
      const pick = data.find((s) => s.chat_session_id === saved) || data.find((s) => s.status === "active");
      if (pick) openSession(pick.chat_session_id).catch(() => {});
    }).catch(() => {});
  }, []);

  const newSession = async () => {
    if (streaming || opening) return;
    openReq.current += 1;
    setOpening(true);
    try {
      const res = await api.post("/chat/sessions", { profile_id: activeProfile.id });
      await openSession(res.data.chat_session_id);
      loadSessions();
    } catch {
      setOpening(false);
      toast.error("Could not start a new screening");
    }
  };

  const send = async () => {
    if ((!input.trim() && !photo) || streaming || opening) return;
    let sid = sessionId;
    if (!sid) {
      openReq.current += 1;
      setOpening(true);
      try {
        const res = await api.post("/chat/sessions", { profile_id: activeProfile.id });
        sid = res.data.chat_session_id;
        await openSession(sid);
      } catch {
        setOpening(false);
        return toast.error("Could not start a screening");
      }
      loadSessions();
    }
    const text = input;
    const attached = photo;
    setInput("");
    setPhoto(null);
    setMessages((prev) => [...prev, { role: "user", content: text, localPhoto: attached?.previewUrl, photoKept: attached?.keep }, { role: "assistant", content: "", streaming: true }]);
    setStreaming(true);
    try {
      let photoId = null;
      if (attached) {
        const form = new FormData();
        form.append("file", attached.file);
        form.append("keep", attached.keep ? "true" : "false");
        photoId = (await api.post(`/chat/sessions/${sid}/photos`, form, { headers: { "Content-Type": "multipart/form-data" } })).data.photo_id;
      }
      const post = () => fetch(`${API}/chat/sessions/${sid}/message`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, photo_id: photoId }),
      });
      let resp = await post();
      if (resp.status === 401) {
        await api.post("/auth/refresh");
        resp = await post();
      }
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || "Failed to send message");
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
        if (!full) return copy.slice(0, -1);
        copy[copy.length - 1] = { role: "assistant", content: full };
        return copy;
      });
    } catch (e) {
      setMessages((prev) => prev.filter((m) => !(m.streaming && m.content === "")));
      toast.error(e?.response?.data?.detail || e?.message || "Failed to send message");
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
        <button onClick={newSession} disabled={streaming || opening} data-testid="new-screening-btn" className="btn-primary w-full justify-center">
          <Plus className="h-4 w-4" /> New Screening
        </button>
        {lastReport && <ShareScreeningCard report={lastReport} />}
        <div className="card p-3 space-y-1 max-h-40 lg:max-h-[480px] overflow-y-auto" data-testid="chat-sessions-list">
          {sessions.length === 0 && <p className="text-sm text-ink-soft p-3">No screenings yet.</p>}
          {sessions.map((s) => (
            <button
              key={s.chat_session_id}
              onClick={() => openSession(s.chat_session_id)}
              disabled={streaming || opening}
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

      <div className="lg:col-span-3 card flex flex-col h-[75vh] lg:h-[640px] min-w-0">
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
                {(m.localPhoto || m.photo_id) && (
                  <img src={m.localPhoto || `${API}/chat/photos/${m.photo_id}`} alt="Shared with the assistant" data-testid={`chat-photo-${i}`}
                    className="mb-2 max-h-56 rounded-xl object-cover" />
                )}
                {(m.photo_discarded || (m.localPhoto && m.photoKept === false)) && (
                  <p className="text-[11px] opacity-80 mb-1" data-testid={`chat-photo-discarded-${i}`}>Photo shared once — not saved</p>
                )}
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

        <ChatPhotoPreview photo={photo} setPhoto={setPhoto} />
        <div className="border-t border-line p-4 flex gap-2">
          <ChatPhotoPicker photo={photo} setPhoto={setPhoto} disabled={streaming} />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={photo ? "Add a note about the photo (optional)" : "Describe your symptoms…"}
            disabled={streaming || opening}
            data-testid="chat-input"
            className="flex-1 min-w-0 border border-line rounded-full px-5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest"
          />
          <button onClick={send} disabled={streaming || opening || (!input.trim() && !photo)} data-testid="chat-send-btn" className="btn-primary !px-4">
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}