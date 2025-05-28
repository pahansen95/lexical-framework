#!/usr/bin/env bash
# Apply ruff formatting and linting to Python files in the project
# Matches the style guidelines from helpers/apply-style.py

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the project root using git
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
}

# Default targets
DEFAULT_TARGETS=("src" "tests" "helpers")

# Parse command line arguments
if [ $# -eq 0 ]; then
    ARGS=("${DEFAULT_TARGETS[@]}")
else
    ARGS=("$@")
fi

echo "Project root: $PROJECT_ROOT"
echo "Processing: ${ARGS[*]}"
echo

# Check if ruff is available
if ! command -v ruff &> /dev/null; then
    echo -e "${RED}Error: ruff is not installed${NC}"
    echo "Install it with: pip install ruff"
    exit 1
fi

# Create a temporary directory for symlinks
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "Creating symlinks in temporary directory..."

# Process arguments - can be mix of files and directories
file_count=0

for arg in "${ARGS[@]}"; do
    # Convert to absolute path if relative
    if [[ "$arg" = /* ]]; then
        path="$arg"
    else
        path="$PROJECT_ROOT/$arg"
    fi
    
    if [ ! -e "$path" ]; then
        echo -e "${YELLOW}Skipping $arg - not found${NC}"
        continue
    fi
    
    if [ -f "$path" ]; then
        # It's a file - add it directly (no filtering)
        # Get relative path from project root
        rel_path="${path#$PROJECT_ROOT/}"
        
        # Create directory structure in temp dir
        link_dir="$TEMP_DIR/$(dirname "$rel_path")"
        mkdir -p "$link_dir"
        
        # Create symlink
        ln -s "$path" "$link_dir/$(basename "$path")"
        file_count=$((file_count + 1))
    elif [ -d "$path" ]; then
        # It's a directory - find Python files
        find "$path" -name "*.py" -type f ! -path "*/.*" -exec sh -c '
            file="$1"
            project_root="$2"
            temp_dir="$3"
            
            # Get relative path from project root
            rel_path="${file#$project_root/}"
            
            # Create directory structure in temp dir
            link_dir="$temp_dir/$(dirname "$rel_path")"
            mkdir -p "$link_dir"
            
            # Create symlink
            ln -s "$file" "$link_dir/$(basename "$file")"
        ' sh {} "$PROJECT_ROOT" "$TEMP_DIR" \;
        
        # Count the files we just linked
        dir_count=$(find "$path" -name "*.py" -type f ! -path "*/.*" | wc -l)
        file_count=$((file_count + dir_count))
    fi
done

if [ $file_count -eq 0 ]; then
    echo -e "${YELLOW}No Python files found in specified targets${NC}"
    exit 0
fi

echo "Found $file_count Python files"
echo

# Run ruff check with --fix on the entire temp directory
echo -e "${GREEN}Checking and fixing all files with ruff...${NC}"
if ruff check --fix --verbose "$TEMP_DIR"; then
    echo "✓ Linting complete"
    lint_success=true
else
    echo -e "${YELLOW}⚠ Some linting issues remain (manual fixes needed)${NC}"
    # Show remaining issues
    echo
    echo "Remaining issues:"
    ruff check "$TEMP_DIR" || true
    lint_success=false
fi

echo

# Run ruff format on the entire temp directory
echo -e "${GREEN}Formatting all files with ruff...${NC}"
if ruff format --verbose "$TEMP_DIR"; then
    echo "✓ Formatting complete"
    format_success=true
else
    echo -e "${RED}✗ Formatting failed${NC}"
    format_success=false
fi

echo
echo "================================"

# Final exit status
if [ "$format_success" = true ] && [ "$lint_success" = true ]; then
    echo -e "${GREEN}✓ PASS: Style enforcement complete!${NC}"
    echo "Successfully processed $file_count files"
    exit 0
elif [ "$format_success" = false ]; then
    echo -e "${RED}✗ ERROR: Formatting failed${NC}"
    echo "Failed to process $file_count files"
    exit 1
else
    echo -e "${YELLOW}⚠ PASS with warnings: Style enforcement complete with remaining lint issues${NC}"
    echo "Processed $file_count files (manual fixes needed for some lint issues)"
    exit 0
fi