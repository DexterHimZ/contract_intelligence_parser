# Contract Intelligence Parser - Troubleshooting Guide

This document provides a kind of overview of all issues I encountered during building and configuration of the system, along with their resolutions.

## Table of Contents
1. [Frontend Issues](#frontend-issues)
2. [Backend Issues](#backend-issues)
3. [Database Connectivity Issues](#database-connectivity-issues)
4. [Docker Configuration Issues](#docker-configuration-issues)
5. [Lessons Learned](#lessons-learned)
6. [Quick Reference](#quick-reference)

---

## Frontend Issues

### 1. NPM Package Lock File Missing

#### Problem
```
ERROR: failed to solve: process "/bin/sh -c npm ci" did not complete successfully: exit code: 1
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /app/package-lock.json
npm ERR! errno -2
npm ERR! enoent Could not read package-lock.json: Error: ENOENT: no such file or directory
```

#### Analysis
The frontend Dockerfile used `npm ci` which requires a `package-lock.json` file for deterministic dependency installation. The project only had `package.json` without the lock file, causing the build to fail.

#### Resolution
Changed the Dockerfile to use `npm install` instead of `npm ci`:

```dockerfile
# Before (frontend/Dockerfile)
RUN npm ci

# After
RUN npm install
```

#### Verification
- Rebuilt the Docker image: `docker-compose build frontend`
- Container started successfully with all dependencies installed

---

### 2. TypeScript Errors in React Components

#### Problem
Multiple TypeScript errors in Next.js components:
- Missing return statements in components
- Incorrect import paths
- Type mismatches in API responses

#### Analysis
The initial component implementations had several TypeScript strictness issues that prevented successful compilation.

#### Resolution
Fixed multiple component files:

**frontend/src/app/page.tsx:**
```typescript
// Added proper return statement
export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
      {/* Component content */}
    </div>
  );
}
```

**frontend/src/app/contracts/[id]/page.tsx:**
```typescript
// Fixed async component and params handling
export default async function ContractDetailPage({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = await params;
  // Component implementation
}
```

#### Verification
- Run `npm run build` in frontend directory
- All TypeScript errors resolved
- Application builds successfully

---

## Backend Issues

### 1. Debian Package Compatibility Issue

#### Problem
```
E: Unable to locate package libgl1-mesa-glx
ERROR: failed to solve: process "/bin/sh -c apt-get update && apt-get install -y libmagic1 poppler-utils tesseract-ocr libgl1-mesa-glx libglib2.0-0"
```

#### Analysis
The backend Dockerfile was based on `python:3.11-slim` which uses Debian 13 (Trixie). The package `libgl1-mesa-glx` has been replaced with `libgl1` in newer Debian versions.

#### Resolution
Updated the package name in the Dockerfile:

```dockerfile
# Before (backend/Dockerfile)
RUN apt-get update && apt-get install -y \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx \  # Old package name
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# After
RUN apt-get update && apt-get install -y \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    libgl1 \  # New package name for Debian 13
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
```

#### Verification
- Docker image builds successfully
- OpenCV and related libraries load correctly in the container

---

### 2. Motor/PyMongo Version Incompatibility

#### Problem
```
ImportError: cannot import name 'create_document_if_not_exists' from 'beanie'
AttributeError: module 'pymongo' has no attribute 'timeout'
```

#### Analysis
The initial `requirements.txt` had version conflicts:
- Motor 3.7.0 was incompatible with PyMongo 4.10.1
- Beanie 1.28.0 required specific versions of Motor
- The `pymongo.timeout` attribute was introduced in PyMongo 4.2+ but Motor 3.7.0 expected an older API

#### Resolution
Updated the requirements.txt with compatible versions:

```txt
# Before (backend/requirements.txt)
motor==3.7.0
pymongo==4.10.1
beanie==1.28.0

# After
motor==3.6.0
pymongo==4.10.1
beanie==1.27.0
```

#### Alternative Resolution (Also Tested)
```txt
# Another working combination
motor==3.5.1
pymongo==4.8.0
beanie==1.26.0
```

#### Verification
- Ran `pip install -r requirements.txt` successfully
- Database connection established without import errors
- Beanie document models initialized correctly

---

### 3. Missing Python Dependencies

#### Problem
Initial requirements.txt was missing several critical packages needed for the extraction pipeline.

#### Analysis
The extraction pipeline required additional packages for:
- PDF text extraction (PyMuPDF)
- Image processing (opencv-python-headless)
- API client functionality (httpx)
- File type detection (python-magic)

#### Resolution
Added missing dependencies to requirements.txt:

```txt
# Added packages
pymupdf==1.24.14
opencv-python-headless==4.10.0.84
pillow==11.0.0
pytesseract==0.3.13
python-magic==0.4.27
httpx==0.28.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

#### Verification
- All imports work correctly in the application
- PDF processing pipeline functions as expected
- OCR fallback operates when needed

---

## Database Connectivity Issues

### 1. MongoDB Connection Configuration

#### Problem
The backend couldn't connect to MongoDB due to incorrect connection string format.

#### Analysis
The connection string needed proper formatting for Docker networking between containers.

#### Resolution
Updated the .env configuration:

```env
# .env file
MONGODB_URI=mongodb://mongodb:27017/contract_intelligence
```

And ensured docker-compose.yml used correct service names:

```yaml
services:
  backend:
    environment:
      - MONGODB_URI=mongodb://mongodb:27017/contract_intelligence
    depends_on:
      - mongodb
```

#### Verification
- Database connection established on startup
- Health check endpoint returns healthy status
- Document operations work correctly

---

## Docker Configuration Issues

### 1. Docker Compose Service Dependencies

#### Problem
Services starting in wrong order causing connection failures.

#### Analysis
The backend service was attempting to connect to MongoDB before it was ready.

#### Resolution
Added proper health checks and dependencies:

```yaml
# docker-compose.yml
services:
  mongodb:
    image: mongo:7.0
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    depends_on:
      mongodb:
        condition: service_healthy
```

#### Verification
- Services start in correct order
- No connection timeouts during startup
- System becomes fully operational without manual intervention

---

### 2. Volume Mounting Issues

#### Problem
Uploaded files weren't persisting between container restarts.

#### Analysis
The upload directory wasn't properly mounted as a Docker volume.

#### Resolution
Added volume configuration to docker-compose.yml:

```yaml
services:
  backend:
    volumes:
      - ./backend:/app
      - uploads:/app/uploads
      - ./backend/.env:/app/.env

volumes:
  uploads:
  mongodb_data:
```

#### Verification
- Files persist after container restart
- Database data maintained between sessions
- Development hot-reload works with mounted source code

---

## Quick Reference

### Common Commands for Troubleshooting

```bash
# Rebuild everything from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up

# Check container logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f mongodb

# Enter container for debugging
docker-compose exec backend bash
docker-compose exec frontend sh

# Test MongoDB connection
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Clear Docker cache
docker system prune -a --volumes

# Check Python package versions in container
docker-compose exec backend pip list | grep -E "motor|pymongo|beanie"

# Verify file permissions
docker-compose exec backend ls -la /app/uploads
```

### Version Compatibility Matrix

| Component | Working Version | Notes |
|-----------|----------------|-------|
| Python | 3.11-slim | Debian 13 (Trixie) based |
| Node.js | 20-alpine | For frontend |
| MongoDB | 7.0 | Latest stable |
| Motor | 3.6.0 | Compatible with PyMongo 4.10.1 |
| PyMongo | 4.10.1 | Required by Beanie |
| Beanie | 1.27.0 | ODM for MongoDB |
| FastAPI | 0.115.6 | Latest stable |
| Next.js | 15.1.3 | Latest with App Router |

### Environment Variables Checklist

```env
# Backend (.env)
MONGODB_URI=mongodb://mongodb:27017/contract_intelligence
JWT_SECRET=your-secret-key-change-in-production
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE=20971520
CORS_ORIGINS=["http://localhost:3000"]

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Conclusion

This troubleshooting guide documents the journey from initial setup issues to a fully functional Contract Intelligence Parser system. The main challenges centered around:

1. **Dependency compatibility** - Particularly Motor/PyMongo versions
2. **Docker image compatibility** - Package naming in different Debian versions
3. **Build configuration** - Missing lock files and TypeScript strictness
4. **Service orchestration** - Proper startup order and health checks

*Document last updated/ timestamp for record debugging: 2025-09-26 XD 5.12am*