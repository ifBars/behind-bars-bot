# Behind Bars Discord Bot

A helpful Discord bot that answers questions about the Behind Bars mod for Schedule I. The bot uses AccuralAI to provide intelligent answers about jail systems, bail, parole, crime tracking, and more.

## Features

- **Knowledge Base Search**: Searches curated documentation about Behind Bars mod features
- **Context7 Integration**: Falls back to Context7 documentation when needed
- **Natural Language Queries**: Ask questions in plain English
- **Custom Commands**: `/behindbars`, `/features`, `/guide` commands
- **Focus on Gameplay**: Answers focus on in-game usage, not source code

## Installation

### Prerequisites

- Python 3.10 or higher
- Discord bot token
- AccuralAI backend configured (Ollama or Google Gemini)

### Setup

1. **Install the package**:
```bash
pip install -e .
```

2. **Configure environment variables**:

   **Option A: Using .env file (Recommended)**
   ```bash
   cp .templateenv .env
   # Edit .env and fill in your values
   ```

   **Option B: Using environment variables**
   ```bash
   export BEHIND_BARS_DISCORD_TOKEN="your_discord_bot_token"
   export BEHIND_BARS_CONFIG_PATH="config.toml"  # Optional, defaults to config.toml
   export BEHIND_BARS_KNOWLEDGE_PATH="knowledge"  # Optional, defaults to package knowledge/
   export GOOGLE_GENAI_API_KEY="your_api_key"  # Required if using Google Gemini backend
   ```

3. **Configure AccuralAI backend**:
   - Edit `config.toml` to configure your backend (Ollama or Google Gemini)
   - For Google Gemini, set `GOOGLE_GENAI_API_KEY` environment variable
   - For Ollama, ensure Ollama is running locally

4. **Run the bot**:
```bash
behind-bars-bot
```

Or:
```bash
python -m behind_bars_bot.bot
```

## Configuration

### Environment Variables

All environment variables are prefixed with `BEHIND_BARS_` to avoid conflicts when running multiple Discord bots on the same server.

**Configuration Methods:**
1. **`.env` file (Recommended)**: Copy `.templateenv` to `.env` and fill in your values
2. **Environment variables**: Set variables in your shell or systemd service

**Required:**
- `BEHIND_BARS_DISCORD_TOKEN`: Your Discord bot token

**Optional:**
- `BEHIND_BARS_CONFIG_PATH`: Path to AccuralAI config file (defaults to `config.toml` in package directory)
- `BEHIND_BARS_KNOWLEDGE_PATH`: Path to knowledge directory (defaults to `knowledge/` in package directory)
- `BEHIND_BARS_SCOPE`: Conversation scope (`per-channel`, `per-user`, `per-thread`, `per-channel-user`, default: `per-channel`)
- `BEHIND_BARS_SYNC_GUILDS`: Guild IDs for slash command syncing (comma-separated, e.g., `123456789012345678,987654321098765432`). Guild commands sync instantly; global commands can take up to 1 hour.
- `BEHIND_BARS_DEBUG`: Enable debug logging (`true`/`false`, default: `false`)
- `BEHIND_BARS_DISABLE_EMBEDDINGS`: Disable the accuralai-rag semantic index and fall back to keyword search (`true`/`false`, default: `false`)

**Backend Configuration:**
- `GOOGLE_GENAI_API_KEY`: For the Google Gemini backend (can also be set in config.toml)

**Legacy Support:**
For backward compatibility, the bot also checks these unprefixed variables (not recommended for multi-bot deployments):
- `DISCORD_BOT_TOKEN` (fallback if `BEHIND_BARS_DISCORD_TOKEN` not set)
- `ACCURALAI_CONFIG_PATH` (fallback if `BEHIND_BARS_CONFIG_PATH` not set)
- `DISCORD_BOT_SCOPE` (fallback if `BEHIND_BARS_SCOPE` not set)
- `DISCORD_DEBUG` (fallback if `BEHIND_BARS_DEBUG` not set)

### AccuralAI Config

Edit `config.toml` to configure:
- Backend (Ollama or Google Gemini)
- Cache settings
- Other AccuralAI options

## Usage

### Commands

- `/behindbars <question>` - Ask a question about the mod
- `/features` - List main mod features
- `/guide` - Get links to guides

### Natural Language

Just ask questions in chat! The bot will automatically search the knowledge base and answer.

Examples:
- "How do I get out of jail?"
- "What is parole?"
- "How does bail work?"
- "What are LSI levels?"

## Knowledge Base

The bot uses multiple focused knowledge documents:
- `jail_system.md` - Jail mechanics and arrest process
- `bail_system.md` - Bail calculation and payment
- `parole_system.md` - Parole mechanics and LSI levels
- `crime_tracking.md` - Crime detection and rap sheets
- `ui_guide.md` - User interface elements
- `faq.md` - Common questions and troubleshooting

## Context7 Integration

The bot can also search Context7 documentation for Behind Bars (`/sirtidez/behind-bars`) as a fallback when local knowledge doesn't have the answer. This requires MCP server configuration.

## Development

### Project Structure

```
behind-bars-bot/
├── pyproject.toml
├── README.md
├── config.toml
├── behind_bars_bot/
│   ├── __init__.py
│   ├── bot.py              # Main bot entry point
│   ├── knowledge_base.py   # Local knowledge base using accuralai-rag
│   └── context7_tool.py    # Context7 MCP integration
├── knowledge/              # Knowledge documents
│   ├── jail_system.md
│   ├── bail_system.md
│   ├── parole_system.md
│   ├── crime_tracking.md
│   ├── ui_guide.md
│   └── faq.md
└── tests/
    └── test_bot.py
```

### Running Tests

```bash
pytest tests/
```

## License

Apache-2.0

## Support

For issues or questions about the bot, please open an issue on the repository.

