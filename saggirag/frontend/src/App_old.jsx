import React, { useState, useRef, useEffect } from 'react';
import './App.css';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  const API_URL = 'http://localhost:8000';

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: input }]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input })
      });
      const data = await response.json();
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: data.response }]);
    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: '❌ Erro' }]);
    }
    setLoading(false);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>💰 RAG Finance Chat</h1>
      </header>
      <div className="messages-container">
        {messages.map(msg => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            <span>{msg.role === 'user' ? '👤' : '🤖'}</span>
            <p>{msg.content}</p>
          </div>
        ))}
      </div>
      <form className="input-form" onSubmit={handleSendMessage}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Pergunta..." disabled={loading} />
        <button disabled={loading}>{loading ? '⏳' : '➤'}</button>
      </form>
    </div>
  );
}
