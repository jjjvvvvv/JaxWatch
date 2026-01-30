# JaxWatch Conversational AI Implementation

## Overview

This directory contains the complete implementation of conversational AI for JaxWatch civic analysis, replacing the original regex-based command system with Claude-powered natural language understanding.

## 🚀 What's New: True Conversational AI

### Revolutionary Change

**❌ Old (Regex-Based):**
```
User: "verify 2026 projects"
Molty: [Pattern matching] → [Execute if exact match] → [Basic response]
```

**✅ New (Conversational AI):**
```
User: "Can you check if our 2026 civic projects are up to date?"
Molty: [Claude LLM] → [Understand intent] → [Contextual response] → [Remember conversation]
```

### Key Benefits

- 🧠 **Natural Language Understanding**: Talk to Molty like a human assistant
- 💭 **Persistent Memory**: Molty remembers your civic work across sessions
- 🔍 **Proactive Intelligence**: Suggests civic analysis actions when new documents appear
- 🌊 **Multi-turn Workflows**: Handle complex civic analysis in natural conversation
- 🎯 **Context Awareness**: References previous work and maintains civic focus

## 📁 Architecture Overview

### Core Components

```
slack_bridge/
├── conversational_agent.py          # Main LLM-powered civic assistant
├── civic_intent_engine.py           # Claude API integration for NLU
├── persistent_memory.py             # Markdown-based conversation storage
├── civic_context.py                 # Civic analysis domain knowledge
├── proactive_monitor.py             # File system intelligence
├── conversational_slack_gateway.py  # Enhanced Slack integration
├── job_manager.py                   # Enhanced with conversational context
└── config/
    ├── civic_tools.yml              # Tool catalog for AI
    └── claude_prompts.yml           # LLM system prompts
```

### Data Flow

```
User Message → Conversation Memory → Claude Intent Understanding →
Civic Action Planning → CLI Execution → Contextual Response →
Update Memory → Proactive Suggestions
```

## 🔧 Setup Instructions

### 1. Environment Variables

```bash
# Required for conversational AI
export ANTHROPIC_API_KEY="your-claude-api-key"

# Required for Slack integration
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export SLACK_SIGNING_SECRET="your-signing-secret"

# Optional: JaxWatch root path
export JAXWATCH_ROOT="/path/to/jaxwatch"
```

### 2. Install Dependencies

```bash
# Install conversational AI dependencies
pip install anthropic>=0.7.0 pyyaml>=6.0

# Install existing Slack dependencies
pip install slack-sdk>=3.21.0 slack-bolt>=1.18.0
```

### 3. Test the Implementation

```bash
# Test all conversational features
python test_conversational_implementation.py

# Test specific intent understanding
python conversational_slack_gateway.py --test-intent "verify 2026 transportation projects"

# Test Slack connection
python conversational_slack_gateway.py --test-connection
```

### 4. Start Conversational Gateway

```bash
# Start with conversational AI (recommended)
python conversational_slack_gateway.py

# Start in Socket Mode explicitly
python conversational_slack_gateway.py --socket-mode

# Start without proactive monitoring
python conversational_slack_gateway.py --disable-proactive
```

## 💬 Conversational Examples

### Natural Language Understanding

**Old Way (Regex):**
```
User: "verify 2026 projects"           # Exact pattern required
Molty: ✅ Running locally...           # Generic response
```

**New Way (Conversational):**
```
User: "Can you check if our 2026 civic projects are compliant?"
Molty: I'll verify all 2026 civic projects for compliance. This will check
       documents against current standards and identify any issues that need attention.

✅ Started Document verification for 2026 projects (Job ID: jw_1738166400)
```

### Multi-Turn Conversations

```
User: "I need to analyze the DIA board documents"
Molty: I can help with that civic analysis. Would you like me to:
       • Verify the documents for compliance
       • Scan for cross-references with other civic documents
       • Or both?

User: "Both please"
Molty: I'll verify the DIA board documents first, then scan for
       cross-references. Starting with document verification...

✅ Started Document verification for DIA board documents (Job ID: jw_1738166401)

[10 minutes later]
Molty: ✅ Document verification completed! Found 3 compliance areas
       requiring attention in transportation projects.

       Now starting reference scanning to find document connections...

✅ Started Reference scanning for DIA board documents (Job ID: jw_1738166402)
```

### Context-Aware Follow-ups

```
[Day 1]
User: "verify 2026 transportation projects"
Molty: I'll verify all 2026 transportation projects for compliance...

[Day 2]
User: "How did those transportation projects look?"
Molty: From yesterday's verification of 2026 transportation projects: I found
       compliance issues in 3 projects - missing environmental assessments
       and budget reconciliation needed.

       Would you like me to re-verify after you've addressed these issues?
```

### Proactive Suggestions

```
Molty: 🔍 I noticed new DIA board meeting minutes were uploaded.
       Should I scan them for project references and cross-connections?

       The documents are:
       • 2026-01-25_DIA_Board_Minutes.pdf (uploaded 5 minutes ago)
       • Infrastructure_Budget_Update.pdf (uploaded 3 minutes ago)

User: "Yes, and also verify them for compliance"
Molty: I'll scan for references first, then verify for compliance.
       This helps identify connected documents before analysis...
```

## 🧠 Conversational Features

### 1. Natural Language Understanding

- **Intent Recognition**: Understands civic analysis requests in natural language
- **Parameter Extraction**: Automatically extracts projects, years, document types
- **Context Integration**: Uses conversation history to understand references
- **Confidence Scoring**: Provides transparency about understanding level

### 2. Persistent Memory

- **Conversation History**: Stored in human-readable markdown files
- **Civic Preferences**: Learns user focus areas and notification preferences
- **Session Continuity**: Maintains context across bot restarts
- **Privacy Protection**: Automatic cleanup of old conversations

### 3. Proactive Intelligence

- **Document Monitoring**: Watches for new civic documents
- **Intelligent Suggestions**: Claude-powered analysis of what actions to suggest
- **Workflow Optimization**: Suggests efficient civic analysis sequences
- **Change Detection**: Identifies when documents need re-analysis

### 4. Enhanced Job Management

- **Rich Completion Messages**: Detailed civic analysis results
- **Follow-up Suggestions**: Intelligent next steps based on results
- **Error Guidance**: Helpful troubleshooting for failed jobs
- **Duration Tracking**: Human-friendly timing information

## 📋 Civic Integrity Safeguards

All civic integrity boundaries from the original system are maintained:

### ✅ What Molty CAN Do
- Parse natural language requests for civic analysis
- Route requests to appropriate JaxWatch CLI tools
- Maintain conversation context and memory
- Suggest relevant civic analysis workflows
- Provide rich status updates and completion messages

### ❌ What Molty CANNOT Do
- See actual document content (only metadata and file paths)
- Perform document analysis directly (only routes to CLI tools)
- Modify civic data (only read and analyze existing information)
- Hallucinate civic facts or compliance status
- Auto-execute actions without explicit confirmation

### 🔍 Transparency Features
- All LLM decisions logged to conversation history
- Civic action reasoning explained to user
- Full conversation context inspectable anytime
- Human-readable markdown storage format
- Graceful fallback when Claude API unavailable

## 🛠️ Configuration

### Civic Tools Catalog (`config/civic_tools.yml`)

Defines available civic analysis tools for the AI:

```yaml
tools:
  - name: document_verify
    command: python document_verifier/document_verifier.py document_verify
    description: Verify civic documents for compliance and standards
    parameters:
      - name: --project
        description: Verify documents for a specific project ID
      - name: --active-year
        description: Verify projects from a specific year
```

### Claude Prompts (`config/claude_prompts.yml`)

System prompts that guide Claude's civic analysis understanding:

```yaml
system_prompts:
  civic_agent_base: |
    You are Molty, a civic analysis assistant for JaxWatch.

    ROLE: Help users analyze civic documents through natural conversation
    while maintaining strict civic integrity boundaries...
```

## 🧪 Testing

### Automated Test Suite

```bash
python test_conversational_implementation.py
```

Tests all components:
- Conversation memory persistence
- Civic context gathering
- Intent understanding (with/without Claude API)
- Proactive monitoring
- Enhanced job management
- End-to-end conversational workflows

### Manual Testing

```bash
# Test intent understanding
python conversational_agent.py "verify 2026 transportation projects" test_user

# Test proactive monitoring
python proactive_monitor.py

# Test conversation memory
python persistent_memory.py
```

## 📊 Migration from Regex System

### Backward Compatibility

The system includes fallback mechanisms:

1. **Graceful Degradation**: Falls back to regex parsing if Claude API unavailable
2. **Existing Commands**: Original command patterns still work
3. **Session Management**: Preserves existing session tracking
4. **Status Reporting**: Maintains existing status collection

### Migration Path

1. **Phase 1**: Install conversational system alongside existing regex system
2. **Phase 2**: Test conversational features with real users
3. **Phase 3**: Switch to conversational gateway as default
4. **Phase 4**: Remove regex components (optional)

## 🔧 Troubleshooting

### Common Issues

**Claude API Not Available:**
- System automatically falls back to regex-based parsing
- Check `ANTHROPIC_API_KEY` environment variable
- Verify API key has sufficient quota

**Conversation Memory Issues:**
- Check write permissions on `conversations/` directory
- Verify disk space for markdown storage
- Old conversations cleaned up automatically after 30 days

**Proactive Monitoring Not Working:**
- Requires Claude API key for intelligent suggestions
- Falls back to rule-based suggestions without API
- Check file permissions on `inputs/` directories

**Intent Understanding Poor:**
- Check Claude API connectivity and quota
- Review system prompts in `config/claude_prompts.yml`
- Examine conversation context for clarity

### Debug Mode

```bash
# Enable debug logging
export DEBUG=1
python conversational_slack_gateway.py

# Test specific components
python -c "from conversational_agent import *; agent = create_conversational_agent('.')"
```

## 🚀 Advanced Features

### Custom Civic Workflows

Define custom civic analysis workflows by modifying `config/civic_tools.yml`:

```yaml
tools:
  - name: custom_compliance_check
    command: python custom_tools/compliance_checker.py
    description: Run custom compliance analysis
    parameters:
      - name: --regulation-set
        description: Specific regulation set to check against
```

### Extending Proactive Intelligence

Add custom document monitoring by extending `proactive_monitor.py`:

```python
def _classify_document(self, file_path: Path) -> Optional[str]:
    # Add custom document type classification
    if 'environmental_impact' in str(file_path).lower():
        return 'environmental_assessment'
    # ... existing logic
```

### Custom Response Templates

Modify `config/claude_prompts.yml` to customize how Molty responds:

```yaml
response_templates:
  custom_completion:
    - "🎯 Your custom analysis completed successfully!"
    - "🔍 Custom analysis revealed important insights!"
```

## 📈 Performance Considerations

### Claude API Usage

- **Intent Understanding**: ~100-500 tokens per message
- **Proactive Suggestions**: ~200-800 tokens per suggestion
- **Rate Limiting**: Automatic retry with exponential backoff
- **Cost Management**: Caches frequent civic context queries

### Memory Usage

- **Conversation Files**: ~5-10KB per user per month (markdown)
- **In-Memory Cache**: ~50MB for active conversations
- **Proactive Monitor**: ~10MB for file state tracking
- **Total Overhead**: ~100MB for conversational features

### Scaling Considerations

- Conversation memory scales linearly with active users
- Proactive monitoring scales with document volume
- Claude API calls scale with conversation complexity
- Consider conversation archiving for high-volume deployments

---

## 🎉 Success Metrics

The conversational transformation enables:

- **Zero "I don't understand" dead-ends** through natural language processing
- **Increased conversation length** via persistent memory
- **More complex civic workflows** initiated through natural conversation
- **Proactive civic intelligence** suggesting relevant analysis actions
- **Improved user satisfaction** through helpful, context-aware assistance

**Result**: True molt.bot utilization as intended - an intelligent conversational agent for civic transparency, not just a command parser.

---

*For questions or issues with the conversational implementation, check the test suite output or create an issue with the conversation logs and error details.*