# Set the Python version

python_version := "3.12"

# Default recipe to display available commands
default:
    @just --list

# Create a virtual environment using uv with specified Python version and set up pre-commit
setup:
    @echo "Creating virtual environment using Python {{ python_version }}..."
    uv venv --python {{ python_version }}
    @echo "Virtual environment created."
    @echo "Installing pre-commit hooks..."
    @just run uv sync
    @just run pre-commit install && pre-commit autoupdate && pre-commit run -a -v
    @echo "Pre-commit hooks installed."
    @echo "To activate the environment, run: just activate"

# Run a command in the virtual environment
run *ARGS:
    @if [ ! -d ".venv" ]; then \
        echo "Virtual environment not found. Creating one..."; \
        uv venv --python {{ python_version }}; \
    fi
    @source .venv/bin/activate && {{ ARGS }}

# Activate the virtual environment
activate:
    #!/usr/bin/env bash
    source .venv/bin/activate
    echo "Virtual environment activated. Run 'deactivate' to exit."
    $SHELL

# Deactivate the virtual environment
deactivate:
    @echo "To deactivate the virtual environment, simply run 'deactivate' in your shell."
    @echo "If you're in a subshell created by 'just activate', type 'exit' to leave it."

# Install project dependencies using uv sync
install:
    @echo "Installing project dependencies..."
    @just run uv sync

# Update project dependencies using uv sync with upgrade
update:
    @echo "Updating project dependencies..."
    @just run uv sync --upgrade

# Start Neo4j via Docker Comose
neo4j:
    docker compose up neo4j
    @echo "Neo4j started on bolt://localhost:7687"

# Stop Neo4j
neo4j-down:
    docker compose down

# Fetch a company from NZBN API and load into Neo4j
fetch company_number:
    @just run nz-companies-office fetch {{ company_number }}

# Load all CSV data into Neo4j via LOAD CSV (pipe script to cypher-shell)
neo4j-import-csv:
    cat scripts/neo4j_load_csv.cypher | docker compose exec -T neo4j cypher-shell -u neo4j -p password

# Drop and reload the full Neo4j graph
load-db *ARGS:
    @just run nz-companies-office load-db {{ ARGS }}

# Run entity resolution pipeline
entity-resolution:
    @just run nz-companies-office er

# Post-load enrichment (share percentages, majority flags)
enrich:
    @just run nz-companies-office enrich

# Set descriptions on Industry ancestor nodes from ANZSIC reference
enrich-industry-descriptions:
    @just run nz-companies-office enrich-industry-descriptions

# Transform LINZ shapefile into a cached CSV
prepare-linz *ARGS:
    @just run nz-companies-office prepare-linz {{ ARGS }}

# Reverse geocode Address nodes using LINZ NZ Addresses
geocode *ARGS:
    @just run nz-companies-office geocode {{ ARGS }}

# Clean up the virtual environment
clean:
    @echo "Removing virtual environment..."
    rm -rf .venv
    @echo "Virtual environment removed."

# Start marimo notebook server pointing at notebooks/
marimo:
    @just run marimo edit notebooks/ --watch

# Start the frontend dev server (Vite) — requires `npm install` in app/ first
ui:
    @echo "Starting Vite dev server on http://localhost:5173 ..."
    @cd app && npx vite

# Build the frontend for production
ui-build:
    @echo "Building frontend..."
    @npm --prefix app run build

# Start the graph visualization
viz: ui

# Export Neo4j data to parquet files for DuckDB-WASM
exp:
    @echo "Exporting Neo4j data to app/public/..."
    @just run python scripts/export_parquet.py
