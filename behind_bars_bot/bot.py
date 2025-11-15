"""Main bot entry point for Behind Bars Discord bot."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from accuralai_discord import DiscordBot, DiscordBotConfig

from .context7_tool import get_context7_search
from .github_readme_tool import get_github_readme_fetcher
from .knowledge_base import KnowledgeBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger("behind_bars_bot")

# Load environment variables from .env file
# Look for .env in the package directory or current working directory
_env_paths = [
    Path(__file__).parent.parent / ".env",  # Package directory
    Path.cwd() / ".env",  # Current working directory
]

for env_path in _env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=False)  # Don't override existing env vars
        LOGGER.info(f"Loaded environment variables from: {env_path}")
        break
else:
    LOGGER.debug("No .env file found, using environment variables only")


def get_knowledge_path() -> Path:
    """Get path to knowledge directory."""
    # Try prefixed environment variable first (for multi-bot deployments)
    env_path = os.getenv("BEHIND_BARS_KNOWLEDGE_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    # Default to package knowledge directory
    package_dir = Path(__file__).parent.parent
    return package_dir / "knowledge"


def setup_behind_bars_tools(bot: DiscordBot, knowledge_base: KnowledgeBase) -> None:
    """Register Behind Bars specific tools with the bot."""
    if not bot._config.enable_tool_calling:
        LOGGER.warning("Tool calling is disabled. Enable it to use knowledge search.")
        return

    context7_search = get_context7_search()
    github_readme_fetcher = get_github_readme_fetcher()

    # GitHub README search tool (with RAG)
    async def search_github_readme_handler(query: str = "", use_cache: bool = True, context: dict = None) -> str:
        """
        Search the latest Behind Bars README from GitHub using semantic search.
        
        If no query is provided, returns a summary. Otherwise performs semantic search.
        """
        try:
            if not query or len(query.strip()) < 2:
                # If no query, fetch and return a summary/overview
                readme_content = await github_readme_fetcher.fetch_readme(use_cache=use_cache)
                if readme_content:
                    # Return first portion as overview
                    overview = readme_content[:2000]
                    return f"{overview}\n\n... (Use a specific query to search the full README)"
                return "Error: Could not fetch README from GitHub."
            
            # Perform semantic search
            results = await github_readme_fetcher.search(query, max_results=5)
            
            if not results:
                return f"No relevant information found in the README for: {query}"
            
            # Format results - combine relevant chunks
            content_parts = []
            for result in results:
                snippet = result.get("snippet", result.get("full_content", ""))
                if snippet:
                    snippet = snippet.strip()
                    if snippet:
                        content_parts.append(snippet)
            
            if content_parts:
                # Combine all relevant content
                combined = "\n\n".join(content_parts)
                # Limit to reasonable length
                if len(combined) > 5000:
                    combined = combined[:5000] + "\n\n... (more results available)"
                return combined
            
            return f"No relevant information found in the README for: {query}"
            
        except Exception as e:
            LOGGER.error(f"Error searching GitHub README: {e}", exc_info=True)
            return f"Error searching GitHub README: {str(e)}"

    # Local knowledge base search tool
    async def search_knowledge_handler(query: str, context: dict) -> str:
        """Search local knowledge base for Behind Bars information."""
        if not query or len(query.strip()) < 2:
            return "Error: Search query must be at least 2 characters."

        try:
            results = await knowledge_base.search(query, max_results=5)

            if not results:
                # Try Context7 as fallback
                LOGGER.debug("No local results, trying Context7...")
                context7_results = await context7_search.search(
                    query=query,
                    topic=query,  # Use query as topic
                    tokens=10000,
                    max_results=5,
                    use_cache=True,
                )
                if context7_results:
                    # Format Context7 results
                    content_parts = []
                    for result in context7_results:
                        snippet = result.get("snippet", result.get("full_content", ""))
                        if snippet:
                            snippet = snippet.strip()
                            if snippet:
                                content_parts.append(snippet)
                    if content_parts:
                        combined = "\n\n".join(content_parts)
                        if len(combined) > 3000:
                            combined = combined[:3000] + "..."
                        return combined
                return "No relevant information found."

            # Format results - return content only, no document names
            # Combine relevant snippets into a natural response
            content_parts = []
            
            for result in results:
                snippet = result.get("snippet", result.get("full_content", ""))
                if snippet:
                    # Clean up the snippet
                    snippet = snippet.strip()
                    if snippet:
                        content_parts.append(snippet)
            
            if content_parts:
                # Combine all relevant content, limiting total length
                combined = "\n\n".join(content_parts)
                # Limit to reasonable length for the LLM context
                if len(combined) > 3000:
                    combined = combined[:3000] + "..."
                return combined
            
            return "No relevant information found."

        except Exception as e:
            LOGGER.error(f"Error searching knowledge base: {e}", exc_info=True)
            return f"Error searching knowledge base: {str(e)}"

    # Context7 search tool (with RAG and topic support)
    async def search_context7_handler(
        query: str,
        topic: str = "",
        tokens: int = 10000,
        context: dict = None
    ) -> str:
        """
        Search Context7 for Behind Bars documentation using semantic search.
        
        Uses the topic parameter to fetch relevant content from Context7, then
        performs RAG-based semantic search through that content.
        """
        if not query or len(query.strip()) < 2:
            return "Error: Search query must be at least 2 characters."

        try:
            # Use query as topic if no topic provided, or use provided topic
            search_topic = topic.strip() if topic else query
            
            # Perform semantic search with RAG
            results = await context7_search.search(
                query=query,
                topic=search_topic if search_topic else None,
                tokens=tokens,
                max_results=5,
                use_cache=True,
            )
            
            if not results:
                return f"No relevant information found in Context7 documentation for: {query}"
            
            # Format results - combine relevant chunks
            content_parts = []
            for result in results:
                snippet = result.get("snippet", result.get("full_content", ""))
                if snippet:
                    snippet = snippet.strip()
                    if snippet:
                        content_parts.append(snippet)
            
            if content_parts:
                # Combine all relevant content
                combined = "\n\n".join(content_parts)
                # Limit to reasonable length
                if len(combined) > 5000:
                    combined = combined[:5000] + "\n\n... (more results available)"
                return combined
            
            return f"No relevant information found in Context7 documentation for: {query}"
            
        except Exception as e:
            LOGGER.error(f"Error searching Context7: {e}", exc_info=True)
            return f"Error searching Context7: {str(e)}"

    # Register tools
    bot.add_tool(
        name="search_behind_bars_knowledge",
        description=(
            "Search the Behind Bars mod knowledge base for information about "
            "jail system, bail, parole, crime tracking, UI guides, and FAQs. "
            "Use this to answer questions about how the mod works in-game. "
            "Focus on user-facing features and gameplay mechanics, not source code."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query about Behind Bars mod features, gameplay, or mechanics",
                }
            },
            "required": ["query"],
        },
        handler=search_knowledge_handler,
    )

    bot.add_tool(
        name="search_behind_bars_context7",
        description=(
            "Search Context7 documentation for Behind Bars mod using semantic search with RAG. "
            "This tool uses the topic parameter to fetch relevant content from Context7, then "
            "performs semantic search through that content. Use this as a fallback when local "
            "knowledge base doesn't have the answer. The topic parameter helps Context7 fetch "
            "more relevant documentation sections."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query about Behind Bars mod for semantic search",
                },
                "topic": {
                    "type": "string",
                    "description": "Optional topic to fetch from Context7 (e.g., 'How do you get out of jail'). If not provided, uses the query as topic.",
                },
                "tokens": {
                    "type": "integer",
                    "description": "Maximum tokens to retrieve from Context7 (default: 10000)",
                    "default": 10000,
                }
            },
            "required": ["query"],
        },
        handler=search_context7_handler,
    )

    bot.add_tool(
        name="search_github_readme",
        description=(
            "Search the latest Behind Bars mod README from GitHub using semantic search. "
            "This tool uses RAG (Retrieval Augmented Generation) to find relevant sections "
            "from the README based on your query. Use this to get up-to-date information about "
            "features, installation, usage, and development details. "
            "If no query is provided, returns an overview of the README."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query about Behind Bars mod features, installation, usage, etc. Leave empty for overview.",
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to use cached README if available (default: true)",
                    "default": True,
                }
            },
            "required": [],
        },
        handler=search_github_readme_handler,
    )

    LOGGER.info("Registered Behind Bars search tools")


def setup_custom_commands(bot: DiscordBot) -> None:
    """Register custom slash commands and mention handling for Behind Bars bot."""
    import discord
    from discord import app_commands
    import re

    # Add mention-only filter: bot only responds when mentioned
    @bot.on_message_preprocess
    async def mention_only_filter(message: discord.Message, context: dict) -> str | None:
        """
        Only process messages where the bot is mentioned.
        Returns message content if bot is mentioned, None otherwise.
        """
        # Get bot user ID from the message's client (more reliable than bot._client)
        bot_user = message.guild.me if message.guild else None
        if not bot_user:
            # Fallback: try to get from bot's client
            if bot._client and bot._client.user:
                bot_user = bot._client.user
            else:
                # If bot isn't ready yet, allow the message through
                # (it will be filtered by other checks)
                return message.content
        
        bot_user_id = bot_user.id
        
        # Check if bot is mentioned in the message
        bot_mentioned = False
        if message.mentions:
            # Check if bot is in the mentions list
            bot_mentioned = any(user.id == bot_user_id for user in message.mentions)
        
        # Also check message content for mention pattern (in case mentions aren't parsed)
        if not bot_mentioned and message.content:
            mention_pattern = r"<@!?(\d+)>"
            mentioned_user_ids = re.findall(mention_pattern, message.content)
            bot_mentioned = str(bot_user_id) in mentioned_user_ids
        
        # Only process if bot is mentioned
        if not bot_mentioned:
            return None  # Filter out this message
        
        # Remove the mention from content so the AI doesn't see it
        content = message.content or ""
        # Remove bot mention patterns
        content = re.sub(rf"<@!?{bot_user_id}>", "", content).strip()
        # Clean up extra whitespace
        content = re.sub(r"\s+", " ", content).strip()
        
        return content if content else None

    # Register /features slash command
    @app_commands.command(name="features", description="List main features of the Behind Bars mod")
    async def features_slash(interaction: discord.Interaction) -> None:
        """Handle /features slash command."""
        response = (
            "**Behind Bars Mod Features:**\n\n"
            "🚔 **Jail System** - Complete jail experience with cells, booking, and facilities\n"
            "💰 **Bail System** - Pay bail to get out of jail early\n"
            "🔄 **Parole System** - Post-release supervision with LSI risk assessment\n"
            "🕵️ **Crime Tracking** - Comprehensive criminal records and rap sheets\n"
            "👮 **NPC System** - Guards, parole officers, and inmates\n"
            "🖥️ **User Interface** - UIs for jail info, bail, parole status, and more\n\n"
            "Ask me about any feature for more details!"
        )
        await interaction.response.send_message(response)
    
    bot.add_slash_command("features", "List main features of the Behind Bars mod", features_slash)

    # Register /guide slash command
    @app_commands.command(name="guide", description="Get links to Behind Bars guides")
    async def guide_slash(interaction: discord.Interaction) -> None:
        """Handle /guide slash command."""
        response = (
            "**Behind Bars Guides:**\n\n"
            "📖 **Jail System** - Ask: \"How does the jail system work?\"\n"
            "💰 **Bail** - Ask: \"How do I pay bail?\"\n"
            "🔄 **Parole** - Ask: \"What is parole?\"\n"
            "🕵️ **Crime Tracking** - Ask: \"How does crime tracking work?\"\n"
            "🖥️ **UI Guide** - Ask: \"What UIs are available?\"\n"
            "❓ **FAQ** - Ask: \"What are common questions?\"\n\n"
            "Just ask me any question about the mod!"
        )
        await interaction.response.send_message(response)
    
    bot.add_slash_command("guide", "Get links to Behind Bars guides", guide_slash)

    LOGGER.info("Registered custom slash commands")


def create_bot_config() -> DiscordBotConfig:
    """Create bot configuration from environment variables."""
    # Required: Bot token (prefixed with BEHIND_BARS_ to avoid conflicts)
    token = os.getenv("BEHIND_BARS_DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        LOGGER.error("BEHIND_BARS_DISCORD_TOKEN environment variable is required")
        sys.exit(1)
    token = token.strip('"').strip("'")

    # Optional: AccuralAI config path (prefixed)
    accuralai_config = os.getenv("BEHIND_BARS_CONFIG_PATH") or os.getenv("ACCURALAI_CONFIG_PATH")
    if accuralai_config:
        accuralai_config = accuralai_config.strip('"').strip("'")
        accuralai_config = os.path.expanduser(accuralai_config)
        if not os.path.isabs(accuralai_config):
            accuralai_config = os.path.abspath(accuralai_config)

    # Personality focused on Behind Bars mod
    personality = (
        "You are Behind Bars Bot, a helpful assistant knowledgeable about the Behind Bars mod for Schedule I. "
        "You help players understand how to use the mod's features in-game, including jail time, "
        "bail, parole, and crime tracking systems. "
        "Focus on in-game usage and gameplay mechanics, not source code or technical implementation. "
        "Answer questions about how the mod works, how to use features, and provide step-by-step guides. "
        "Use the search_behind_bars_knowledge tool to find relevant information when answering questions. "
        "If local knowledge doesn't have the answer, try search_behind_bars_context7 as a fallback. "
        "For the most up-to-date information about features, installation, or development details, "
        "use search_github_readme with a specific query to search the latest README from GitHub using semantic search. "
        "When you use search tools, the results contain relevant information - use this information naturally "
        "to answer the user's question. Do NOT mention document names, file paths, or internal knowledge base "
        "structure. Just answer the question using the information you found, as if you naturally know it. "
        "Always provide clear, user-friendly answers focused on what players need to know to use the mod."
    )

    # Parse guild IDs for command syncing (comma-separated)
    sync_guild_ids: list[int] = []
    guild_ids_str = os.getenv("BEHIND_BARS_SYNC_GUILDS", os.getenv("DISCORD_SYNC_GUILDS", ""))
    if guild_ids_str:
        try:
            sync_guild_ids = [int(gid.strip()) for gid in guild_ids_str.split(",") if gid.strip()]
        except ValueError:
            LOGGER.warning(f"Invalid guild IDs format: {guild_ids_str}. Expected comma-separated integers.")

    config = DiscordBotConfig(
        token=token,
        personality=personality,
        conversation_scope=os.getenv("BEHIND_BARS_SCOPE", os.getenv("DISCORD_BOT_SCOPE", "per-channel")),
        accuralai_config_path=accuralai_config,
        enable_tool_calling=True,
        enable_multimodal=False,  # Not needed for this bot
        use_embeds=False,
        enable_analytics=True,
        smart_history=False,
        context_aware=True,
        enable_slash_commands=True,  # Enable slash commands
        auto_sync_slash_commands=True,  # Auto-sync on startup
        sync_guild_commands=sync_guild_ids if sync_guild_ids else None,  # Sync to specific guilds if provided
        debug=os.getenv("BEHIND_BARS_DEBUG", os.getenv("DISCORD_DEBUG", "false")).lower() == "true",
    )

    return config


async def initialize_knowledge_base() -> KnowledgeBase:
    """Initialize knowledge base asynchronously."""
    knowledge_path = get_knowledge_path()
    LOGGER.info(f"Loading knowledge base from: {knowledge_path}")

    # Configure knowledge base with optimized settings
    # Use larger chunks to reduce total number (128 -> ~40-50 chunks)
    # accuralai-rag handles embeddings locally, avoiding remote quotas
    
    # Check if embeddings are disabled via environment variable
    disable_embeddings = os.getenv("BEHIND_BARS_DISABLE_EMBEDDINGS", "false").lower() == "true"
    
    knowledge_base = KnowledgeBase(
        knowledge_path=knowledge_path,
        use_embeddings=not disable_embeddings,
        chunk_size=2000,  # Larger chunks = fewer total chunks (reduces from 128 to ~40-50)
        chunk_overlap=300,
    )
    await knowledge_base.initialize()
    return knowledge_base


def main() -> None:
    """Main entry point for the bot (synchronous)."""
    LOGGER.info("Starting Behind Bars Discord Bot...")

    # Create bot configuration
    config = create_bot_config()

    # Initialize knowledge base in a separate event loop
    # (bot.run() will create its own event loop)
    try:
        knowledge_base = asyncio.run(initialize_knowledge_base())
    except Exception as e:
        LOGGER.error(f"Failed to initialize knowledge base: {e}", exc_info=True)
        sys.exit(1)

    # Create bot
    bot = DiscordBot(config=config)

    # Setup tools
    setup_behind_bars_tools(bot, knowledge_base)

    # Setup custom commands
    setup_custom_commands(bot)

    # Run bot (this creates its own event loop)
    LOGGER.info("Bot initialized. Starting...")
    try:
        bot.run()
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped by user")
    except Exception as e:
        LOGGER.error(f"Bot error: {e}", exc_info=True)
        sys.exit(1)


def main_sync() -> None:
    """Synchronous entry point (alias for main)."""
    main()


if __name__ == "__main__":
    main_sync()

