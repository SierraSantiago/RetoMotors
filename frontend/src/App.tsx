const metrics = [
  { label: "Leads analizados", value: "1.503" },
  { label: "Conversaciones", value: "677" },
  { label: "Asesores activos", value: "40" },
  { label: "Capacidad diaria", value: "694" },
];

function App() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div>
          <div className="brandMark">LP</div>
          <h1>Lead Priority</h1>
          <p className="muted">Sistema inteligente de gestión comercial</p>
        </div>

        <nav>
          <button className="navItem active">Resumen</button>
          <button className="navItem" disabled>Mis leads</button>
          <button className="navItem" disabled>Modelo</button>
          <button className="navItem" disabled>Pipeline</button>
        </nav>

        <div className="status">
          <span className="dot" />
          Etapa 1 completada
        </div>
      </aside>

      <section className="content">
        <header>
          <div>
            <span className="eyebrow">RETO TÉCNICO · ANALISTA IA</span>
            <h2>Entendimiento de datos</h2>
            <p>
              Perfilado reproducible de las fuentes antes de definir limpieza,
              deduplicación, IA y priorización.
            </p>
          </div>
          <div className="badge">Development</div>
        </header>

        <div className="metricGrid">
          {metrics.map((metric) => (
            <article className="metricCard" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </article>
          ))}
        </div>

        <div className="grid">
          <article className="panel">
            <span className="eyebrow">CALIDAD</span>
            <h3>Hallazgos principales</h3>
            <ul>
              <li>Formatos heterogéneos de fechas, ciudades y canales.</li>
              <li>Duplicados dentro y entre comercializadoras.</li>
              <li>190 textos de modelo para 24 referencias oficiales.</li>
              <li>Conversaciones con relación 1:N respecto al lead.</li>
              <li>Registros corruptos que deben ir a cuarentena.</li>
            </ul>
          </article>

          <article className="panel accent">
            <span className="eyebrow">SIGUIENTE ETAPA</span>
            <h3>PostgreSQL RAW</h3>
            <p>
              Diseñar el modelo de datos e implementar una ingestión idempotente
              y trazable sobre Supabase/PostgreSQL.
            </p>
            <div className="flow">
              <span>Sources</span><b>→</b><span>Python</span><b>→</b><span>RAW</span>
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}

export default App;
