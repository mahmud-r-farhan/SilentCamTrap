# =============================================================================
# SilentCamTrap Server - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production image
# Author: Mahmud Rahman (https://github.com/mahmud-r-farhan)
# =============================================================================

# Stage 1: Build dependencies
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies for building)
RUN npm ci --only=production

# Stage 2: Production image
FROM node:20-alpine AS production

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodeuser -u 1001

# Set working directory
WORKDIR /app

# Copy built node_modules from builder stage
COPY --from=builder /app/node_modules ./node_modules

# Copy application source code
COPY --chown=nodeuser:nodejs src/ ./src/
COPY --chown=nodeuser:nodejs package*.json ./

# Create data directories with proper permissions
RUN mkdir -p /app/data/uploads /app/data/logs && \
    chown -R nodeuser:nodejs /app/data

# Set environment variables
ENV NODE_ENV=production \
    PORT=3000 \
    UPLOAD_DIR=/app/data/uploads \
    LOGS_DIR=/app/data/logs

# Expose the application port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

# Switch to non-root user
USER nodeuser

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Start the application
CMD ["node", "src/server.js"]
