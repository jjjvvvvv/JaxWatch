# JaxWatch Image Prompt Generator

A creative visualization tool that generates detailed prompts for image generation AI tools using Jacksonville civic project data from JaxWatch.

## 🎨 Purpose

Transform real civic project data into compelling visual prompts for:
- **Streetview-focused generators** (like "nano banana" or similar urban visualization tools)
- **General AI image generators** (DALL-E, Midjourney, Stable Diffusion)
- **Architectural visualization tools**
- **Urban planning concept art**

This tool operates independently of JaxWatch's core functionality and serves as a creative extension for visualizing Jacksonville's development landscape.

## 🚀 Quick Start

```bash
# Preview prompts for all projects
python3 tools/image_prompt_generator.py --preview

# Generate streetview prompts for Laura Street projects
python3 tools/image_prompt_generator.py --filter "Laura" --type streetview

# Export all prompt types to file
python3 tools/image_prompt_generator.py --type all --output my_prompts.txt

# Generate conceptual art prompts
python3 tools/image_prompt_generator.py --type conceptual --preview
```

## 📊 Data Analysis

The generator performs intelligent analysis of JaxWatch project data:

### Project Classification
- **Scale Detection**: Major development, significant development, standard development, improvement project
- **Type Analysis**: Mixed-use, residential, commercial, public infrastructure, etc.
- **Location Context**: Downtown setting, waterfront, historic district
- **Civic Process Stage**: Approved, proposed, under construction, planning
- **Architectural Style**: Modern, historic preservation, contemporary urban

### Financial Analysis
Extracts financial amounts from project documents to infer scale and scope

### Geographic Context
Uses address data and project descriptions to add location-specific details:
- Downtown Jacksonville urban grid
- St. Johns River waterfront context
- Historic district character

## 🎯 Prompt Types

### Streetview Prompts
Optimized for street-level visualization tools
- Detailed architectural descriptions
- Environmental and lighting context
- Jacksonville-specific urban elements
- Professional photography style directions

### Aerial Prompts
Designed for drone/bird's-eye view generation
- Urban planning perspective
- Neighborhood integration context
- Infrastructure and transportation networks

### Conceptual Prompts
Artistic interpretation for concept art
- Vision-focused language
- Community impact emphasis
- Inspirational architectural rendering style

## 📝 Example Output

```
PROJECT 1: 231 N Laura Street
Location: 231 N Laura Street
Scale: Standard Development | Type: Public Infrastructure

STREETVIEW PROMPT:
Enhanced streetscape and public infrastructure at 231 N Laura Street, Jacksonville, Florida.
thoughtfully designed urban architecture, contemporary Florida architectural style. urban
downtown setting, mixed pedestrian and vehicle traffic, city skyline visible in background,
subtropical landscaping with palm trees, Florida sunshine lighting, wide sidewalks with
modern streetscape elements. finished development ready for use. professional architectural
photography, high resolution, realistic lighting, urban planning visualization.
```

## 🛠️ Command Line Options

```bash
python3 tools/image_prompt_generator.py [OPTIONS]

Options:
  --filter TEXT        Filter projects by title/address substring
  --type CHOICE        Type of prompts: streetview, aerial, conceptual, both, all
  --output FILE        Output file for prompts (default: timestamped file)
  --preview           Preview prompts in terminal instead of saving
  --help              Show help message

Examples:
  --preview                          # Preview all streetview prompts
  --type aerial --output prompts.txt # Export aerial prompts
  --filter "Laura" --type both       # Both types for Laura Street projects
  --type conceptual --preview        # Conceptual art prompts
```

## 📂 File Structure

```
tools/
├── image_prompt_generator.py         # Main generator script
├── README_IMAGE_PROMPTS.md          # This documentation
└── example_image_prompts.txt        # Sample output file
```

## 🔗 Integration

### Data Source
Reads from: `admin_ui/data/projects_index.json`
- Uses geocoded project locations
- Analyzes project descriptions and snippets
- Extracts financial and timeline data

### Independence
- **No dependencies** on core JaxWatch functionality
- **Separate namespace** - lives in `tools/` directory
- **Optional feature** - doesn't affect main pipeline
- **Extensible design** - easy to enhance over time

## 🎨 Image Generation Workflow

1. **Run JaxWatch Pipeline**: Collect and enrich project data
2. **Generate Prompts**: Use this tool to create image prompts
3. **Choose Generator**: Feed prompts to your preferred image AI
4. **Create Visuals**: Generate streetviews, aerials, or concept art
5. **Iterate**: Refine prompts based on results

## 🔮 Future Enhancements

Potential improvements for future development:

### Enhanced Analysis
- Sentiment analysis of public comments
- Integration with property records for building details
- Historical comparison prompts (before/after)

### Additional Prompt Types
- **Interior visualization** prompts for public spaces
- **Timeline sequence** prompts showing development phases
- **Community impact** prompts showing people using spaces

### Integration Features
- Direct API integration with image generation services
- Batch processing with multiple style variations
- Web interface for non-technical users

### Output Formats
- JSON export for programmatic use
- CSV format for spreadsheet analysis
- Integration with presentation tools

## 🏗️ Technical Details

### Architecture
- **Pure Python** - no external dependencies beyond standard library
- **Modular design** - easy to extend with new prompt types
- **Efficient data processing** - handles large project datasets
- **Error handling** - graceful degradation with incomplete data

### Performance
- Fast analysis of project datasets
- Minimal memory footprint
- Suitable for automated workflows

## 💡 Creative Applications

This tool enables creative visualization of civic projects:

- **Public engagement**: Visual communication of development plans
- **Planning presentations**: Concept art for city meetings
- **Educational content**: Illustrate urban development processes
- **Art projects**: Data-driven civic art installations
- **Historical documentation**: Visual archive of city development

## 🎯 Design Philosophy

**Separate but Connected**: This tool maintains the JaxWatch philosophy of factual, source-driven analysis while adding a creative visualization dimension that doesn't interfere with core data integrity.

**Community Oriented**: Designed to make civic development data more accessible and engaging through visual storytelling.

**Extensible Foundation**: Built as a foundation that can grow and improve over time as both the data and image generation technologies evolve.

---

*Part of the JaxWatch civic transparency toolkit - transforming municipal data into actionable community insights.*