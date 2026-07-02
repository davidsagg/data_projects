import React, { useState, useRef, useEffect } from 'react';
import './App.css';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState('data_science');
  
  const API_URL = 'http://localhost:8000';

  const categories = {
    data_science: '📊 Dados & ML',
    financas: '💰 Finanças',
    software_engineering: '💻 Engenharia de Software'
  };

  const categoryDescriptions = {
    data_science: 'Análise de Dados, Machine Learning e Estatística',
    financas: 'Finanças, Investimentos e Planejamento Financeiro',
    software_engineering: 'Arquitetura e Engenharia de Software'
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: input, category }]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input, category })
      });
      const data = await response.json();
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: data.response, category }]);
    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'assistant', content: '❌ Erro ao conectar com a API' }]);
    }
    setLoading(false);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-top">
          <h1>🧠 SAGGIRAG</h1>
          <div className="category-selector">
            {Object.entries(categories).map(([key, label]) => (
              <button
                key={key}
                className={`category-btn ${category === key ? 'active' : ''}`}
                onClick={() => setCategory(key)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <p className="category-description">{categoryDescriptions[category]}</p>
      </header>

      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-state">
            <h2>Bem-vindo ao SAGGIRAG</h2>
            <p>{categoryDescriptions[category]}</p>
            <div className="example-questions">
              <p>Exemplos de perguntas:</p>
              <ul>
                {category === 'data_science' && (
                  <>
                    <li>"Qual algoritmo usar para classificação multiclasse?"</li>
                    <li>"Como lidar com dados desbalanceados?"</li>
                    <li>"Quais técnicas de feature engineering existem?"</li>
                  </>
                )}
                {category === 'financas' && (
                  <>
                    <li>"O que é juros simples?"</li>
                    <li>"Como calcular ROI?"</li>
                    <li>"Qual a diferença entre renda fixa e variável?"</li>
                  </>
                )}
                {category === 'software_engineering' && (
                  <>
                    <li>"O que é Arquitetura Monolítica?"</li>
                    <li>"Como otimizar performance em Python?"</li>
                    <li>"Quais são as boas práticas de clean code?"</li>
                  </>
                )}
              </ul>
            </div>
          </div>
        ) : (
          messages.map(msg => (
            <div key={msg.id} className={`message message-${msg.role}`}>
              <span className="avatar">{msg.role === 'user' ? '👤' : '🤖'}</span>
              <p>{msg.content}</p>
            </div>
          ))
        )}
        {loading && (
          <div className="message message-assistant">
            <span className="avatar">🤖</span>
            <div className="thinking">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
      </div>

      <form className="input-form" onSubmit={handleSendMessage}>
        <input 
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
          placeholder="Faça sua pergunta..." 
          disabled={loading} 
          className="message-input"
        />
        <button disabled={loading} className="send-button">
          {loading ? '⏳' : '➤'}
        </button>
      </form>
    </div>
  );
}