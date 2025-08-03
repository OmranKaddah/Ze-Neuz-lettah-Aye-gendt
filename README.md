# Ze Neuz lettah Aye-gendt

An AI-powered newzz generation system that automatically searches for the latest developments in AI agents, multi-agent systems, and related technologies. The system generates beautiful HTML and text newsletters suitable for email distribution.
Best in the world, second in mars.

## Features

- 🔍 **Parallel Search**: Simultaneously searches ArXiv papers and AI news/tutorials
- 📚 **ArXiv Integration**: Fetches latest research papers on AI agents
- 🌐 **Web Search**: Uses Tavily API to find recent news, tools, and tutorials
- 📧 **Email-Ready Output**: Generates both HTML and plain text newsletters
- 🎨 **Professional Design**: Beautiful, responsive HTML newsletter template
- 🐳 **Docker Support**: Easy deployment with Docker and Docker Compose
- 📊 **Structured Data**: Uses Pydantic models for type-safe data handling

## Architecture

The system uses `pydantic_graph` to orchestrate a workflow with parallel execution:

1. **Parallel Search Phase**: Simultaneously searches ArXiv and web sources
2. **Coordination Phase**: Waits for both searches to complete
3. **Generation Phase**: Creates newsletter header and formats content
4. **Output Phase**: Saves newsletter in HTML and text formats

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- API Keys for:
  - [Tavily Search API](https://tavily.com/) (required)
  - [Google Gemini API](https://ai.google.dev/) (required)
  - [Groq API](https://groq.com/) (optional, alternative to Gemini)

## Quick Start

### 2. Create Required Directories

```bash
mkdir -p data logs
```

### 3. Run with Docker Compose

```bash
docker compose up --build
```

The newsletter will be generated and saved to the `./data` directory on your local machine.

## Project Structure

```
simple-newsletter-agent/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── workflow.py          # Workflow orchestration
│   └── agents.py           # AI agents configuration
├── data/                   # Generated newsletters (mounted volume)
├── logs/                   # Application logs (mounted volume)
├── output/                 # output (mounted volume)
├── output_samples/         # output_samples (mounted volume)
├── .env                   # Environment variables
├── pyproject.toml         # Python dependencies
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Usage Options

### Docker Compose (Recommended)

```bash
# Run the full newsletter generation
docker-compose up --build

# Run in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f

# test
docker compose run --rm newsletter-agent uv run python src/main.py test
```

### Direct Python Execution

If you prefer to run without Docker:

```bash
# Install uv package manager
pip install uv

# Install dependencies
uv sync
# api keys (export all environment )
source .export_evn

# Run different workflows
uv run python src/main.py       # run
uv run python src/main.py test         # Test agent connections
uv run python src/main.py mermaid      # Show workflow diagrams
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | API key for Tavily search service |
| `GEMINI_API_KEY` | Google Gemini API key for AI models |
| `GROQ_API_KEY` | Groq API key (alternative to Gemini) |

### Workflow Options

- **no argument**: runs newsletter coordination nodes that mimic LangGraph behavior
- **test**: Tests all agent connections without generating content
- **mermaid**: Displays workflow diagrams

## Output

The system generates two types of newsletters in the `./data` directory:

### HTML Newsletter (`newsletter_YYYYMMDD_HHMMSS.html`)
- Professional, responsive design
- Styled with modern CSS
- Organized by content categories
- Clickable links to sources
- Email-compatible HTML

### Text Newsletter (`newsletter_YYYYMMDD_HHMMSS.txt`)
- Plain text format for email clients
- Structured, readable layout
- All content and links included
- Compatible with any email system

## Customization

### Modifying Search Criteria

Edit the prompts in `src/workflow.py`:

```python
# ArXiv search prompt
response = await research_arxiv_agent.run("""
    Find the 5 most recent arXiv papers related to your specific topic...
""")

# Web search prompt  
response = await search_agent.run("""
    Find recent developments in your area of interest...
""")
```

### Styling the Newsletter

Modify the CSS in the `generate_newsletter_html()` function in `src/newsletter_formatter.py` to customize:
- Colors and fonts
- Layout and spacing
- Component styling
- Responsive behavior

### Adding New Content Sources

1. Create new agent in `src/agents.py`
2. Add corresponding node in `src/workflow.py`
3. Update the parallel coordinator to include the new search
4. Modify newsletter generation to include new content type

## Troubleshooting


### Debugging

Enable debug logging by modifying `src/workflow.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
```

### Viewing Workflow Diagrams

```bash
docker-compose run newsletter-agent uv run python src/main.py mermaid
```



## Development

### Adding New Features

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Test with `docker-compose up --build`
5. Submit a pull request

### Testing

```bash
# Test agent connections
docker-compose run newsletter-agent uv run python src/main.py test
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For support and questions:

1. Check the troubleshooting section above
2. Review the logs in `./logs/`
3. Test individual components with the test command
4. Open an issue with detailed error information

## Roadmap

- [ ] Email delivery integration
- [ ] Scheduled execution with cron
- [ ] Multiple newsletter templates
- [ ] Integration with more data sources
- [ ] Web interface for configuration
- [ ] Analytics and tracking