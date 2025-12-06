# TriArchitect

> **A Shared-State Multi-Agent Framework for Safe Legacy Code Migration**

TriArchitect is an intelligent code migration system that uses three specialized AI agents—Archeologist, Architect, and Validator—coordinated through a Typed Migration Graph (TMG) and Cyclic Consensus Protocol to safely migrate Java 8 codebases to Java 17.

## Key Features

- 🔍 **Static Analysis** - Parse Java source files and build dependency graphs
- 🤖 **Multi-Agent Architecture** - Three specialized agents with distinct responsibilities
- 📊 **Typed Migration Graph (TMG)** - Persistent semantic state for code artifacts
- ✅ **Consensus Protocol** - Cyclic proposal-verify-sign loop for reliable migrations
- 🐳 **Docker Isolation** - Run tests in isolated containers for safety
- 📈 **Rich Observability** - Structured logging with correlation IDs

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                            │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐               │
│  │Archeologist│    │ Architect │    │ Validator │               │
│  │  (Parser)  │◄──►│   (LLM)   │◄──►│ (Docker)  │               │
│  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘               │
│        │                │                │                      │
│        └────────────────┼────────────────┘                      │
│                         ▼                                       │
│              ┌─────────────────────┐                            │
│              │  Typed Migration    │                            │
│              │  Graph (TMG)        │                            │
│              └─────────────────────┘                            │
│                         ▼                                       │
│              ┌─────────────────────┐                            │
│              │ Consensus Protocol  │                            │
│              └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Docker (optional, for isolated test execution)
- OpenAI or Anthropic API key (for Architect agent)

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd TriArchitect-Agent

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

## Quick Start

### Run the Demo

```bash
python examples/run_demo.py
```

### Analyze a Repository

```bash
python -m src.cli analyze /path/to/java/project
```

### Full Migration (requires API key)

```bash
python -m src.cli migrate /path/to/java/project --dry-run
```

### Validate a Project

```bash
python -m src.cli validate /path/to/maven/project
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `analyze <path>` | Run static analysis with Archeologist agent |
| `migrate <path>` | Full migration pipeline with all agents |
| `validate <path>` | Run tests with Validator agent |
| `version` | Show version and configuration |

### Options

- `--verbose, -v` - Enable verbose output
- `--output, -o <dir>` - Output directory for results
- `--dry-run` - Don't apply changes (migrate only)
- `--no-docker` - Use local Maven instead of Docker
- `--max-proposals <n>` - Limit proposals to process

## Configuration

Configuration is managed via environment variables or `.env` file:

```env
# LLM Configuration
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
LLM_PROVIDER=openai  # or anthropic

# Consensus Settings
CONSENSUS_THRESHOLD=0.85
CONSENSUS_MAX_ITERATIONS=3

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=console  # or json

# Docker
DOCKER_IMAGE=maven:3.9-eclipse-temurin-17
DOCKER_TIMEOUT=300
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src --cov-report=term-missing

# Run specific tests
python -m pytest tests/shared/test_tmg.py -v
```

## Project Structure

```
TriArchitect-Agent/
├── src/
│   ├── agents/
│   │   ├── archeologist/    # Static analysis agent
│   │   ├── architect/       # LLM planning agent
│   │   └── validator/       # Testing agent
│   ├── consensus/           # Consensus protocol
│   ├── orchestrator/        # Main engine
│   └── shared/
│       ├── tmg/             # Typed Migration Graph
│       ├── config.py        # Settings
│       └── logger.py        # Structured logging
├── tests/
├── examples/
└── requirements.txt
```

## The Three Agents

### 🔍 Archeologist
- Parses Java source files using `javalang`
- Extracts classes, methods, imports, and dependencies
- Populates the TMG with nodes and edges
- Identifies deprecated Java 8 APIs

### 🏗️ Architect
- Uses LLM (GPT-4o or Claude) for intelligent planning
- Generates migration proposals
- Creates code transformations
- Provides confidence scores for proposals

### ✅ Validator
- Runs Maven tests in Docker containers
- Compares test counts (before/after)
- Verifies semantic preservation
- Signs proposals in consensus rounds

## The Typed Migration Graph (TMG)

The TMG is the shared state mechanism that enables coordination:

- **Nodes**: Code artifacts (classes, methods, fields)
- **Edges**: Dependencies (imports, method calls)
- **States**: UNPROCESSED → ANALYZED → DEPRECATED → MIGRATED

## Consensus Protocol

The Cyclic Consensus Protocol ensures reliability:

1. **Proposal**: Architect generates migration
2. **Verification**: Validator runs tests
3. **Signing**: All agents vote
4. **Decision**: Approve if score ≥ threshold

## License

MIT

## Contributing

See AGENTS.md for development guidelines.
