# ============================================================
# Stage 1: Build the gws CLI from source (Rust)
# ============================================================
FROM rust:1-bookworm AS gws-builder

RUN apt-get update && apt-get install -y git pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch v0.22.5 https://github.com/googleworkspace/cli.git /build
WORKDIR /build
RUN cargo build --release

# ============================================================
# Stage 2: Runtime — Python + gws binary + MCP servers
# ============================================================
FROM python:3.11-slim-bookworm

# Install gcloud CLI (required by `gws auth setup`)
RUN apt-get update && apt-get install -y curl \
    && curl -sSL https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/opt \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/google-cloud-sdk/bin:${PATH}"

# Copy the compiled gws binary from the builder stage
COPY --from=gws-builder /build/target/release/gws /usr/local/bin/gws
RUN chmod +x /usr/local/bin/gws

# Use file-based keyring for headless Docker operation (no OS keyring available)
ENV GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file

# Create working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python MCP server source
COPY src/ ./src/

# Verify gws is working
RUN gws --version

# Keep container alive as a daemon for MCP stdio exec
CMD ["sleep", "infinity"]
