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

## Lernplan: Level 2 der Reihe nach, Theorie Level 1 parallel

| Praxis Level 2 (Notebook) | Bezug Theorie Level 1 | Status |
|---|---|---|
| 2.1 Prebuilt Agent instanziieren (`create_agent` + `@tool`) | 1.5 Tools · 1.6 Agentic Loop | ✅ |
| 2.2 Structured Output (JSON-Schema strict, Pydantic `with_structured_output`) | 1.5 Tools (Tool-Definitionen = JSON-Schema) | ⏭ |
| 2.3 Externe Tools integrieren (Tavily; Übung: Wikipedia) | 1.5 Tools | |
| 2.4 LLM-Call-Chain (Prompt Chaining) | 1.7 Design Patterns | |
| 2.5 Agent-Klasse from scratch (nur try_it) · Effektive Prompts (nur try_it) | 1.6 Agentic Loop | |
| 2.6 Loops für mehrstufige Tasks (nur try_it) | 1.6 Agentic Loop | |
| 2.7 Nodes, Edges, Graphs, State in LangGraph | 1.7 Design Patterns | |
| 2.8 State in einem LangGraph-Workflow verwalten | 1.8 Short-/Long-Term Memory | |
| 2.9 Logging · 2.10 API-Fehler · 2.11 Chatbot mit Gedächtnis (nur try_it) | 1.8 Memory (2.11) · weitere offen | |
| 2.12 Streaming · 2.13 Async vs. Sync · 2.14 Prompt-Templates | offen | |
| 2.15 Guardrails · 2.16 Testfälle · 2.17 Performance & Kosten | offen | |

Konvention: Übungen als Kopie mit Kürzel `-WRO` bearbeiten, Originale bleiben unverändert. `.ipynb_checkpoints/` enthalten eine ältere Nummerierung – ignorieren.
