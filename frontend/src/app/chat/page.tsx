"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useDataSource } from "@/components/data-source-provider";
import { Send, Bot, User, AlertCircle, Database } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  communities?: string[];
  txCount?: number;
}

const SUGGESTIONS = [
  "Which 1BR under AED 1.5M has the best net yield?",
  "What are the risks of investing in JVC?",
  "Compare Dubai Marina vs Downtown for rental income",
  "Is Palm Jumeirah overpriced right now?",
  "Which communities have high supply risk?",
  "What's the best area for short-term rentals?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { useLive } = useDataSource();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(query: string) {
    if (!query.trim() || loading) return;

    const userMsg: Message = { role: "user", content: query.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await api.chat(query.trim());
      const assistantMsg: Message = {
        role: "assistant",
        content: res.answer,
        communities: res.communities,
        txCount: res.transaction_count,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setError(err.message || "Failed to get response");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={20} className="text-emerald-400" />
          <h1 className="text-lg font-bold">Investment Advisor</h1>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Database size={14} />
          <span>Powered by DuckDB + ChromaDB + Groq</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
              <Bot size={32} className="text-emerald-400" />
            </div>
            <div className="text-center">
              <h2 className="text-xl font-bold">Dubai Property Advisor</h2>
              <p className="text-muted-foreground mt-1 max-w-md">
                Ask anything about Dubai real estate investment. I&apos;ll analyze
                transaction data, community scores, and market reports.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="text-left text-sm p-3 rounded-lg border border-border hover:bg-accent/50 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                <Bot size={16} className="text-emerald-400" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-accent/50"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="text-sm whitespace-pre-wrap leading-relaxed">
                  {msg.content}
                </div>
              ) : (
                <div className="text-sm">{msg.content}</div>
              )}
              {msg.role === "assistant" && msg.communities && msg.communities.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border/50 flex flex-wrap gap-1.5">
                  {msg.communities.map((c) => (
                    <span
                      key={c}
                      className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400"
                    >
                      {c}
                    </span>
                  ))}
                  {msg.txCount !== undefined && msg.txCount > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400">
                      {msg.txCount} transactions
                    </span>
                  )}
                </div>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <User size={16} className="text-primary" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
              <Bot size={16} className="text-emerald-400" />
            </div>
            <div className="bg-accent/50 rounded-xl px-4 py-3">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
              <AlertCircle size={16} className="text-red-400" />
            </div>
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-border">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about Dubai real estate..."
            disabled={loading}
            className="flex-1 bg-accent/50 border border-border rounded-xl px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-primary text-primary-foreground rounded-xl px-4 py-3 hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={18} />
          </button>
        </form>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          {useLive ? "Using live BayutAPI data" : "Using mock data"} • Powered
          by Groq (Llama 3.3)
        </p>
      </div>
    </div>
  );
}
