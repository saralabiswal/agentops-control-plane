const tables = ['Session', 'AgentDefinition', 'ModelPricing', 'Task', 'AgentRun', 'BusinessOutcome', 'Metric']

export function DataModel() {
  return (
    <section className="page-section">
      <div className="section-title"><h2>Data model</h2></div>
      <div className="agent-grid">
        {tables.map((table) => <article className="agent-tile" key={table}><strong>{table}</strong><span>SQLAlchemy model</span></article>)}
      </div>
    </section>
  )
}

