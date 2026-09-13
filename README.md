# Hermes Social Engagement Agent
# Production pipeline for stockscribe.in autonomous acquisition

## Quick Start

```bash
# Initialize and run in dry-run mode (default)
cp .env.example .env
# Edit .env with your preferences
python -m hermes_social

# Run the CLI
python -m hermes_social --cli
```

## Architecture

- **Discovery Engine**: Searches platforms for investing/trading content
- **Relevance Engine**: Scores content for StockScribe fit
- **Comment Generator**: Creates contextual comments
- **Quality Checker**: Evaluates comments before publishing
- **Queue System**: Manages comment lifecycle
- **Tracking**: UTM-based conversion tracking
- **Learning Engine**: Optimizes strategy based on outcomes

## Configuration

All settings are in `.env` (see `.env.example`). Key settings:

- `DRY_RUN=true` - Default, prevents actual publishing
- `APPROVAL_REQUIRED=true` - Requires manual approval
- `AUTONOMOUS_POSTING_ENABLED=false` - Enable for auto-publishing

## Database

Uses SQLite by default (file: `data/state.db`). PostgreSQL can be configured
via `DATABASE_URL=postgresql://...`.

## Platforms

- YouTube (implemented, search requires API key)
- Instagram (placeholder)
- X/Twitter (placeholder)
- Reddit (placeholder)
- LinkedIn (placeholder)

## Safety Features

- Per-platform rate limits
- Per-creator cooldowns
- Duplicate detection
- Quality scoring
- Kill switches
- Approval mode