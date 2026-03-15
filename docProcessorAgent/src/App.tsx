import { useState, useRef, useEffect } from "react";
import "./chatbot.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import remarkSqueezeParagraphs from "remark-squeeze-paragraphs";

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
    setLoading(false);
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
        fullText += chunk;
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content: fullText
          };
          return updated;
        });
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

  function formatLLMToMarkdown(input: string): string {
    if (!input) return "";
    let text = input.trim();
    text = text.replace(/\s*###\s+/g, "\n\n### ");
    text = text.replace(/\n?\s*-\s+/g, "\n- ");
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
              <ReactMarkdown
               remarkPlugins={[remarkGfm, remarkSqueezeParagraphs]}
                rehypePlugins={[rehypeRaw]}

              >
                {m.content}
              </ReactMarkdown>
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
