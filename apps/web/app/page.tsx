"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, apiRequest } from "../lib/api";

type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

type Chat = {
  id: string;
  title: string;
};

type Message = {
  id: string;
  role: string;
  content: string;
  created_at: string;
};

type DocumentItem = {
  id: string;
  file_name: string;
  status: string;
};

export default function HomePage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const messagesRef = useRef<HTMLDivElement>(null);

  const activeChat = useMemo(() => chats.find((chat) => chat.id === activeChatId), [activeChatId, chats]);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSignup(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest("/auth/signup", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await handleLogin();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleLogin() {
    setError("");
    setBusy(true);
    try {
      const auth = await apiRequest<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(auth.access_token);
      await loadChats(auth.access_token);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function loadChats(authToken: string) {
    const data = await apiRequest<Chat[]>("/chats", {}, authToken);
    setChats(data);
    if (data[0]) {
      setActiveChatId(data[0].id);
      await loadMessages(data[0].id, authToken);
      await loadDocuments(data[0].id, authToken);
    }
  }

  async function createChat() {
    if (!token) return;
    const chat = await apiRequest<Chat>(
      "/chats",
      { method: "POST", body: JSON.stringify({ title: `Chat ${chats.length + 1}` }) },
      token
    );
    const nextChats = [chat, ...chats];
    setChats(nextChats);
    setActiveChatId(chat.id);
    setMessages([]);
    setDocuments([]);
  }

  async function loadMessages(chatId: string, authToken: string = token) {
    const data = await apiRequest<Message[]>(`/chats/${chatId}/messages`, {}, authToken);
    setMessages(data);
  }

  async function loadDocuments(chatId: string, authToken: string = token) {
    const data = await apiRequest<DocumentItem[]>(`/chats/${chatId}/documents`, {}, authToken);
    setDocuments(data);
  }

  async function uploadDocument() {
    if (!token || !activeChatId || !uploadFile) return;
    const form = new FormData();
    form.append("file", uploadFile);
    await apiRequest<DocumentItem>(
      `/chats/${activeChatId}/documents`,
      { method: "POST", body: form },
      token
    );
    setUploadFile(null);
    await loadDocuments(activeChatId);
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!token || !activeChatId || !prompt.trim() || sending) return;
    const input = prompt.trim();
    setPrompt("");
    setError("");
    setSending(true);

    const now = new Date().toISOString();
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: input,
      created_at: now,
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      created_at: now,
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    try {
      const response = await fetch(`${API_URL}/chats/${activeChatId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content: input }),
      });
      if (!response.ok || !response.body) {
        throw new Error(await response.text());
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let done = false;

      while (!done) {
        const read = await reader.read();
        done = read.done;
        buffer += decoder.decode(read.value || new Uint8Array(), { stream: !done });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const evt of events) {
          const line = evt.trim();
          if (!line.startsWith("data:")) continue;
          const payload = JSON.parse(line.slice(5).trim()) as {
            type: string;
            content?: string;
            citations?: { file_name: string; chunk_index: number; score: number }[];
            message?: string;
          };

          if (payload.type === "token" && payload.content) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId ? { ...msg, content: msg.content + payload.content } : msg
              )
            );
          }

          if (payload.type === "citations" && payload.citations?.length) {
            const sources = payload.citations
              .map((c) => `${c.file_name} (chunk ${c.chunk_index}, score=${Number(c.score).toFixed(4)})`)
              .join("\n");
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId ? { ...msg, content: `${msg.content}\n\nSources:\n${sources}` } : msg
              )
            );
          }

          if (payload.type === "error" && payload.message) {
            setError(payload.message);
          }
        }
      }
      await loadMessages(activeChatId);
      await loadDocuments(activeChatId);
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  }

  if (!token) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <h1 className="auth-title">Local-First RAG Chatbot</h1>
          <p className="auth-sub">
            Private document chat with local storage, retrieval, and open-source models.
          </p>
          {error && <p className="error">{error}</p>}
          <form onSubmit={handleSignup}>
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
              <button type="submit" disabled={busy}>
                Sign Up + Login
              </button>
              <button
                className="secondary"
                type="button"
                disabled={busy}
                onClick={() => void handleLogin()}
              >
                Login
              </button>
            </div>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <h2 className="sidebar-title">Conversations</h2>
        <button onClick={() => void createChat()}>+ New Chat</button>
        <p className="muted" style={{ color: "#c6d4ef", margin: "10px 0 8px" }}>
          {chats.length} chat(s)
        </p>
        <div className="chat-list">
          {chats.map((chat) => (
            <button
              key={chat.id}
              className={`chat-item ${chat.id === activeChatId ? "active" : ""}`}
              onClick={() => {
                setActiveChatId(chat.id);
                void loadMessages(chat.id);
                void loadDocuments(chat.id);
              }}
            >
              {chat.title}
            </button>
          ))}
        </div>
      </aside>

      <section className="main-shell">
        <header className="main-head">
          <h1 className="main-title">{activeChat ? activeChat.title : "Select a chat"}</h1>
          <p className="main-sub">Upload up to 4 documents per chat and ask grounded questions.</p>
        </header>

        <section className="doc-panel">
          <input
            type="file"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            style={{ maxWidth: 280 }}
          />
          <button className="ghost" disabled={!uploadFile} type="button" onClick={() => void uploadDocument()}>
            Upload
          </button>
          {documents.map((doc) => (
            <span key={doc.id} className="doc-chip">
              {doc.file_name} - {doc.status}
            </span>
          ))}
        </section>

        {error && <p className="error" style={{ margin: "12px 18px 0" }}>{error}</p>}

        <section ref={messagesRef} className="messages">
          {messages.map((message) => (
            <article key={message.id} className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
              {message.content || (message.role === "assistant" ? "Thinking..." : "")}
            </article>
          ))}
        </section>

        <footer className="composer">
          <form onSubmit={sendMessage} className="composer-row">
            <textarea
              rows={3}
              value={prompt}
              placeholder="Ask anything about your uploaded documents..."
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button type="submit" disabled={sending}>
              {sending ? "Sending..." : "Send"}
            </button>
          </form>
        </footer>
      </section>
    </main>
  );
}

