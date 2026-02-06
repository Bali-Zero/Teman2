# 🏗️ Nuzantara Workspace Configuration

## Workspace Structure

| Package | Path | Type | Version |
|---------|------|------|---------|
| `nuzantara` | `/` | Root | 5.2.0 |
| `mouth` | `apps/mouth` | Next.js 16 Frontend | 5.2.0 |
| `backend-rag` | `apps/backend-rag` | Python FastAPI | 5.2.0 |
| `webapp` | `apps/webapp` | Next.js App | 5.2.0 |
| `admin-dashboard` | `apps/admin-dashboard` | Admin Panel | 5.2.0 |
| `zantara-media` | `apps/zantara-media/dashboard` | Media Dashboard | 5.2.0 |

## Unified Commands

```bash
# Development
npm run dev:mouth         # Start mouth dev server
npm run dev:backend       # Start Python backend

# Building
npm run build:all         # Build all workspaces

# Testing
npm run test              # Run all tests
npm run test:coverage     # Run with coverage

# Code Quality
npm run format            # Format all code
npm run typecheck         # Type-check all
npm run lint:all          # Lint all workspaces

# Security
npm run security:audit    # Audit dependencies
npm run security:fix      # Fix security issues

# Workspace Management
npm run workspace:clean   # Clean all node_modules
npm run workspace:reset   # Clean + reinstall
```

## TypeScript Project References

```
root tsconfig.json
├── apps/mouth/tsconfig.json
├── apps/webapp/tsconfig.json
├── apps/admin-dashboard/tsconfig.json
└── apps/zantara-media/dashboard/tsconfig.json
```

## Dependency Strategy

- **Root**: Shared dev tools (TypeScript, Prettier, Husky)
- **Workspaces**: Framework-specific dependencies
- **No duplicates**: React/Tailwind only in `mouth`

## Version Alignment

All packages aligned to **v5.2.0** for consistency.
