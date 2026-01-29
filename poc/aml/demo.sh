#!/bin/bash
# =============================================================================
# DecisionGraph AML POC Demo Script
# =============================================================================
#
# Usage: ./demo.sh [actimize|csv|both]
#
# Demonstrates the full AML monitoring pipeline:
# 1. Map vendor data to CaseBundle format
# 2. Run decision engine with Canadian FinCrime rules
# 3. Display results and verification
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default to both demos
DEMO_TYPE="${1:-both}"

echo -e "${CYAN}"
echo "============================================================================"
echo "  DecisionGraph AML Monitoring POC"
echo "============================================================================"
echo -e "${NC}"

# Function to run Actimize demo
run_actimize_demo() {
    echo -e "${YELLOW}>>> Demo 1: NICE Actimize Transaction Monitoring${NC}"
    echo ""
    echo "Source: Actimize TM Alert Export"
    echo "Customer: Maria Rodriguez (CUST-12345)"
    echo "Scenario: Potential structuring with high-risk jurisdiction exposure"
    echo ""

    echo -e "${BLUE}Step 1: Map Actimize export to CaseBundle${NC}"
    "$ROOT_DIR/dg" map-case \
        --input "$ROOT_DIR/adapters/fincrime/actimize/example_input.json" \
        --adapter "$ROOT_DIR/adapters/fincrime/actimize/mapping.yaml" \
        --out "$SCRIPT_DIR/output/actimize_mapped.json"

    echo ""
    echo -e "${BLUE}Step 2: Run decision engine with Canadian FinCrime rules${NC}"
    set +e
    "$ROOT_DIR/dg" run-case \
        --case "$SCRIPT_DIR/output/actimize_mapped.json" \
        --pack "$ROOT_DIR/packs/fincrime_canada.yaml" \
        --out "$SCRIPT_DIR/output/"
    EXIT_CODE=$?
    set -e

    echo ""
    echo -e "${BLUE}Step 3: Display verdict summary${NC}"
    echo ""
    CASE_DIR="$SCRIPT_DIR/output/ACT-2026-00789"
    if [ -f "$CASE_DIR/manifest.json" ]; then
        echo -e "${GREEN}Case ID:${NC} ACT-2026-00789"
        VERDICT=$(jq -r '.verdict' "$CASE_DIR/manifest.json")
        INHERENT=$(jq -r '.score.inherent_score' "$CASE_DIR/manifest.json")
        MITIGATION=$(jq -r '.score.mitigation_sum' "$CASE_DIR/manifest.json")
        RESIDUAL=$(jq -r '.score.residual_score' "$CASE_DIR/manifest.json")
        SIGNALS=$(jq -r '.signals_fired' "$CASE_DIR/manifest.json")
        MITIGATIONS=$(jq -r '.mitigations_applied' "$CASE_DIR/manifest.json")

        echo -e "${RED}Verdict: $VERDICT${NC}"
        echo "Inherent Score:    $INHERENT"
        echo "Mitigations:       $MITIGATION"
        echo "Residual Score:    $RESIDUAL"
        echo "Signals Fired:     $SIGNALS"
        echo "Mitigations Applied: $MITIGATIONS"
        echo "Exit Code: $EXIT_CODE"
    fi

    echo ""
    echo -e "${BLUE}Step 4: Verify bundle integrity${NC}"
    "$ROOT_DIR/dg" verify-bundle --bundle "$CASE_DIR/bundle.zip"
    echo ""
}

# Function to run Generic CSV demo
run_csv_demo() {
    echo -e "${YELLOW}>>> Demo 2: Generic CSV Export (Mid-Market Bank)${NC}"
    echo ""
    echo "Source: CSV export converted to JSON"
    echo "Customer: Sarah Johnson (CUST-001)"
    echo "Scenario: Cash structuring with international wire"
    echo ""

    echo -e "${BLUE}Step 1: Map CSV export to CaseBundle${NC}"
    "$ROOT_DIR/dg" map-case \
        --input "$ROOT_DIR/adapters/fincrime/generic_csv/example_input.json" \
        --adapter "$ROOT_DIR/adapters/fincrime/generic_csv/mapping.yaml" \
        --out "$SCRIPT_DIR/output/csv_mapped.json"

    echo ""
    echo -e "${BLUE}Step 2: Run decision engine with Canadian FinCrime rules${NC}"
    set +e
    "$ROOT_DIR/dg" run-case \
        --case "$SCRIPT_DIR/output/csv_mapped.json" \
        --pack "$ROOT_DIR/packs/fincrime_canada.yaml" \
        --out "$SCRIPT_DIR/output/"
    EXIT_CODE=$?
    set -e

    echo ""
    echo -e "${BLUE}Step 3: Display verdict summary${NC}"
    echo ""
    CASE_DIR="$SCRIPT_DIR/output/CSV-2026-001"
    if [ -f "$CASE_DIR/manifest.json" ]; then
        echo -e "${GREEN}Case ID:${NC} CSV-2026-001"
        VERDICT=$(jq -r '.verdict' "$CASE_DIR/manifest.json")
        INHERENT=$(jq -r '.score.inherent_score' "$CASE_DIR/manifest.json")
        MITIGATION=$(jq -r '.score.mitigation_sum' "$CASE_DIR/manifest.json")
        RESIDUAL=$(jq -r '.score.residual_score' "$CASE_DIR/manifest.json")
        SIGNALS=$(jq -r '.signals_fired' "$CASE_DIR/manifest.json")
        MITIGATIONS=$(jq -r '.mitigations_applied' "$CASE_DIR/manifest.json")

        echo -e "${RED}Verdict: $VERDICT${NC}"
        echo "Inherent Score:    $INHERENT"
        echo "Mitigations:       $MITIGATION"
        echo "Residual Score:    $RESIDUAL"
        echo "Signals Fired:     $SIGNALS"
        echo "Mitigations Applied: $MITIGATIONS"
        echo "Exit Code: $EXIT_CODE"
    fi

    echo ""
    echo -e "${BLUE}Step 4: Verify bundle integrity${NC}"
    "$ROOT_DIR/dg" verify-bundle --bundle "$CASE_DIR/bundle.zip"
    echo ""
}

# Create output directory
mkdir -p "$SCRIPT_DIR/output"

# Run demos based on argument
case "$DEMO_TYPE" in
    actimize)
        run_actimize_demo
        ;;
    csv)
        run_csv_demo
        ;;
    both)
        run_actimize_demo
        echo ""
        echo -e "${CYAN}============================================================================${NC}"
        echo ""
        run_csv_demo
        ;;
    *)
        echo "Usage: $0 [actimize|csv|both]"
        exit 1
        ;;
esac

echo -e "${CYAN}"
echo "============================================================================"
echo "  POC Demo Complete"
echo "============================================================================"
echo -e "${NC}"
echo "Output bundles: $SCRIPT_DIR/output/"
echo ""
echo "Key files per case:"
echo "  - manifest.json   : Metadata, scores, provenance"
echo "  - report.txt      : Human-readable report"
echo "  - cells.jsonl     : Complete decision chain"
echo "  - verification.json : Integrity verification"
echo "  - bundle.zip      : Signed bundle for transport"
echo ""
