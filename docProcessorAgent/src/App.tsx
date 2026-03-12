import { useState, useRef, useEffect } from "react";
import "./chatbot.css";

export default function Chatbot() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi, How can I help you today?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
  if (!input.trim() || loading) return;

  const userMsg = { role: "user", content: input };
  setMessages((m) => [...m, userMsg]);
  setInput("");
  setLoading(true);

  try {
    const res = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userMsg.content }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
  } catch (err) {
    setMessages((m) => [
      ...m,
      { role: "assistant", content: `Error: ${err.message}` },
    ]);
  } finally {
    setLoading(false);
  }
}
``
function clearChat() {
  setMessages([
    { role: "assistant", content: "Hi, How can I help you today?" }
  ]);
  setLoading(false);
}
  return (
    <div className="chat-root">
      
<header className="chat-header">
  <span>Doc Processing Agent</span>
  <button className="clear-btn" onClick={clearChat}>
    Clear chat
  </button>
</header>


      <div className="chat-body">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.content}</div>
          </div>
        ))}

        {loading && (
          <div className="msg assistant">
            <div className="bubble typing">Typing…</div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Ask anything…"
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}
