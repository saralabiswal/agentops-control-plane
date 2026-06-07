const routes = ['/agents', '/sessions', '/tasks', '/runs', '/outcomes', '/metrics', '/stream/runs']

export function ApiSurface() {
  return (
    <section className="page-section">
      <div className="section-title"><h2>API surface</h2></div>
      <div className="run-list">
        {routes.map((route) => <article className="run-card" key={route}><strong>GET/POST {route}</strong><p>/api/v1{route}</p></article>)}
      </div>
    </section>
  )
}

