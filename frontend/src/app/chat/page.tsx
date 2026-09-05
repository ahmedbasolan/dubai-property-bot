"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useDataSource } from "@/components/data-source-provider";
import {
  Send,
  Bot,
  User,
  AlertCircle,
  Database,
  Key,
  Check,
  ChevronDown,
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  communities?: string[];
  txCount?: number;
}

const PROVIDERS = [
  { id: "groq", label: "Groq", models: ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b"], defaultModel: "openai/gpt-oss-120b", free: true },
  { id: "openai", label: "OpenAI", models: ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], defaultModel: "gpt-4o-mini", free: false },
  { id: "openrouter", label: "OpenRouter", models: ["openai/gpt-4o-mini", "anthropic/claude-3-haiku", "meta-llama/llama-3.1-8b-instruct"], defaultModel: "openai/gpt-4o-mini", free: false },
];

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
  const [showSettings, setShowSettings] = useState(false);
  const [provider, setProvider] = useState("groq");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [keySaved, setKeySaved] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { useLive } = useDataSource();

  const currentProvider = PROVIDERS.find((p) => p.id === provider)!;

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
      const res = await api.chat(query.trim(), {
        provider,
        apiKey: apiKey || undefined,
        model: model || undefined,
      });
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
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={20} className="text-emerald-400" />
          <h1 className="text-lg font-bold">Investment Advisor</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg border border-border hover:bg-accent/50 transition-colors"
          >
            <Key size={12} />
            <span className={apiKey ? "text-emerald-400" : "text-muted-foreground"}>
              {currentProvider.label}
              {apiKey ? " (Custom)" : ""}
            </span>
            <ChevronDown size={12} className={`transition-transform ${showSettings ? "rotate-180" : ""}`} />
          </button>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Database size={14} />
            <span>LLM</span>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="px-4 pb-3">
          <div className="p-4 rounded-lg bg-accent/30 border border-border space-y-3">
            {/* Provider Selector */}
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Provider</label>
              <div className="flex gap-2">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setProvider(p.id);
                      setModel("");
                      setApiKey("");
                    }}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      provider === p.id
                        ? "bg-primary text-primary-foreground"
                        : "bg-background border border-border hover:bg-accent/50"
                    }`}
                  >
                    {p.label}
                    {p.free && (
                      <span className="ml-1.5 text-xs opacity-60">Free</span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Model Selector */}
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">Default ({currentProvider.defaultModel})</option>
                {currentProvider.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            {/* API Key Input */}
            <div>
              <label className="text-xs text-muted-foreground block mb-1.5">
                API Key {provider === "groq" && "(free at console.groq.com/keys)"}
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setKeySaved(false);
                  }}
                  placeholder={
                    provider === "groq" ? "gsk_..." :
                    provider === "openai" ? "sk-..." :
                    "sk-or-..."
                  }
                  className="flex-1 bg-background border border-border rounded-lg px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <button
                  onClick={() => setKeySaved(true)}
                  className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90"
                >
                  {keySaved ? <Check size={14} /> : "Save"}
                </button>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {apiKey ? "Using your custom key" : "Using server default (if configured)"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
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

      {/* Input */}
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
          {useLive ? "Live BayutAPI data" : "Mock data"} •{" "}
          {currentProvider.label} •{" "}
          {apiKey ? "Your key" : "Server key"}
        </p>
      </div>
    </div>
  );
}
