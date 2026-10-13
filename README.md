# O'Reilly Skills – AI Agents: Praxis-Repo

Notebooks und Übungen zur O'Reilly-Skills-Schulung „AI Agents“ (Level 2–4).
Theorie-Notizen liegen in Confluence (Level-1-Index), hier liegt der lauffähige Code.

## Struktur

| Pfad | Inhalt |
|---|---|
| `Jupyter Notebooks/level_2/` | Grundlagen-Praxis: create_agent, Tools, LangGraph-State, Logging, Fehler, Streaming, Guardrails, Tests |
| `Jupyter Notebooks/level_3/` | Conditional Edges, Custom Workflows, MCP-Interop, RAG/Embeddings, Deep Agents, HITL, Memory, FastAPI-Deployment |
| `Jupyter Notebooks/level_4/` | Swarm, Subgraphs, Parallelisierung, Time Travel, Kontextmanagement, Evaluation, Worker-/Scaling-Deployment (Docker/Celery/Redis), Semantic Caching |
| `Jupyter Notebooks/data/` | Beispieldaten (techmart_troubleshooting.csv) |
| `*/guided_practice/` | geführte Tutorials |
| `*/try_it_yourself/` | Übungen (`_try_it`) + Musterlösung (`_try_it_solution`) |
| `AI_Agents_Jupyter Notebooks.zip` | Original-Download, nicht im git (unveränderte Sicherung) |

## Setup (einmalig, im Terminal im Projektordner)

```bash
bash setup.sh                 # venv (.venv), Pakete, Jupyter-Kernel, .env, git init + erster Commit
source .venv/bin/activate     # danach in jeder neuen Shell
```

- Kernel im Notebook: **„Python (AI Agents O'Reilly)“** (VS Code erkennt `.venv` auch direkt).
- API-Keys in `.env` eintragen (`OPENAI_API_KEY`, `TAVILY_API_KEY`, optional `OPENWEATHER_API_KEY`).
- Stack: LangChain 1.x / LangGraph 1.x – eine gemeinsame Umgebung reicht für alle Notebooks.
  Exakte Versionen: `requirements.lock.txt`. Die `%pip install`-Zellen in den Notebooks kann man überspringen.
- Level-4-Deployments (4_14, 4_15) laufen per Docker mit eigener `requirements.txt` im Unterordner.

## Arbeitsweise mit git

- Original-Notebooks bleiben im ersten Commit unverändert → `git diff` zeigt jederzeit, was ich selbst geändert habe.
- Pro Lerneinheit ein Commit, z. B. `git commit -am "2.3 Tools: Tavily-Agent + eigenes Wetter-Tool"`.
- Eigene Experimente in `*_try_it.ipynb` oder neuen Notebooks (`mein_…ipynb`), Lösungen nur zum Abgleich öffnen.

## Lernplan: Theorie Level 1 ↔ Praxis Level 2 parallel

| Theorie Level 1 (Kompetenz) | Status | Praxis Level 2 (Notebook) |
|---|---|---|
| 1.5 Tools (Tool-Anatomie, Description-Feld, MCP) | ✅ Theorie | 2.1 Prebuilt Agent instanziieren (`create_agent`) · 2.3 Tavily-Such-Tool integrieren |
| 1.6 Agentic Loop (Phasen des Loops) | ✅ Theorie | try_it 2.5 Agent-Klassenstruktur · try_it 2.6 Loops implementieren |
| 1.7 Agentic Design Patterns | ✅ Theorie | 2.4 LLM-Call-Chain (Prompt Chaining) · 2.7 Nodes, Edges, Graphs, State in LangGraph |
| 1.8 Short-/Long-Term Memory | ⏭ als Nächstes | 2.8 State in einem LangGraph-Workflow verwalten · try_it 2.11 Chatbot-Agent mit Gedächtnis |
| weitere Level-1-Kompetenzen | offen | 2.2 Structured Output · try_it 2.5 Effektive Prompts · 2.14 Prompt-Templates · 2.9 Logging · 2.10 Fehlerbehandlung · 2.12 Streaming · 2.13 Async vs. Sync · 2.15 Guardrails · 2.16 Testfälle · 2.17 Performance-Metriken |

Hinweis: 2.5, 2.6 und 2.11 gibt es nur unter `try_it_yourself/`. Die `.ipynb_checkpoints/` enthalten eine ältere Nummerierung – ignorieren.
