#!/bin/bash
# run_experiments.sh - Full J8-to-J17-Bench Evaluation Pipeline
# 
# Usage: ./run_experiments.sh [DATA_PATH] [NUM_REPOS]

set -e

DATASET_PATH="${1:-/mnt/data/J8-to-J17-Bench/selected}"
NUM_REPOS="${2:-300}"
RESULTS_DIR="./evaluation_results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $RESULTS_DIR

echo "=========================================="
echo "TriArchitect J8-to-J17-Bench Evaluation"
echo "=========================================="
echo "Dataset:    $DATASET_PATH"
echo "Repos:      $NUM_REPOS"
echo "Output:     $RESULTS_DIR"
echo "Timestamp:  $TIMESTAMP"
echo "=========================================="
echo ""

# Check Python environment
python3 -c "import src.orchestrator" 2>/dev/null || {
    echo "ERROR: TriArchitect not installed. Run: pip install -e ."
    exit 1
}

# Phase 1: Zero-Shot Baseline
echo "[Phase 1/3] Running Zero-Shot LLM baseline..."
python3 scripts/run_baseline_zero_shot.py \
  --input_dir "$DATASET_PATH" \
  --num_repos $NUM_REPOS \
  --output_file "$RESULTS_DIR/zero_shot_$TIMESTAMP.json" \
  --provider openai \
  2>&1 | tee "$RESULTS_DIR/zero_shot.log"

# Phase 2: Sequential Agent Baseline  
echo ""
echo "[Phase 2/3] Running Sequential Agent baseline..."
python3 scripts/run_baseline_sequential.py \
  --input_dir "$DATASET_PATH" \
  --num_repos $NUM_REPOS \
  --output_file "$RESULTS_DIR/sequential_$TIMESTAMP.json" \
  --provider openai \
  2>&1 | tee "$RESULTS_DIR/sequential.log"

# Phase 3: TriArchitect
echo ""
echo "[Phase 3/3] Running TriArchitect..."
python3 scripts/run_triarchitect.py \
  --input_dir "$DATASET_PATH" \
  --num_repos $NUM_REPOS \
  --output_file "$RESULTS_DIR/triarchitect_$TIMESTAMP.json" \
  2>&1 | tee "$RESULTS_DIR/triarchitect.log"

# Analyze Results
echo ""
echo "[Analysis] Generating comparison figures..."
python3 scripts/analyze_results.py \
  --zero_shot "$RESULTS_DIR/zero_shot_$TIMESTAMP.json" \
  --sequential "$RESULTS_DIR/sequential_$TIMESTAMP.json" \
  --triarchitect "$RESULTS_DIR/triarchitect_$TIMESTAMP.json" \
  --output_file "$RESULTS_DIR/final_analysis_$TIMESTAMP.json" \
  --figures_dir "$RESULTS_DIR/figures"

echo ""
echo "=========================================="
echo "Evaluation Complete!"
echo "=========================================="
echo "Results:  $RESULTS_DIR/final_analysis_$TIMESTAMP.json"
echo "Figures:  $RESULTS_DIR/figures/"
echo "=========================================="
