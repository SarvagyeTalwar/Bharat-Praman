# Bharat Praman — Enterprise Policy & Ministry Knowledge Graph Landing

Dedicated B2B landing folder on the `enterprise-landing` branch, designed for:
- **Standalone Static Deployment**: Point GitHub Pages, Vercel, Netlify, or Cloudflare Pages to `enterprise-landing/`.
- **FastAPI / Railway Deployment**: `main.py` on this branch serves `enterprise-landing/index.html` at `/` and `/enterprise-landing/` while keeping `/api/rag/search`, `/api/rag/ask`, `/api/budget/*`, and `/health` active.

## Files
- `index.html` — Executive landing page with synchronized GraphRAG typewriter workspace, Neo4j subgraph visualizer, telemetry metrics, 3-pillar principles, interactive chunk/RBAC control plane preview, and 8-ministry corpus matrix.
- `styles.css` — Architectural business styling (flat surfaces, zero CSS gradients, zero pill buttons, zero emojis/sparkles).
- `app.js` — Interactive hero choreography, SVG node-edge drawing + click inspector, live `/api/rag/search` fallback hook, control-plane previews, and scroll counters.
