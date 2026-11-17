# TravelBuddy

**AI-assisted travel planning, from a natural-language request to a human-reviewed itinerary.**

TravelBuddy coordinates specialist agents to gather flight-related, accommodation, weather, and budget information, then drafts a personalized travel plan. Review the draft, approve it, or request a revision before receiving the final response.

> TravelBuddy is a planning assistant. It does not book travel. Verify routes, prices, availability, and weather with providers before making decisions.

## Highlights

- **Natural-language trip requests** — describe your destination, dates, budget, and preferences in plain language.
- **Specialist research agents** — an LLM supervisor selects research agents for airport and airline data, accommodation search, and destination weather.
- **Budget-aware itineraries** — budget analysis and itinerary drafting combine the request with available research results.
- **Human-in-the-loop review** — approve a draft or provide feedback to guide a revision.
- **Resumable planning sessions** — LangGraph checkpoints are stored in PostgreSQL and associated with a thread ID.
- **Guardrail checks** — AWS Bedrock Guardrails checks user input and can block content or anonymize PII according to the configured guardrail.
- **API and web interface** — use the FastAPI endpoints directly or plan trips through the Streamlit interface.

## How it works

```mermaid
flowchart TD
    U[Travel request] --> G[AWS Bedrock Guardrail]
    G --> S[Groq supervisor]
    S --> F[Flight data agent]
    S --> H[Accommodation research agent]
    S --> W[Weather agent]
    F --> J[Join research results]
    H --> J
    W --> J
    J --> B[Budget analysis]
    B --> I[Draft itinerary]
    I --> R{Human review}
    R -->|Approve or request revision| L[Final response]
    J -. checkpointed by thread ID .-> P[(PostgreSQL)]
    R -. resume workflow .-> P
```

The research agents use MCP integrations: AviationStack for airport and airline data, Tavily for accommodation research, and a local OpenWeather MCP server for current conditions and forecasts. The workflow is orchestrated with LangGraph and uses a configured Groq chat model for supervisor, budget, itinerary, and final-response generation.

## Technology

| Area | Tools |
| --- | --- |
| Language | Python 3.13+ |
| UI and API | Streamlit, FastAPI, Uvicorn |
| Agent workflow | LangChain, LangGraph, Groq |
| Tool integration | Model Context Protocol (MCP), AviationStack, Tavily, OpenWeather |
| Persistence | PostgreSQL, LangGraph PostgreSQL checkpointer |
| Safety | AWS Bedrock Guardrails |
| Optional tracing | LangSmith |

## Requirements

- Python 3.13 or newer
- [`uv`](https://docs.astral.sh/uv/) installed and available on your `PATH`
- PostgreSQL database reachable from the application
- AWS credentials and permissions to call Bedrock Guardrails
- API credentials for Groq, Tavily, and AviationStack
- OpenWeather API key for weather results
- Network access to the configured external services

The AviationStack MCP server is started through `uvx`, which is installed with `uv`.

## Quick start

### 1. Get the code and install dependencies

```bash
git clone https://github.com/Pavan-220405/TravelBuddy.git
cd TravelBuddy
uv sync
```

### 2. Configure environment variables

Create a `.env` file in the repository root:

```dotenv
# Required model and data service credentials
GROQ_API_KEY=your_groq_api_key
MEDIUM_MODEL=your_groq_model_name
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
OPENWEATHER_API_KEY=your_openweather_api_key

# PostgreSQL used for LangGraph checkpoints
DATABASE_URL=postgresql://postgres:password@localhost:5432/travelbuddy

# AWS Bedrock Guardrails
AWS_DEFAULT_REGION=your_aws_region
BEDROCK_GUARDRAIL_ID=your_guardrail_id
BEDROCK_GUARDRAIL_VERSION=your_guardrail_version

# Optional LangSmith tracing
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=travelbuddy
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# Optional: override the API URL used by the Streamlit UI
# TRAVELBUDDY_API_URL=http://localhost:8000
```

`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are not required when AWS credentials are supplied through another supported boto3 provider, such as an AWS profile or role. Keep real credentials private; do not commit `.env`.

| Variable | Required | Used for |
| --- | :---: | --- |
| `GROQ_API_KEY` | Yes | Groq model access |
| `MEDIUM_MODEL` | Yes | Groq model name |
| `TAVILY_API_KEY` | Yes | Tavily MCP accommodation research |
| `AVIATIONSTACK_API_KEY` | Yes | AviationStack MCP airport and airline data |
| `OPENWEATHER_API_KEY` | Yes for weather | Local weather MCP server |
| `DATABASE_URL` | Yes | PostgreSQL graph checkpoint storage |
| `AWS_DEFAULT_REGION` | Yes | AWS Bedrock Runtime region |
| `BEDROCK_GUARDRAIL_ID` | Yes | Guardrail applied to trip requests |
| `BEDROCK_GUARDRAIL_VERSION` | Yes | Guardrail version to apply |
| `LANGSMITH_*` | Optional | LangSmith tracing configuration |
| `TRAVELBUDDY_API_URL` | Optional | API base URL for the Streamlit UI; defaults to `http://localhost:8000` |

### 3. Start the services

Start PostgreSQL and make sure the database in `DATABASE_URL` exists. Then run the API and UI in separate terminals from the project root.

**Terminal 1 — API**

```bash
uv run uvicorn app.backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Streamlit UI**

```bash
uv run streamlit run frontend_v2.py --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501) to use the application. The API's interactive documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## API

### Health check

```http
GET /api/health
```

### Generate a draft

```bash
curl -X POST http://localhost:8000/api/trips/draft \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "thread_id": "demo_user_trip_001",
    "query": "Plan a 7-day Japan trip under INR 200000 with budget hotels and no overnight flights."
  }'
```

The response includes selected agents, available research, budget analysis, a draft itinerary, and a status. A draft requiring review returns `"status": "awaiting_approval"`.

### Approve or request a revision

Send the approval decision using the same `thread_id` as the draft:

```bash
curl -X POST http://localhost:8000/api/trips/demo_user_trip_001/approval \
  -H "Content-Type: application/json" \
  -d '{
    "approved": false,
    "feedback": "Reduce the number of hotel changes and add one rest day."
  }'
```

Set `"approved": true` to approve the itinerary. The response contains the final travel plan.

## Project structure

```text
.
├── app/
│   ├── agent/          # LangGraph state, agents, prompts, and workflow
│   ├── backend/        # FastAPI application, routes, schemas, and services
│   ├── guardrails/     # AWS Bedrock Guardrails integration
│   └── mcp_sc/         # MCP client and local OpenWeather MCP server
├── frontend_v2.py      # Streamlit UI (recommended entry point)
├── frontend_v1.py      # Legacy direct-graph UI
├── pyproject.toml      # Project metadata and dependencies
├── requirements.txt    # Pip-compatible dependency list
└── uv.lock             # Locked uv dependency resolution
```

## MCP integrations

The FastAPI application loads its MCP tools during startup:

- **Tavily** — remote MCP endpoint for accommodation research.
- **AviationStack** — launched with `uvx aviationstack-mcp` for airport and airline data.
- **OpenWeather** — local stdio MCP server in `app/mcp_sc/openweather_mcp.py` for current weather and forecast data.

## Development

Compile the application modules to check for Python syntax errors:

```bash
uv run python -m compileall app frontend_v2.py
```

The MCP smoke test calls the configured services and therefore requires valid API credentials and network access:

```bash
uv run python app/mcp_sc/test_mcp.py
```

## Notes

- TravelBuddy provides planning research and generated suggestions; it does not reserve or purchase travel services.
- Third-party data may be incomplete or change after a plan is generated. Confirm details with the relevant provider before booking.
- Avoid entering payment details, secrets, or other sensitive information in trip requests.
