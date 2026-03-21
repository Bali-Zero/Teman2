import { useState, useEffect } from "react";
import "./App.css";

interface Message {
  id: number;
  text: string;
  sender: "user" | "ai";
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (input.trim()) {
      const newUserMessage: Message = {
        id: messages.length + 1,
        text: input,
        sender: "user",
      };
      setMessages((prevMessages) => [...prevMessages, newUserMessage]);
      setInput("");

      // Simulate AI response
      setTimeout(() => {
        const aiResponse: Message = {
          id: messages.length + 2,
          text: `I received your message: "${input}". How can I further assist you?`,
          sender: "ai",
        };
        setMessages((prevMessages) => [...prevMessages, aiResponse]);
      }, 1000);
    }
  };

  useEffect(() => {
    // Scroll to the bottom of the chat window when new messages arrive
    const chatWindow = document.getElementById("chat-window");
    if (chatWindow) {
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="d-flex flex-column min-vh-100 bg-dark text-white">
      <header className="p-3 bg-dark border-bottom border-secondary d-flex justify-content-between align-items-center">
        <img src="/logo.png" alt="Company Logo" style={{ height: "40px" }} />
        <h4 className="mb-0 ms-3">AI Team Chat</h4>
      </header>

      <div
        id="chat-window"
        className="flex-grow-1 p-3 overflow-auto"
        style={{ maxHeight: "calc(100vh - 120px)" }}
      >
        {messages.length === 0 ? (
          <div className="text-center text-muted mt-5">
            Type a message to start the conversation.
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`d-flex mb-2 ${message.sender === "user" ? "justify-content-end" : "justify-content-start"}`}
            >
              <div
                className={`p-2 rounded ${
                  message.sender === "user"
                    ? "bg-primary text-white"
                    : "bg-secondary text-white"
                }`}
                style={{ maxWidth: "70%" }}
              >
                {message.text}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-3 bg-dark border-top border-secondary">
        <div className="input-group">
          <input
            type="text"
            className="form-control bg-dark text-white border-secondary"
            placeholder="Type your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter") {
                handleSend();
              }
            }}
          />
          <button
            className="btn btn-primary"
            type="button"
            onClick={handleSend}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
