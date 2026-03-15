"use client";

import { FormEvent, useMemo, useState } from "react";
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

type ChatResponse = {
  user_message: Message;
  assistant_message: Message;
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

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId),
    [activeChatId, chats]
  );

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
      { method: "POST", body: JSON.stringify({ title: "New Chat" }) },
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
    if (!token || !activeChatId || !prompt.trim()) return;
    const input = prompt;
    setPrompt("");
    setError("");

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
              .map(
                (c) =>
                  `${c.file_name} (chunk ${c.chunk_index}, score=${Number(c.score).toFixed(4)})`
              )
              .join("\n");
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: `${msg.content}\n\nSources:\n${sources}` }
                  : msg
              )
            );
          }
          if (payload.type === "error" && payload.message) {
            setError(payload.message);
          }
        }
      }
      await loadMessages(activeChatId);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main>
      <h1>Local-First RAG Chatbot</h1>
      <p className="muted">Milestone 0 scaffold: auth, chats, and message flow are live.</p>
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}

      {!token && (
        <section className="card">
          <h2>Auth</h2>
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
            <button type="submit" disabled={busy}>
              Sign Up + Login
            </button>
          </form>
          <button
            style={{ marginTop: 8, background: "#334155" }}
            disabled={busy}
            onClick={() => void handleLogin()}
          >
            Login
          </button>
        </section>
      )}

      {token && (
        <section className="grid">
          <aside className="card">
            <h2>Chats</h2>
            <button onClick={() => void createChat()}>Create Chat</button>
            <div style={{ marginTop: 12 }}>
              {chats.map((chat) => (
                <button
                  key={chat.id}
                  style={{
                    marginTop: 6,
                    background: chat.id === activeChatId ? "#0f766e" : "#475569",
                  }}
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

          <section className="card">
            <h2>{activeChat ? activeChat.title : "Select a chat"}</h2>
            <div className="card" style={{ marginBottom: 12 }}>
              <h3>Documents</h3>
              <p className="muted">Upload up to 4 files per chat.</p>
              <input
                type="file"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              />
              <button
                style={{ marginTop: 8, background: "#1d4ed8" }}
                disabled={!uploadFile}
                onClick={() => void uploadDocument()}
                type="button"
              >
                Upload
              </button>
              {documents.map((doc) => (
                <p key={doc.id} className="muted">
                  {doc.file_name} ({doc.status})
                </p>
              ))}
            </div>
            <div style={{ minHeight: 220 }}>
              {messages.map((message) => (
                <p key={message.id}>
                  <strong>{message.role}:</strong> {message.content}
                </p>
              ))}
            </div>
            <form onSubmit={sendMessage}>
              <textarea
                rows={4}
                value={prompt}
                placeholder="Ask your question about uploaded documents..."
                onChange={(e) => setPrompt(e.target.value)}
              />
              <button type="submit">Send</button>
            </form>
          </section>
        </section>
      )}
    </main>
  );
}
