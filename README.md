<a href="https://ds500.paiml.com/rankings/llms" title="LLM Rankings" style="text-decoration: none;">
  <img src="./.github/header.svg" alt="LLM Rankings">
</a>

<h1 align="center"><a href="https://ds500.paiml.com/rankings/llms">Gemini 2.5 Pro</a></h1>
<h5 align="center">Model Evaluation</h5>

This repository holds the code output of GPT 5, used for evaluation with [PMAT](https://github.com/paiml/paiml-mcp-agent-toolkit).

Evaluations are posted at [Pragmatic AI Labs](https://ds500.paiml.com/rankings/llms).

For details on the prompt used, check the [test.yaml](./test.yaml) file.


> [!NOTE]
> This repository does not accept Pull Requests

## How the Overall Score is Calculated

The overall score is calculated on a scale of 0-100 points using three key complexity metrics, each with a maximum penalty of 25 points:

### Scoring Components

| Component | Max Penalty | Calculation Method |
|-----------|-------------|-------------------|
| **Cognitive Complexity** | 25 points | Percentage of functions exceeding cognitive complexity thresholds |
| **Cyclomatic Complexity** | 25 points | Percentage of functions exceeding cyclomatic complexity thresholds |
| **Big-O Complexity** | 25 points | Percentage of functions with high algorithmic complexity (O(n²) or worse) |

### Final Score Formula

```
Final Score = 100 - Cognitive Penalty - Cyclomatic Penalty - Big-O Penalty
```

- **Minimum possible score**: 25/100 (when all three categories reach maximum penalty)
- **Maximum possible score**: 100/100 (when no penalties are applied)

### Penalty Calculation Details

Each penalty is calculated as:
```
Penalty = min(25, (affected_functions / total_functions) × 100)
```

- **Cognitive Complexity**: Functions with high nesting, branching, and logical complexity
- **Cyclomatic Complexity**: Functions with excessive conditional paths and decision points
- **Big-O Complexity**: Functions with O(n²), O(n³), or worse algorithmic complexity

### Grading Scale

The numeric score is converted to a letter grade:

| Grade | Score Range | Percentage |
|-------|-------------|------------|
| A+    | 0.97-1.00   | 97-100%    |
| A     | 0.93-0.96   | 93-96%     |
| A-    | 0.90-0.92   | 90-92%     |
| B+    | 0.87-0.89   | 87-89%     |
| B     | 0.83-0.86   | 83-86%     |
| B-    | 0.80-0.82   | 80-82%     |
| C+    | 0.77-0.79   | 77-79%     |
| C     | 0.73-0.76   | 73-76%     |
| C-    | 0.70-0.72   | 70-72%     |
| D     | 0.60-0.69   | 60-69%     |
| F     | 0.00-0.59   | Below 60%  |

### Evaluation Details

- Repository: This codebase
- Model: Check the ./test.yaml file for model details
- Prompt: See ./test.yaml for the original prompt used
- Results: Available at [LLM Rankings](https://ds500.paiml.com/rankings/llms)

### About the Evaluation System

The Real-World Code Score system evaluates AI-generated code across multiple dimensions to provide a comprehensive quality assessment. Unlike simple correctness checks, it analyzes real-world code quality factors that matter in
production environments.
