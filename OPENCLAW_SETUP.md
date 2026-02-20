# OpenClaw Integration for JaxWatch

## Overview

Replaced custom `slack_bridge/` with **OpenClaw** (v2026.2.17) — an open-source AI assistant with native Slack support, shell execution, file access, and custom Skills system. Runs locally on Apple Silicon using MLX.

## Architecture

```
Slack ↔ OpenClaw Gateway ↔ Ollama API (port 11434)
                              ↓
                         mlx-proxy.py
                              ↓
                    mlx-openai-server (port 8085)
                              ↓
                      Qwen3-14B-4bit (MLX)
```

**Key Components:**
- **OpenClaw Gateway**: Daemon running via LaunchAgent, handles Slack Socket Mode
- **mlx-proxy.py**: Translates Ollama API (`/api/chat`) ↔ OpenAI API (`/v1/chat/completions`)
- **mlx-openai-server**: Serves MLX models via OpenAI-compatible API with tool calling support
- **Qwen3-14B-4bit**: Local 14B parameter model quantized to 4-bit, runs on Apple Neural Engine

## File Locations

### OpenClaw Configuration
- `~/.openclaw/openclaw.json` — Main config (model, Slack settings, workspace path)
- `~/.openclaw/agents/main/agent/auth-profiles.json` — Ollama auth profile
- `~/.openclaw/workspace/` — Skills, SOUL.md, TOOLS.md
- `~/.openclaw/workspace/skills/` — Custom JaxWatch skills (5 skills)
- `~/.openclaw/logs/gateway.log` — Gateway stdout
- `~/.openclaw/logs/gateway.err.log` — Gateway stderr

### MLX Server Configuration
- `~/.openclaw/mlx-server.conf` — Model path, parser, port, template
- `~/.openclaw/mlx-server-start.sh` — Wrapper script to read conf and launch
- `~/.openclaw/qwen3-no-think.jinja` — Custom chat template (thinking disabled)
- `~/.openclaw/mlx-proxy.py` — HTTP proxy (Ollama ↔ OpenAI translation)
- `~/.openclaw/mlx-server-venv/` — Python venv with mlx-openai-server v1.5.3

### LaunchAgents
- `~/Library/LaunchAgents/ai.openclaw.gateway.plist` — OpenClaw gateway daemon
- `~/Library/LaunchAgents/local.mlx-openai-server.plist` — MLX server daemon
- `~/Library/LaunchAgents/local.mlx-proxy.plist` — Proxy daemon

### Logs
- `/tmp/openclaw/openclaw-YYYY-MM-DD.log` — Detailed agent execution logs (JSON lines)
- `/tmp/mlx-openai-server.log` — MLX server stdout
- `/tmp/mlx-openai-server.err` — MLX server stderr (startup banner)
- `/tmp/mlx-proxy.log` — Proxy stdout (empty - logging suppressed)
- `/tmp/mlx-proxy.err` — Proxy stderr (errors, debug when enabled)

## JaxWatch Skills (5 Skills)

Created but **not yet tested**:
1. **jaxwatch-search** — Search projects, full-text content search
2. **jaxwatch-collect** — Run collection pipeline (Makefile targets)
3. **jaxwatch-analysis** — Document verification, reference scanning
4. **jaxwatch-maintain** — Update project metadata, merge duplicates
5. **jaxwatch-status** — System status, project counts, data freshness

Helper scripts (not yet written):
- `~/.openclaw/workspace/skills/jaxwatch-search/scripts/search_projects.py`
- `~/.openclaw/workspace/skills/jaxwatch-search/scripts/search_content.py`
- `~/.openclaw/workspace/skills/jaxwatch-analysis/scripts/check_verification.py`
- `~/.openclaw/workspace/skills/jaxwatch-maintain/scripts/update_project.py`
- `~/.openclaw/workspace/skills/jaxwatch-maintain/scripts/merge_projects.py`
- `~/.openclaw/workspace/skills/jaxwatch-status/scripts/system_status.py`

## Current Status

### ✅ Working
- OpenClaw installed and configured
- Gateway connected to Slack (#dev channel)
- MLX server running with Qwen3-14B-4bit model
- Proxy translating Ollama ↔ OpenAI API formats (non-streaming)
- Tool calling infrastructure in place
- Custom chat template loaded (thinking disabled)
- 5 JaxWatch skills registered with OpenClaw

### ⚠️ Known Issues

#### Issue #1: Qwen3 Thinking Mode Causes Timeouts
**Problem:** Even with custom chat template (`qwen3-no-think.jinja`) that injects `<think>\n\n</think>\n\n` to skip thinking, the model still generates thinking tokens for 2+ minutes. OpenClaw's typing indicator has a 2-minute TTL, causing timeouts.

**Evidence:**
- mlx-openai-server receives request, logs "messages filtered", but no `200 OK` after 2+ minutes
- Proxy gets `BrokenPipeError` when trying to write chunks back (OpenClaw closed connection)
- During thinking, proxy strips `<think>...</think>` tokens → no data sent to OpenClaw → HTTP read timeout

**Attempted Fixes:**
1. ✗ `enable_thinking: false` in request body → mlx-openai-server ignores it
2. ✗ `/no_think` in system message → model still thinks
3. ✗ Custom chat template with `<think>\n\n</think>\n\n` pre-injected → model still thinks
4. ✗ Thinking token stripping in proxy → causes read timeout (no heartbeat during 2+ min thinking)

**Root Cause:** Unknown why template isn't disabling thinking. Possible:
- Template applied incorrectly
- Model ignoring the closed `<think></think>` block in context
- mlx-openai-server not using the custom template despite `--chat-template-file` flag

**Next Steps:**
- Debug: Add chat template to request body directly to verify it's being used
- Debug: Check if Qwen3-14B-4bit actually supports thinking disable (might need different model)
- Alternative: Switch to Qwen2.5-Coder-14B (no thinking mode)
- Alternative: Use non-streaming mode (accumulate full response, then return)
- Alternative: Send heartbeat chunks to OpenClaw during thinking

#### Issue #2: Streaming Disconnects
**Problem:** When streaming works, OpenClaw sometimes closes connection mid-stream (`BrokenPipeError` in proxy).

**Possible causes:**
- OpenClaw's HTTP client has a read timeout when no data arrives for too long
- Malformed NDJSON chunks (though manual tests work fine)
- OpenClaw can't parse tool calls in Ollama streaming format

#### Issue #3: Large Request Bodies
**Problem:** OpenClaw sends very large requests (15 skills × tool schemas + system prompts). If OpenClaw uses chunked transfer encoding (HTTP/1.1) and the proxy (HTTP/1.0) doesn't handle it, body might be truncated.

**Evidence:** Debug logging added but not yet tested with full OpenClaw request.

**Fix:** Upgrade proxy to use HTTP/1.1 or handle chunked encoding.

## Troubleshooting

### Check if services are running
```bash
launchctl list | grep -E "openclaw|mlx"
lsof -i :11434  # Proxy
lsof -i :8085   # MLX server
lsof -i :18789  # OpenClaw gateway
```

### Restart services
```bash
# Restart OpenClaw gateway
launchctl kickstart -k gui/$UID/ai.openclaw.gateway

# Restart MLX server (picks up new mlx-server.conf)
launchctl kickstart -k gui/$UID/local.mlx-openai-server

# Restart proxy
launchctl unload ~/Library/LaunchAgents/local.mlx-proxy.plist
launchctl load ~/Library/LaunchAgents/local.mlx-proxy.plist
```

### View logs
```bash
# OpenClaw gateway
tail -f ~/.openclaw/logs/gateway.log

# OpenClaw agent execution (JSON lines)
tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | jq

# MLX server
tail -f /tmp/mlx-openai-server.log

# Proxy (enable debug logging first by uncommenting in mlx-proxy.py)
tail -f /tmp/mlx-proxy.err
```

### Test proxy manually
```bash
# Non-streaming
curl -X POST http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:14b","messages":[{"role":"user","content":"say hi"}],"stream":false}'

# Streaming
curl -X POST http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:14b","messages":[{"role":"user","content":"say hi"}],"stream":true}'
```

### Test MLX server directly
```bash
curl -X POST http://127.0.0.1:8085/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ollama-local" \
  -d '{"model":"qwen2.5-coder:14b","messages":[{"role":"user","content":"say hi"}],"stream":false}'
```

### Clear stale sessions
```bash
# If OpenClaw is using a stale session with deleted transcript
echo '{}' > ~/.openclaw/agents/main/sessions/sessions.json
```

## Model Configuration

### Switching Models
Edit `~/.openclaw/mlx-server.conf`:
```bash
MODEL_PATH=mlx-community/Qwen3-14B-4bit
TOOL_CALL_PARSER=qwen3
PORT=8085
CHAT_TEMPLATE=/Users/jjjvvvvv/.openclaw/qwen3-no-think.jinja
```

Then restart: `launchctl kickstart -k gui/$UID/local.mlx-openai-server`

### Recommended Models

**For interactive Slack (fast responses):**
- `mlx-community/Qwen2.5-Coder-14B-4bit` — No thinking mode, fast, good at coding

**For complex reasoning (if thinking timeout is fixed):**
- `mlx-community/Qwen3-14B-4bit` — Current model, has thinking mode
- `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` — Larger, better quality (requires 32GB+ RAM)

## Performance Notes

- **First token latency**: ~5-6 seconds for simple prompts
- **With thinking**: 2+ minutes before actual response (causes timeout)
- **Without thinking**: Should be <30 seconds for typical requests
- **Model loading**: ~10 seconds on first request after server restart
- **Memory**: Qwen3-14B-4bit uses ~8GB RAM when loaded

## Next Steps

1. **Fix thinking timeout issue** (critical)
   - Debug why custom template isn't working
   - Consider switching to Qwen2.5-Coder-14B

2. **Test JaxWatch skills**
   - Write the 6 helper scripts
   - Test each skill individually from Slack

3. **Verify tool calling works end-to-end**
   - Model generates tool call → OpenClaw executes → Result sent back

4. **Optimize for production**
   - Tune model parameters (temperature, top_p, max_tokens)
   - Add monitoring/alerting for service health
   - Set up log rotation

## References

- OpenClaw docs: https://docs.openclaw.ai/
- mlx-openai-server: https://github.com/Blaizzy/mlx-openai-server
- Qwen3 model card: https://huggingface.co/mlx-community/Qwen3-14B-4bit
- Ollama API spec: https://github.com/ollama/ollama/blob/main/docs/api.md
