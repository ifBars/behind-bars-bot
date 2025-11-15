# Deployment Guide for Oracle Cloud VM

This guide covers deploying the Behind Bars Discord bot to an Oracle Cloud VM alongside other Discord bots.

## Environment Variable Isolation

All environment variables are prefixed with `BEHIND_BARS_` to prevent conflicts with other Discord bots running on the same server.

### Configuration Methods

**Option 1: Using .env file (Recommended)**

1. Copy the template:
   ```bash
   cp .templateenv .env
   ```

2. Edit `.env` and fill in your values:
   ```bash
   nano .env
   ```

3. The bot will automatically load variables from `.env` file

**Option 2: Using environment variables**

Set variables directly in your shell or systemd service.

### Required Variables

```bash
BEHIND_BARS_DISCORD_TOKEN=your_discord_bot_token_here
GOOGLE_GENAI_API_KEY=your_google_api_key
```

### Optional Variables

```bash
BEHIND_BARS_CONFIG_PATH=/path/to/config.toml
BEHIND_BARS_KNOWLEDGE_PATH=/path/to/knowledge
BEHIND_BARS_SCOPE=per-channel
BEHIND_BARS_DEBUG=false
```

## Systemd Service Setup

Create a systemd service file for the bot:

### `/etc/systemd/system/behind-bars-bot.service`

**Option A: Using .env file (Recommended)**

```ini
[Unit]
Description=Behind Bars Discord Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/behind-bars-bot
EnvironmentFile=/path/to/behind-bars-bot/.env
ExecStart=/usr/bin/python3 -m behind_bars_bot.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Option B: Using Environment directives**

```ini
[Unit]
Description=Behind Bars Discord Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/behind-bars-bot
Environment="BEHIND_BARS_DISCORD_TOKEN=your_token_here"
Environment="BEHIND_BARS_CONFIG_PATH=/path/to/behind-bars-bot/config.toml"
Environment="GOOGLE_GENAI_API_KEY=your_api_key"
Environment="BEHIND_BARS_SCOPE=per-channel"
Environment="BEHIND_BARS_DEBUG=false"
ExecStart=/usr/bin/python3 -m behind_bars_bot.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Service Management

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable behind-bars-bot

# Start service
sudo systemctl start behind-bars-bot

# Check status
sudo systemctl status behind-bars-bot

# View logs
sudo journalctl -u behind-bars-bot -f
```

## Using .env File in Package Directory

The bot automatically looks for `.env` file in:
1. Package directory (`behind-bars-bot/.env`)
2. Current working directory

Simply create `.env` from the template:

```bash
cd /path/to/behind-bars-bot
cp .templateenv .env
nano .env  # Edit and fill in your values
```

Then use `EnvironmentFile` in systemd to load it:

```ini
[Service]
EnvironmentFile=/path/to/behind-bars-bot/.env
ExecStart=/usr/bin/python3 -m behind_bars_bot.bot
```

**Security Note**: Ensure `.env` file has proper permissions:
```bash
chmod 600 /path/to/behind-bars-bot/.env
chown your_user:your_user /path/to/behind-bars-bot/.env
```

## Multiple Bots on Same Server

When running multiple Discord bots, ensure each uses unique:

1. **Environment Variables**: All prefixed (e.g., `BEHIND_BARS_*`, `OTHER_BOT_*`)
2. **Service Names**: Unique systemd service names
3. **Working Directories**: Separate directories for each bot
4. **Cache Files**: Different cache.db paths in config.toml
5. **Log Files**: Separate log files if using file logging

### Example Multi-Bot Setup

```bash
# Bot 1: Behind Bars Bot
/etc/systemd/system/behind-bars-bot.service
Environment="BEHIND_BARS_DISCORD_TOKEN=token1"
WorkingDirectory=/opt/bots/behind-bars-bot

# Bot 2: Other Bot
/etc/systemd/system/other-bot.service
Environment="OTHER_BOT_DISCORD_TOKEN=token2"
WorkingDirectory=/opt/bots/other-bot
```

## Configuration File

Ensure `config.toml` uses environment variable substitution:

```toml
[backends.google]
plugin_id = "accuralai-google"
options = { api_key = "${GOOGLE_GENAI_API_KEY}", model = "gemini-2.5-flash-lite" }

[cache]
plugin_id = "accuralai-cache-layered"
options = { memory_max_size = 100, disk_path = "/var/lib/behind-bars-bot/cache.db" }
```

## Security Best Practices

1. **File Permissions**: Restrict access to config files and tokens
   ```bash
   chmod 600 /etc/behind-bars-bot/env.conf
   chown your_user:your_user /etc/behind-bars-bot/env.conf
   ```

2. **User Isolation**: Run each bot as a separate user
   ```bash
   sudo useradd -r -s /bin/false behind-bars-bot
   ```

3. **Firewall**: Only allow necessary outbound connections

4. **Logs**: Monitor logs for security issues
   ```bash
   sudo journalctl -u behind-bars-bot --since "1 hour ago"
   ```

## Troubleshooting

### Bot Not Starting

1. Check environment variables:
   ```bash
   sudo systemctl show behind-bars-bot --property=Environment
   ```

2. Check logs:
   ```bash
   sudo journalctl -u behind-bars-bot -n 50
   ```

3. Test manually:
   ```bash
   cd /path/to/behind-bars-bot
   export BEHIND_BARS_DISCORD_TOKEN=your_token
   python3 -m behind_bars_bot.bot
   ```

### Conflicts with Other Bots

1. Verify all environment variables are prefixed
2. Check for port conflicts (Discord bots use websockets, not ports)
3. Ensure separate cache files
4. Check systemd service isolation

### Performance

- Monitor resource usage: `htop` or `top`
- Check memory: `free -h`
- Review logs for errors: `journalctl -u behind-bars-bot`

## Updating the Bot

```bash
# Stop the service
sudo systemctl stop behind-bars-bot

# Update code
cd /path/to/behind-bars-bot
git pull  # or your update method
pip install -e .

# Start the service
sudo systemctl start behind-bars-bot

# Verify it's running
sudo systemctl status behind-bars-bot
```

