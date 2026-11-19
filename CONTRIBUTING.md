# Contributing to agent-treasury-stream

We welcome contributions from the community!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/devsoniclk/agent-treasury-stream.git
   cd agent-treasury-stream
   ```

2. Install development dependencies:
   ```bash
   pip install -e ".[dev,mcp]"
   ```

3. Run the test suite:
   ```bash
   pytest tests -v
   ```

## Pull Request Guidelines
- All tests must pass with 100% pass rate.
- Include unit tests for any new features or bug fixes.
- Follow PEP 8 style conventions and maintain typing compliance.
- Update documentation and changelog as appropriate.
