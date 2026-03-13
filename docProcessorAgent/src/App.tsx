import { useState, useRef, useEffect } from "react";
import "./chatbot.css";
import ReactMarkdown from "react-markdown";

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

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // add empty assistant message
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: userMsg.content })
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let fullText = "";
      let firstChunk = true;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });

        if (firstChunk) {
          setLoading(false); // hide "Typing..."
          firstChunk = false;
        }

        for (const char of chunk) {
          fullText += char;

          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: "assistant",
              content: fullText
            };
            return updated;
          });

          await new Promise(r => setTimeout(r, 15));
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function clearChat() {
    setMessages([
      { role: "assistant", content: "Hi, How can I help you today?" }
    ]);
    setLoading(false);
  }

  // formatLLM.ts
  function formatLLMToMarkdown(input: string): string {
    if (!input) return "";

    let text = input.trim();

    // Ensure headings always start on a new line
    text = text.replace(/\s*###\s+/g, "\n\n### ");

    // Normalize bullet points
    text = text.replace(/\n?\s*-\s+/g, "\n- ");

    // Clean excessive spacing
    text = text.replace(/\n{3,}/g, "\n\n");

    return text.trim();
  } return (
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
            <div className="bubble">
              <ReactMarkdown>{m.content}</ReactMarkdown>
            </div>
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
