"""
Prompt templates for the Architect agent.

Contains carefully crafted prompts for migration analysis and
code transformation suggestions.
"""

SYSTEM_PROMPT = """You are an expert Java developer specializing in legacy code migration.
Your task is to analyze Java 8 code and propose migrations to Java 17.

Key principles:
1. NEVER invent or hallucinate APIs or methods that don't exist
2. Always verify that suggested replacements are valid in Java 17
3. Preserve the original code's semantics and behavior
4. Provide clear, actionable migration steps
5. Flag any uncertainties or areas requiring human review

You have access to the Typed Migration Graph (TMG) which contains:
- All classes, methods, and fields in the codebase
- Import dependencies and method call relationships
- Current migration state of each artifact

Use this context to ensure your proposals are consistent with the codebase."""


ANALYSIS_PROMPT = """Analyze the following Java 8 code artifact for migration to Java 17.

## Artifact Information
- **ID**: {node_id}
- **Type**: {node_type}
- **File**: {file_path}
- **Dependencies**: {dependencies}

## Source Code
```java
{source_code}
```

## Known Deprecated APIs Used
{deprecated_apis}

## Task
Provide a detailed analysis including:
1. **Deprecation Issues**: List all deprecated Java 8 APIs used
2. **Migration Steps**: Specific changes needed for Java 17 compatibility
3. **Risk Assessment**: Potential issues or side effects
4. **Confidence Score**: Your confidence in the migration (0.0-1.0)

Respond in the following JSON format:
{{
    "deprecations": [
        {{"api": "...", "replacement": "...", "reason": "..."}}
    ],
    "migration_steps": [
        {{"step": 1, "description": "...", "code_before": "...", "code_after": "..."}}
    ],
    "risk_level": "low|medium|high",
    "risk_factors": ["..."],
    "confidence": 0.0-1.0,
    "requires_human_review": true|false,
    "notes": "..."
}}"""


MIGRATION_PROMPT = """Generate the migrated Java 17 code for the following artifact.

## Context
- **Source Version**: Java 8
- **Target Version**: Java 17
- **Node ID**: {node_id}

## Original Code
```java
{original_code}
```

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

Respond with the migrated code wrapped in a code block, followed by a rationale.

```java
// Migrated code here
```

**Rationale**: [Explain key changes and why they were made]
**Confidence**: [0.0-1.0 confidence score]"""


VALIDATION_PROMPT = """Review the following migration proposal for correctness.

## Original Code (Java 8)
```java
{original_code}
```

## Proposed Migration (Java 17)
```java
{proposed_code}
```

## Migration Rationale
{rationale}

## Validation Checklist
Please verify:
1. [ ] All deprecated APIs are properly replaced
2. [ ] No hallucinated APIs or methods are used
3. [ ] Behavior is preserved (semantic equivalence)
4. [ ] Imports are complete and correct
5. [ ] No compilation errors expected
6. [ ] No runtime behavior changes

Respond in JSON format:
{{
    "approved": true|false,
    "issues": [
        {{"severity": "error|warning", "description": "...", "line": null|int}}
    ],
    "suggestions": ["..."],
    "confidence": 0.0-1.0
}}"""


CONSENSUS_PROMPT = """As part of the cyclic consensus protocol, review this migration proposal.

## Proposal Summary
- **Node**: {node_id}
- **Proposer**: Architect Agent
- **Current Votes**: {current_votes}

## Original vs Proposed
{code_diff}

## Previous Round Feedback
{previous_feedback}

## Your Role
You are acting as a {role} in this consensus round. Your responsibilities:

**If Archeologist**: Check semantic preservation and verify dependencies
**If Validator**: Check for testability and runtime safety
**If Architect**: Defend or revise the proposal based on feedback

Provide your vote and rationale:
{{
    "vote": "approve|reject|abstain",
    "confidence": 0.0-1.0,
    "feedback": "...",
    "required_changes": ["..."] // Only if rejecting
}}"""
