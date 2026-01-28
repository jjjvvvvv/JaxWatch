# Clawdbot - JaxWatch Enhancement Tool

Clawdbot enhances JaxWatch project data using Large Language Models to provide deeper insights and analysis.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd clawdbot
   pip install -r requirements.txt
   ```

2. **Try the demo (no API key needed):**
   ```bash
   python3 clawdbot.py demo
   ```

3. **For live LLM analysis:**
   ```bash
   export GROQ_API_KEY="your-groq-api-key-here"
   python3 clawdbot.py summarize
   ```

4. **Verify installation:**
   ```bash
   python3 verify.py
   ```

## Commands

### `demo`

Run a demonstration with mock LLM responses (no API key required).

- **Purpose**: Show what the enhancement looks like without API costs
- **Output**: `demo_output.json` with sample enhanced projects
- **Use case**: Testing, demonstrations, development

### `summarize`

Enhances JaxWatch projects with real LLM-generated summaries.

- **Input**: `../admin_ui/data/projects_index.json`
- **Output**: `../admin_ui/data/projects_enriched.json`
- **Process**: Selects 10 most interesting projects and enhances them with AI analysis
- **Requirements**: GROQ_API_KEY environment variable

**Enhanced output format:**
```json
{
  "id": "PROJ-SHIPYARDS",
  "title": "The Shipyards & Four Seasons",
  // ... all existing JaxWatch fields unchanged ...
  "clawdbot_analysis": {
    "enhanced_summary": "AI-generated 2-3 sentence summary focusing on what the project does, financial indicators, and current status",
    "processed_at": "2026-01-27T18:44:45.520425",
    "version": "0.1.0"
  }
}
```

## Example Output

Here's what the AI enhancement adds to a project:

**Original JaxWatch data:**
- Title: "The Shipyards & Four Seasons"
- Summary: "Master project for The Shipyards & Four Seasons with 118 related documents"
- Child project count: 118

**Clawdbot enhancement:**
- Enhanced summary: "The Shipyards development is a major mixed-use waterfront project featuring residential, commercial, and entertainment facilities. With 118 related documents spanning multiple years, this represents one of Jacksonville's most significant ongoing developments with substantial public investment and regulatory oversight."

## Configuration

Edit `config.yaml` to customize:

```yaml
# LLM Settings
llm_provider: "groq"
llm_model: "llama-3.1-8b-instant"
llm_api_key_env: "GROQ_API_KEY"

# Data Paths (relative to clawdbot directory)
input_path: "../admin_ui/data/projects_index.json"
output_path: "../admin_ui/data/projects_enriched.json"
```

## Project Selection Logic

Clawdbot automatically selects the most interesting projects based on:

1. **Master project status** (10 points)
2. **Number of child documents** (up to 20 points)
3. **Has address information** (5 points)
4. **Has meaningful summary** (5 points)
5. **Substantial title** (3 points)

This ensures processing focuses on substantial, well-documented projects rather than system artifacts.

## Requirements

- Python 3.7+
- Dependencies: `requests`, `pyyaml`
- For live mode: Groq API key (free tier available at https://console.groq.com)
- Internet connection for LLM API calls

## Getting a Groq API Key

1. Visit https://console.groq.com
2. Sign up for free account
3. Generate an API key
4. Export it: `export GROQ_API_KEY="your-key-here"`

Free tier includes generous usage limits sufficient for testing.

## Cost Estimate

- Demo mode: $0 (uses mock responses)
- Live mode: < $0.10 for 10 projects using Groq free tier
- Typical response time: 1-3 seconds per project

## Verification

Run the verification script to ensure everything is working:

```bash
python3 verify.py
```

This checks:
- ✅ File structure completeness
- ✅ Configuration validity
- ✅ Input data accessibility
- ✅ Demo output format

## Implementation Status

**Phase A: Minimal Working Enhancement** ✅

- [x] Single command implementation
- [x] Basic LLM integration
- [x] Project selection logic
- [x] Demo mode for testing
- [x] Verification script
- [x] Comprehensive documentation

This is the initial "factory floor first" implementation focused on proving value with real data before expanding features.

## Next Steps (Phase B - Only if Phase A proves valuable)

Potential future enhancements:
- Classification commands
- Relationship extraction
- Integration with JaxWatch pipeline
- Additional LLM providers
- Batch processing modes

The focus remains on simple, working tools that provide genuine insight into Jacksonville civic projects.