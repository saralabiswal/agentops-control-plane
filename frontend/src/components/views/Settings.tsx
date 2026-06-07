export function Settings() {
  return (
    <section className="page-section">
      <div className="section-title"><h2>Settings</h2></div>
      <div className="agent-grid">
        {['Ollama', 'Groq', 'Gemini'].map((provider) => (
          <article className="agent-tile" key={provider}>
            <strong>{provider}</strong>
            <span>{provider === 'Ollama' ? 'Default local provider' : 'Optional API key provider'}</span>
          </article>
        ))}
      </div>
    </section>
  )
}

