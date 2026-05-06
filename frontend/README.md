# Frontend (placeholder)

Empty intentionally. This is where the React + Recharts dashboard lives once
scaffolded — see `docs/design-doc.md` for the design and §16 for the suggested
first slice (the **Best Sellers** page end-to-end).

## When you scaffold

The expected stack from the design doc is:

- **Vite** (React + TypeScript template)
- **Recharts** for charts
- **React Router** for the five pages: Overview, Best Sellers, Time Series, Peak Hours, Comparison
- A small fetch wrapper that talks to the backend at `http://localhost:8000`

### Suggested commands when ready

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install recharts react-router-dom
```

Then add a `frontend` service to `compose.yaml` (or run the Vite dev server on
the host) and point it at `VITE_API_URL=http://localhost:8000`.
