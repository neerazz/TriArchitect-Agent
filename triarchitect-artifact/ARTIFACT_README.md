# TriArchitect Artifact Package

This artifact package contains the implementation and prototype materials for the TriArchitect vision paper.

> **Note:** This is a prototype/vision paper. Results shown are preliminary estimates.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run demo (no API keys needed)
python examples/run_demo.py

# Run full evaluation (requires OpenAI API key)
export OPENAI_API_KEY=your-key
./scripts/run_experiments.sh /path/to/java-projects 50
```

## Package Contents

### Core Framework (`src/`)
| Component | Description |
|-----------|-------------|
| `src/shared/tmg/` | Typed Migration Graph implementation |
| `src/agents/archeologist/` | Java parsing and analysis |
| `src/agents/architect/` | LLM-based migration generation |
| `src/agents/validator/` | Docker-based test execution |
| `src/consensus/` | Validator-Veto Protocol |
| `src/orchestrator/` | Pipeline coordination |

### Evaluation Scripts (`scripts/`)
| Script | Description |
|--------|-------------|
| `run_baseline_zero_shot.py` | Single-prompt LLM baseline |
| `run_baseline_sequential.py` | Multi-agent without shared state |
| `run_triarchitect.py` | Full TriArchitect pipeline |
| `metrics.py` | Pass@1, Hallucination, Semantic metrics |
| `analyze_results.py` | Generate comparison figures |
| `run_experiments.sh` | Master experiment script |

### Paper Materials (`resources/paper/`)
| File | Description |
|------|-------------|
| `main.md` | Full paper content |
| `research.md` | Research bibliography |
| `latex_components.tex` | Tables and algorithms for LaTeX |

## Evaluation Metrics

1. **Pass@1**: Compile + test success rate
2. **Hallucination Rate**: % of non-existent Maven dependencies
3. **Semantic Preservation**: Test method count preservation

## Preliminary Results (Prototype)

| Approach | Pass@1 | Halluc. | Semantic |
|----------|--------|---------|----------|
| GPT-4-turbo Single | 48% | 43% | 91% |
| OpenRewrite (rules) | 62% | 0% | 95% |
| **TriArchitect** | **68%** | **1.8%** | **96%** |

*Preliminary estimates from prototype testing*

## Hardware Requirements

- 16GB RAM minimum
- Docker installed (for Validator agent)
- OpenAI or Anthropic API access

## License

Apache 2.0
