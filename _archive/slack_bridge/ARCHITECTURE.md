# JaxWatch Slack Bridge Architecture

## Simplified Architecture (Current)

The Slack bridge has been streamlined to use a direct, efficient flow:

```
Slack Message → ConversationalSlackGateway → JaxWatchCore API → Response
```

### Key Components

1. **ConversationalSlackGateway** (Primary)
   - Claude-powered natural language understanding
   - Direct integration with JaxWatchCore API
   - Real-time responses for quick operations
   - Background job management for long-running tasks

2. **JaxWatchCore API**
   - Unified API for all JaxWatch functionality
   - Document verification, project extraction, reference scanning
   - No subprocess calls - direct Python integration

3. **SlackGateway** (⚠️ DEPRECATED)
   - Legacy regex-based command parsing
   - Maintained for backward compatibility only
   - Use `--legacy` flag to run deprecated version

## Benefits of Simplified Architecture

- **No subprocess overhead** - Direct Python API calls
- **Better error handling** - Exceptions caught and handled properly
- **Real-time feedback** - Immediate responses for quick operations
- **Conversational AI** - Natural language understanding via Claude
- **Reduced complexity** - Single gateway instead of two competing implementations

## Usage

### Start Modern Gateway (Recommended)
```bash
cd slack_bridge
python -m slack_bridge
```

### Start Legacy Gateway (Deprecated)
```bash
cd slack_bridge
python -m slack_bridge --legacy
```

## Environment Variables

Required:
- `SLACK_BOT_TOKEN` - Slack bot token
- `SLACK_APP_TOKEN` - Slack app token (Socket Mode)

Optional:
- `ANTHROPIC_API_KEY` - Claude API key for AI features

## Migration Guide

If currently using SlackGateway:

1. Switch to using `python -m slack_bridge` (no args)
2. Test functionality with ConversationalSlackGateway
3. Remove any scripts/cron jobs that call SlackGateway directly
4. Update documentation to reference new architecture

The ConversationalSlackGateway provides:
- All functionality of legacy gateway
- Enhanced natural language understanding
- Better error messages and user experience
- Direct API integration (no subprocess calls)

## Development Notes

- JobManager has been updated to use JaxWatchCore API instead of subprocess calls
- Command parsing is now AI-powered instead of regex-based
- Status checks use direct API calls for real-time data
- Background jobs use the unified enrichment pipeline