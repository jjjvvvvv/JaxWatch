# JaxWatch Slack Bridge

Slack-first molt.bot integration as a conversational remote control for JaxWatch.

## Architecture

```
Slack → molt.bot (gateway only) → JaxWatch CLI → Local Analysis → Results
```

- **molt.bot role:** Command router + job orchestrator + status reporter (NO analysis)
- **JaxWatch role:** All document processing, AI operations, data storage

## Quick Setup

1. **Install dependencies:**
   ```bash
   cd slack_bridge
   pip install -r requirements.txt
   ```

2. **Configure Slack app credentials:**
   ```bash
   export SLACK_BOT_TOKEN="xoxb-your-bot-token"
   export SLACK_SIGNING_SECRET="your-signing-secret"
   export SLACK_APP_TOKEN="xapp-your-app-token"  # For Socket Mode
   ```

3. **Test connection:**
   ```bash
   python slack_gateway.py --test-connection
   ```

4. **Start the gateway:**
   ```bash
   python slack_gateway.py
   ```

## Slack Commands

### Document Verification
- `verify documents` - Run document verification on all projects
- `verify project DIA-RES-2025-12-03` - Verify specific project
- `verify 2026 projects` - Verify projects from specific year

### Reference Scanning
- `scan references` - Scan for document references
- `scan dia_board 2026` - Scan specific source and year

### System Status
- `status` or `health` - Show system health and activity
- `dashboard` - Get dashboard URL

### Help
- `help` or `commands` - Show available commands

## Example Slack Flows

### Document Verification Request
```
User: "@moltybot verify 2026 projects"
molt.bot: "✅ Running locally on JaxWatch. Started verify projects from specific year (ID: jw_1738166400). I'll report back here when done."
[Background: Runs python document_verifier/document_verifier.py document_verify --active-year 2026]
molt.bot (5 min later): "✅ Document verification completed locally! Processed 23 documents. Check dashboard for details."
```

### Status Check (Immediate)
```
User: "molty status"
molt.bot: "📊 JaxWatch Status (running locally):
• Total projects: 847
• Verified documents: 234
• Reference annotations: 312
• Dashboard: http://localhost:5000
• Last activity: 5 minutes ago

No active background jobs"
```

## Configuration

### Command Mappings (`config/command_mappings.yml`)

Commands are mapped using regex patterns:

```yaml
commands:
  - pattern: "(?i)verify\\s+(\\d{4})\\s+projects?"
    cli_command: "python document_verifier/document_verifier.py document_verify --active-year {1}"
    description: "Verify projects from specific year"
    background: true
```

### Slack Settings (`config/slack_config.yml`)

```yaml
slack:
  socket_mode: true  # Use Socket Mode (recommended)
  respond_to_mentions: true
  respond_to_dm: true
  respond_to_keywords: ["molty", "molt"]
```

## Slack App Setup

Required Slack app permissions:
- `chat:write` - Send messages to channels
- `app_mentions:read` - Receive @mentions
- `channels:history` - Read channel messages
- `im:history` - Read direct messages

Event subscriptions:
- `app_mention` - Trigger on @moltybot mentions
- `message.channels` - Trigger on channel messages containing "molty"
- `message.im` - Trigger on direct messages

## Running Modes

### Socket Mode (Recommended)
```bash
export SLACK_APP_TOKEN="xapp-your-app-token"
python slack_gateway.py --socket-mode
```

### HTTP Mode
```bash
python slack_gateway.py --http-mode
```

## Error Handling

- Invalid commands get helpful error messages
- Job failures reported back to user
- Timeouts handled gracefully (30 minute limit)
- No data corruption on failed jobs

## Security

- All processing runs locally on your machine
- No cloud dependencies for analysis
- molt.bot NEVER receives PDF content or document data
- molt.bot NEVER performs AI analysis or LLM calls
- molt.bot NEVER writes to JaxWatch data directories
- molt.bot ONLY executes CLI commands and reports status

## Integration Boundaries

**Critical separation:**

**molt.bot responsibilities:**
- Slack message receiving and parsing
- Command mapping via regex patterns
- Background job scheduling and status tracking
- Response formatting for Slack consumption

**JaxWatch responsibilities:**
- All PDF processing and text extraction
- All AI operations (MLX/Llama 3.2 analysis)
- All data storage and annotation management
- All dashboard and web interface operations

**Guiding principle:** molt.bot is a remote control for a deterministic civic analysis machine.