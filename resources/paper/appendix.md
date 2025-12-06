# TriArchitect Supplementary Materials

## Appendix A: Complete Deprecation Knowledge Base

### Java 8 → Java 17 API Mappings

| Deprecated API (Java 8) | Replacement (Java 17) | Migration Complexity |
|-------------------------|----------------------|---------------------|
| `javax.xml.bind.*` | `jakarta.xml.bind.*` | Medium |
| `javax.activation.*` | `jakarta.activation.*` | Medium |
| `javax.annotation.*` | `jakarta.annotation.*` | Low |
| `java.lang.Object.finalize()` | `java.lang.ref.Cleaner` | High |
| `java.util.Date` | `java.time.LocalDate/ZonedDateTime` | High |
| `java.util.Calendar` | `java.time.LocalDate/LocalTime` | High |
| `java.security.AccessControlException` | SecurityManager removal | High |
| `sun.misc.BASE64Encoder` | `java.util.Base64` | Low |
| `sun.misc.Unsafe` | VarHandle API | High |
| `java.util.Hashtable` | `ConcurrentHashMap` | Low |
| `java.util.Vector` | `ArrayList` | Low |
| `java.util.Stack` | `ArrayDeque` | Low |
| `Thread.stop()` | Cooperative interruption | High |
| `Thread.suspend()/resume()` | Lock-based synchronization | High |
| `Runtime.getRuntime().exec(String)` | `ProcessBuilder` | Medium |

### Build Configuration Changes

#### Maven

```xml
<!-- Required for javax.xml.bind migration -->
<dependency>
    <groupId>jakarta.xml.bind</groupId>
    <artifactId>jakarta.xml.bind-api</artifactId>
    <version>4.0.0</version>
</dependency>
<dependency>
    <groupId>org.glassfish.jaxb</groupId>
    <artifactId>jaxb-runtime</artifactId>
    <version>4.0.3</version>
</dependency>
```

---

## Appendix B: Prompt Templates

### Analysis Prompt (Archeologist Agent)

```
You are an expert Java developer specializing in legacy code migration.
Your task is to analyze Java 8 code and identify deprecated APIs.

## Artifact Information
- **ID**: {node_id}
- **Type**: {node_type}

## Source Code
{source_code}

## Task
List all deprecated Java 8 APIs used and their modern replacements.
```

### Constraints-Injected Prompt (Architect Agent)

```
Generate the migrated Java 17 code for {node_id}.

## TMG Constraints (CRITICAL)
The following dependencies have been MIGRATED. You MUST use new package names:
{migrated_dependencies}
(e.g., javax.xml.bind -> jakarta.xml.bind)

## Instructions
1. Replace all deprecated APIs.
2. adhere strictly to the TMG constraints above. 
3. Do not assume 'javax' availability if TMG says it is gone.
```

---

## Appendix C: Validator-Veto Protocol Pseudocode

```python
class ValidatorVetoProtocol:
    def __init__(self, max_iterations=3):
        self.max_iterations = max_iterations
    
    def run(self, proposal, agents):
        current_proposal = proposal
        
        for iteration in range(1, self.max_iterations + 1):
            # Phase 1: Verification (The Veto)
            validation_result = agents['validator'].verify(current_proposal)
            
            # Phase 2: Decision
            if validation_result.status == 'PASSED':
                return ConsensusResult(APPROVED, current_proposal)
            
            if validation_result.status == 'HARD_FAILURE':
                 # Cannot be fixed (e.g. infinite loop)
                return ConsensusResult(REJECTED, error=validation_result.error)
            
            # Phase 3: Revision Cycle
            # Architect receives stderr from Validator
            feedback = validation_result.stderr
            current_proposal = agents['architect'].revise(current_proposal, feedback)
        
        # Exhausted retries
        return ConsensusResult(NEEDS_HUMAN_REVIEW)
```

---

## Appendix D: J8-to-J17-Bench Details

### Project Selection Criteria

1. **Active maintenance**: Updated within last 12 months
2. **Test coverage**: Minimum 40% line coverage
3. **Java 8 baseline**: Compiles with Java 8
4. **Deprecated API usage**: Contains at least 5 deprecated API usages
5. **Open source**: Apache 2.0 or MIT license

### Benchmark Statistics

| Metric | Value |
|--------|-------|
| Total Projects | 50 |
| Total Migration Tasks | 1,000 |
| Median Tests per Project | 847 |
| Average KLOC per Project | 45.3 |
| Total Deprecated API Usages | 3,847 |

---

## Appendix E: Experimental Configuration

### Hardware
- CPU: AMD EPYC 7763 (64 cores)
- RAM: 256 GB DDR4
- GPU: NVIDIA H100 (80GB) - Updated Dec 2025
- Storage: 2TB NVMe SSD

### Software
- OS: Ubuntu 24.04 LTS
- Python: 3.12
- Java: OpenJDK 8 (baseline), OpenJDK 17 (target)
- Docker: 26.0.0
- Maven: 3.9.6

### LLM Configuration
- **GPT-5 (Preview):** `gpt-5-preview-2025-08-07`
- **Claude Opus 4.5:** `claude-3-opus-20251124`
- **GPT-4-turbo:** `gpt-4-turbo-2024-04-09`

---

## Appendix F: Statistical Analysis

### Significance Testing (Welch's t-test)

| Comparison | t-statistic | p-value | Significance |
|------------|-------------|---------|--------------|
| TriArchitect vs GPT-5 (Preview) | 3.12 | 0.002 | **Significant** (p < 0.05) |
| TriArchitect vs Claude Opus 4.5 | 4.45 | < 0.001 | **Significant** (p < 0.001) |
| TriArchitect vs AgentCoder | 5.87 | < 0.001 | **Significant** (p < 0.001) |

### Effect Size (Cohen's d)

| Comparison | Cohen's d | Interpretation |
|------------|-----------|----------------|
| vs GPT-5 (Preview) | 0.38 | Small-Medium |
| vs Claude Opus 4.5 | 0.52 | Medium |
| vs AgentCoder | 0.65 | Medium-Large |

**Interpretation:** While the gap between TriArchitect and pure LLMs (GPT-5) has narrowed compared to GPT-4 (d=1.82), the "State consistency" advantage remains statistically significant.

---

## Appendix G: Failure Analysis

### Categories of Remaining Failures

| Failure Type | Percentage | Root Cause |
|--------------|------------|------------|
| Test flakiness | 3.2% | Non-deterministic tests |
| Complex refactoring | 2.8% | Beyond single-node migration |
| Undocumented APIs | 2.1% | Internal/sun.* packages |
| Build configuration | 2.0% | Complex multi-module setups |
| Environment-specific | 1.6% | OS/filesystem dependencies |

---

## Appendix H: Reproducibility Checklist

- [x] Source code available (GitHub repository)
- [x] Environment requirements documented (requirements.txt, Dockerfile)
- [x] Benchmark dataset available (J8-to-J17-Bench)
- [x] Random seeds specified (42 for all experiments)
- [x] Hyperparameters documented (Appendix E)
- [x] Statistical tests specified (Appendix F)
