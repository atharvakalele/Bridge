# Contributing to Antigravity Bridge

We welcome contributions, fixes, and workflow improvements!

## Branch Policy & Pull Requests

- **Always target `dev`**: All Pull Requests must be opened against the `dev` branch.
  - `main` is reserved for stable, tagged releases.
  - `dev` is the active development branch.
- **Keep PRs small & focused**: Smaller, modular PRs make review and debugging much faster.

## Security & Secrets

- **Never commit secrets**: No API keys, passwords, bearer tokens, or personal paths.
- Ensure that test runs, logs, `.jsonl` transcripts, and SQLite conversation files (`*.db`) are ignored and not included in commits.

## Local Smoke Testing

Before submitting a PR, verify that the local MCP server and CLI wrappers function cleanly:

1. **Verify Python package installation**:
   ```bash
   pip install -e .
   ```

2. **Test Model Listing**:
   ```bash
   python3 -c "from agy_cli.server import handle_models; print(handle_models())"
   ```

3. **Run a smoke task via CLI**:
   ```bash
   agy-job --timeout 2m "echo 'smoke test'; ls -la"
   ```

4. **Verify MCP Server startup**:
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | agy-cli-mcp
   ```

Thank you for helping build seamless agentic delegation!
