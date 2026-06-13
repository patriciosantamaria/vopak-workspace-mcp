# =============================================================================
# Vopak Workspace MCP Server — Multi-stage Docker Build
# Produces a ~22MB Alpine image with a single static Go binary.
# =============================================================================

# Stage 1: Build
FROM golang:1.25-alpine AS builder
WORKDIR /build

# Copy module files and resolve dependencies
COPY go.mod ./
RUN go mod download 2>/dev/null || true

# Copy source and resolve + build
COPY . .
RUN go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

# Stage 2: Runtime
FROM alpine:3.21
RUN apk --no-cache add ca-certificates

COPY --from=builder /server /app/server

# The container stays alive; Antigravity calls tools via `docker exec`
ENTRYPOINT ["sleep", "infinity"]
