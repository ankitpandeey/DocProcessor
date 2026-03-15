import { useState, useRef } from "react";
import "./chatbot.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import remarkSqueezeParagraphs from "remark-squeeze-paragraphs";

export default function Chatbot() {

  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi, How can I help you today?" }
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const assistantStartRef = useRef(null);

  async function sendMessage() {

    if (!input.trim() || loading) return;

    const userMsg = { role: "user", content: input };

    setMessages(prev => [
      ...prev,
      userMsg,
      { role: "assistant", content: "" }
    ]);

    setInput("");

    // scroll to assistant answer start
    setTimeout(() => {
      assistantStartRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }, 0);

    setLoading(true);

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
          setLoading(false);
          firstChunk = false;
        }

        fullText += chunk;

        requestAnimationFrame(() => {
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1].content = fullText;
            return updated;
          });
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
  }

  return (
    <div className="chat-root">

      {/* HEADER */}
      <header className="chat-header">
        <div className="header-inner">
          <span>Doc Processing Agent</span>
          <button className="clear-btn" onClick={clearChat}>
            Clear chat
          </button>
        </div>
      </header>

      {/* CHAT BODY */}
      <div className="chat-body">

        <div className="chat-container">

          {messages.map((m, i) => {

            const isAssistantStart =
              m.role === "assistant" && m.content === "";

            return (
              <div
                key={i}
                className={`msg-row ${m.role}`}
                ref={isAssistantStart ? assistantStartRef : null}
              >
                <div className="msg-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkSqueezeParagraphs]}
                    rehypePlugins={[rehypeRaw]}
                  >
                    {m.content}
                  </ReactMarkdown>
                </div>
              </div>
            );

          })}

          {loading && (
            <div className="msg-row assistant">
              <div className="msg-content typing">
                Typing…
              </div>
            </div>
          )}

        </div>

      </div>

      {/* INPUT */}
      <div className="chat-input-wrapper">

        <div className="chat-input">

          <textarea
            rows={1}
            value={input}
            placeholder="Ask anything…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
          />

          <button onClick={sendMessage}>
            Send
          </button>

        </div>

      </div>

    </div>
  );
}