# Document Verifier - JaxWatch Enhancement Tool

Document Verifier annotates JaxWatch derived project views with AI interpretations for easier browsing. All outputs are interpretations, not authoritative data.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd document_verifier
   pip install -r requirements.txt
   ```

2. **Try the demo (no API key needed):**
   ```bash
   python3 document_verifier.py demo
   ```

3. **For live AI annotation (requires MLX framework):**
   ```bash
   # MLX automatically loads models on first use
   python3 document_verifier.py document_verify
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

### `document_verify`

Annotates derived JaxWatch project views with AI interpretations.

- **Input**: `../admin_ui/data/projects_index.json`
- **Output**: `../admin_ui/data/projects_enriched.json`
- **Process**: Selects 10 most relevant project views and adds AI annotations
- **Requirements**: MLX framework installation

**Annotated output format:**
```json
{
  "id": "PROJ-SHIPYARDS",
  "title": "The Shipyards & Four Seasons",
  // ... all existing JaxWatch fields unchanged ...
  "document_verification": {
    "enhanced_summary": "AI-generated interpretation focusing on what the project appears to do, scale indicators, and current status",
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

**Document Verifier annotation:**
- AI interpretation: "The Shipyards development appears to be a major mixed-use waterfront project featuring residential, commercial, and entertainment facilities. With 118 related documents spanning multiple years, this represents one of Jacksonville's most significant ongoing developments with substantial public investment and regulatory oversight."

## Configuration

Edit `config.yaml` to customize:

```yaml
# LLM Settings
llm_provider: "mlx"
mlx_model: "mlx-community/Llama-3.2-1B-Instruct-4bit"
max_tokens: 2048
temperature: 0.1

# Data Paths (relative to document_verifier directory)
input_path: "../admin_ui/data/projects_index.json"
output_path: "../admin_ui/data/projects_enriched.json"
```

## Project Selection Logic

Document Verifier automatically selects the most interesting projects based on:

1. **Master project status** (10 points)
2. **Number of child documents** (up to 20 points)
3. **Has address information** (5 points)
4. **Has meaningful summary** (5 points)
5. **Substantial title** (3 points)

This ensures processing focuses on substantial, well-documented projects rather than system artifacts.

## Requirements

- Python 3.7+
- Dependencies: `requests`, `pyyaml`
- For live mode: MLX framework with Llama 3.2 model
- No internet connection required for local processing

## Setting up MLX

1. Install MLX framework: `pip install mlx-lm`
2. The model `mlx-community/Llama-3.2-1B-Instruct-4bit` downloads automatically on first use
3. No additional setup required - MLX handles model loading and inference
4. Verify by running a test document verification

Local processing ensures data privacy and no API costs.

## Resource Usage

- Demo mode: No resources (uses mock responses)
- Live mode: Local CPU/GPU processing only - no API costs
- Typical response time: 2-5 seconds per project (varies by hardware)

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