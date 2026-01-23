# Mainly.AI

Mainly.AI is a graph-first AI development platform that enables real-time collaboration on structured, modular AI workflows. Build full-stack applications using node-based visual programming, where nodes represent functions, services, and integrations.

## Key Features

- **Graph-based architecture**: Define application structure through visual graphs where nodes represent modular, reusable components.
- **Real-time collaboration**: Multiple developers can work simultaneously without the file exchange and merge conflicts typical of notebooks.
- **Full-stack AI DevOps**: Complete end-to-end workflow from data preparation and model training to deployment and MLOps.
- **Flexible infrastructure**: Hot-swap models with no vendor lock-in, supporting OpenAI, Anthropic, Mistral, Gemini, Hugging Face, and more.
- **Python under the hood**: All nodes are written in standard Python—if you can do it in Python, you can do it in Mainly.AI.

## Repository Structure

```
packages/
| mirmod/              # Core graph execution engine and workflow processing
| miranda_admin_ops/   # Private Git submodule, contains mostly SQL scripts and migrations

apps/
| localbot/            # Local runtime manager for mirmod.processor instances
| cdc/                 # Change data capture utilities
```

## Requirements

- Python 3.12 or higher (< 3.14)
- [uv](https://github.com/astral-sh/uv) package manager

## Building

```bash
# Build all python packages and apps
uv run poe build

# Build Docker images
uv run poe build:docker:processor
```

## Documentation

For detailed documentation and guides, visit [mainly.ai](https://docs.mainly.ai/).

## Contributing & Contact

Contributions are welcome! For questions or support, reach out at contact@mainly.ai or join our Discord community at [https://discord.gg/CPubC4TKqQ](https://discord.gg/CPubC4TKqQ).

## License

This project is licensed under the GNU General Public License v2.0. See [LICENSE](LICENSE) for details.