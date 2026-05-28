# AI Agent Workshop

Experiments with AI-powered automation for GitHub workflows.

## Features

- **PR Explainer Action** — Auto-generates plain-English summary of every pull request using Claude API. Posts sticky comment with summary, key changes, risk areas, and test focus.

## Setup

1. Clone repo:
   ```bash
   git clone https://github.com/Bishuzph/AI_agent_workshop.git
   cd AI_agent_workshop
   ```

2. Add `ANTHROPIC_API_KEY` to GitHub repo secrets:
   - Settings → Secrets and variables → Actions → New repository secret
   - Name: `ANTHROPIC_API_KEY`
   - Value: your key from https://console.anthropic.com

## Usage

Open a pull request. Workflow runs automatically. Bot posts/updates explanation comment on each push.

## Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| `.github/workflows/explain-pr.yml` | PR opened, synchronized, reopened | Generate PR explanation |

## Configuration

Model defaults to `claude-opus-4-7`. Swap to `claude-haiku-4-5-20251001` in workflow for cheaper runs.

Diff truncated at 60KB to fit context window.

## License

MIT
