# TriArchitect Artifact Package

**Paper ID:** XXX  
**Venue:** ICSE 2027 Technical Track  
**Status:** Anonymous Submission

---

## Quick Start

```bash
# Clone repository
git clone https://anonymous.4open.science/r/triarchitect-artifact

# Install dependencies
pip install -e .

# Run demo (no API keys needed - uses mock responses)
python examples/run_demo.py

# Run full evaluation (requires OpenAI API key)
export OPENAI_API_KEY=your-key
./scripts/run_experiments.sh ./data/J8-to-J17-Bench 300
```

## Repository Structure

```
triarchitect-artifact/
├── src/                      # Core framework
│   ├── shared/tmg/           # Typed Migration Graph
│   ├── agents/               # Archeologist, Architect, Validator
│   ├── consensus/            # Cyclic Consensus Protocol
│   └── orchestrator/         # Pipeline coordination
├── scripts/                  # Evaluation scripts
│   ├── run_baseline_zero_shot.py
│   ├── run_baseline_sequential.py
│   ├── run_triarchitect.py
│   ├── metrics.py
│   └── analyze_results.py
├── data/                     # J8-to-J17-Bench subset
│   └── J8-to-J17-Bench/       # 300 Java 8→17 migration tasks
├── docker/                   # Validator container
│   └── Dockerfile.validator
└── tests/                    # Unit tests (94% coverage)
```

## Artifact Claims

| Claim | Location | Reproducibility |
|-------|----------|-----------------|
| 94.2% semantic preservation | Table 1 | `scripts/run_triarchitect.py` |
| 86.3% hallucination reduction | Section 6.2 | `scripts/metrics.py` |
| Sensitivity analysis ±1.5% | Section 5.4 | `scripts/sensitivity.py` |
| Wall-clock 47s/migration | Section 6.2 | Logged in output |

## Hardware Requirements

- **RAM:** 16GB minimum
- **Storage:** 10GB for dataset
- **Docker:** Required for Validator agent
- **API Access:** OpenAI (GPT-5.1) or Anthropic (Claude Opus 4.5)

## Reproducing Key Results

### Table 1: Migration Quality Comparison

```bash
# Run all baselines (expects ~8 hours on 8-core machine)
./scripts/run_experiments.sh ./data/J8-to-J17-Bench 300

# Output: evaluation_results/final_analysis.json
```

### Table 2: Ablation Study

```bash
# Run ablation configurations
python scripts/run_ablation.py \
  --config full \
  --config no_consensus \
  --config no_validator \
  --config no_tmg \
  --config random_order
```

### Sensitivity Analysis

```bash
python scripts/sensitivity.py \
  --theta_range 0.70,0.75,0.80,0.85,0.90,0.95 \
  --weight_range 0.30,0.35,0.40,0.45,0.50
```

## J8-to-J17-Bench Dataset

300 Java 8→17 migration tasks from:

| Category | Projects | Tasks |
|----------|----------|-------|
| Apache Commons | 12 | 98 |
| Spring Framework | 8 | 76 |
| Utilities (Guava, Jackson) | 15 | 64 |
| Enterprise (Hibernate, etc.) | 15 | 62 |

**Selection Criteria:**
- Active maintenance (commit in last 6 months)
- Minimum 40% test coverage
- At least 5 deprecated Java 8 API usages
- Successful Maven build pre-migration

## Docker Validator Setup

```bash
# Build validator image
docker build -t triarchitect-validator:17 -f docker/Dockerfile.validator .

# Test execution
docker run --rm -v $(pwd)/test_project:/project triarchitect-validator:17
```

## API Configuration

```bash
# Create .env file
cp .env.example .env

# Edit with your API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Or set environment variables
export OPENAI_API_KEY=sk-...
```

## Expected Runtime

| Configuration | Time (300 repos) |
|---------------|------------------|
| GPT-5.1 Single | ~2 hours |
| GPT-5.1 + RAG | ~3 hours |
| Claude Opus 4.5 | ~2.5 hours |
| MetaGPT | ~6 hours |
| TriArchitect | ~4 hours |

## License

Apache 2.0

## Contact

For questions during review: [anonymous email will be provided]
