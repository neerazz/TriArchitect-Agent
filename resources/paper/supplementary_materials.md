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

<!-- Required for javax.activation migration -->
<dependency>
    <groupId>jakarta.activation</groupId>
    <artifactId>jakarta.activation-api</artifactId>
    <version>2.1.2</version>
</dependency>
```

---

## Appendix B: Prompt Templates

### Analysis Prompt (Architect Agent)

```
You are an expert Java developer specializing in legacy code migration.
Your task is to analyze Java 8 code and propose migrations to Java 17.

Key principles:
1. NEVER invent or hallucinate APIs or methods that don't exist
2. Always verify that suggested replacements are valid in Java 17
3. Preserve the original code's semantics and behavior
4. Provide clear, actionable migration steps
5. Flag any uncertainties or areas requiring human review

## Artifact Information
- **ID**: {node_id}
- **Type**: {node_type}
- **File**: {file_path}
- **Dependencies**: {dependencies}

## Source Code
{source_code}

## Known Deprecated APIs Used
{deprecated_apis}

## Task
Provide a detailed analysis including:
1. **Deprecation Issues**: List all deprecated Java 8 APIs used
2. **Migration Steps**: Specific changes needed for Java 17 compatibility
3. **Risk Assessment**: Potential issues or side effects
4. **Confidence Score**: Your confidence in the migration (0.0-1.0)

Respond in JSON format.
```

### Migration Prompt (Architect Agent)

```
Generate the migrated Java 17 code for the following artifact.

## Context
- **Source Version**: Java 8
- **Target Version**: Java 17
- **Node ID**: {node_id}

## Original Code
{original_code}

## Migration Requirements
{migration_requirements}

## Dependencies Context
The following related artifacts have already been migrated:
{migrated_dependencies}

## Instructions
1. Generate the complete migrated code
2. Ensure all imports are updated
3. Replace deprecated APIs with their modern equivalents
4. Maintain backward compatibility where possible
5. Add comments for any non-obvious changes

Respond with the migrated code in a Java code block, followed by rationale
and confidence score.
```

---

## Appendix C: Consensus Protocol Pseudocode

```python
class ConsensusProtocol:
    def __init__(self, threshold=0.85, max_iterations=3):
        self.threshold = threshold
        self.max_iterations = max_iterations
    
    def run(self, proposal, agents):
        for iteration in range(1, self.max_iterations + 1):
            signatures = SignatureCollection(proposal.id)
            
            # Phase 1: Collect votes from all agents
            for agent in agents:
                vote = agent.verify(proposal)
                signatures.add(vote)
            
            # Phase 2: Calculate consensus score
            score = self.calculate_score(signatures)
            
            # Phase 3: Check stopping conditions
            if score >= self.threshold and signatures.all_approved():
                return ConsensusResult(APPROVED, score, signatures)
            
            if signatures.has_hard_rejection():
                return ConsensusResult(REJECTED, score, signatures)
            
            # Phase 4: Revision cycle
            feedback = signatures.get_feedback()
            proposal = agents['architect'].revise(proposal, feedback)
        
        return ConsensusResult(NEEDS_REVIEW, score, signatures)
    
    def calculate_score(self, signatures):
        total = len(signatures)
        approvals = signatures.approval_count()
        avg_confidence = signatures.average_confidence()
        
        base_score = (approvals / total) * avg_confidence
        unanimous_bonus = 0.1 if signatures.is_unanimous() else 0
        
        return min(1.0, base_score + unanimous_bonus)
```

---

## Appendix D: MigrationBench Details

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

### Deprecated API Distribution

| API Category | Count | Percentage |
|--------------|-------|------------|
| javax.xml.bind (JAXB) | 1,234 | 32.1% |
| java.util.Date/Calendar | 892 | 23.2% |
| finalize() | 456 | 11.9% |
| sun.misc.* | 387 | 10.1% |
| javax.annotation | 312 | 8.1% |
| Other | 566 | 14.7% |

---

## Appendix E: Experimental Configuration

### Hardware
- CPU: AMD EPYC 7763 (64 cores)
- RAM: 256 GB DDR4
- GPU: NVIDIA A100 (80GB) - for LLM inference
- Storage: 2TB NVMe SSD

### Software
- OS: Ubuntu 22.04 LTS
- Python: 3.11
- Java: OpenJDK 8 (baseline), OpenJDK 17 (target)
- Docker: 24.0.5
- Maven: 3.9.4

### LLM Configuration
- Model: GPT-4-0125-preview
- Temperature: 0.3
- Max tokens: 4096
- Top-p: 1.0

### Consensus Parameters
- Threshold (θ): 0.85
- Max iterations (k): 3
- Agent weights: Archeologist=0.3, Architect=0.4, Validator=0.3

---

## Appendix F: Statistical Analysis

### Significance Testing

All reported improvements are statistically significant at p < 0.001 using paired t-tests with Bonferroni correction for multiple comparisons.

| Comparison | t-statistic | p-value |
|------------|-------------|---------|
| TriArchitect vs GPT-4 Single | 14.23 | < 0.001 |
| TriArchitect vs GPT-4 + RAG | 11.87 | < 0.001 |
| TriArchitect vs Claude-3 | 12.94 | < 0.001 |
| TriArchitect vs MigrationMiner | 7.45 | < 0.001 |

### Effect Size (Cohen's d)

| Comparison | Cohen's d | Interpretation |
|------------|-----------|----------------|
| vs GPT-4 Single | 1.82 | Large |
| vs GPT-4 + RAG | 1.54 | Large |
| vs Claude-3 | 1.68 | Large |
| vs MigrationMiner | 0.91 | Large |

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

### Example: Complex Refactoring

Some migrations require coordinated changes across multiple files that exceed our single-node approach:

```java
// Before: Spread across 3 files
class DateUtils {
    public static Date parse(String s) { ... }
}
class Formatter {
    public String format(Date d) { ... }
}
class Handler {
    public void process(Date d) { ... }
}

// After: Requires atomic update of all 3
// TriArchitect handles via batch_transition
```

---

## Appendix H: Reproducibility Checklist

- [x] Source code available (GitHub repository)
- [x] Environment requirements documented (requirements.txt, Dockerfile)
- [x] Benchmark dataset available (MigrationBench)
- [x] Random seeds specified (42 for all experiments)
- [x] Hyperparameters documented (Appendix E)
- [x] Statistical tests specified (Appendix F)
- [x] Compute requirements noted (Appendix E)
- [x] Evaluation scripts included (scripts/evaluate.py)
