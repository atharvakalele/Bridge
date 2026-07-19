# Installing the Claude Code ↔ Antigravity IDE Bridge

Follow these steps to set up the bidirectional autonomous bridge between Claude Code and the Antigravity IDE.

## Prerequisites
- **Python 3.8+** must be installed on your machine.
- **Claude Code** and **Antigravity IDE** must be installed and running.

---

## Step 1: Run the Installation Script
From the root of the `Bridge/` directory, run the installation script:
```bash
bash scripts/install.sh
```

This script will:
1. Create the global configuration directory at `~/.config/bridge`.
2. Copy the Gemini-side scripts to `~/.config/bridge/gemini_side/`.
3. Create the default configuration file `~/.config/bridge/config.json`.
4. Install the Python package globally or in the active virtual environment using `pip install -e .`.

---

## Step 2: Register the MCP Server with Claude Code
Run the following command in your terminal to register the Bridge server globally with Claude Code:
```bash
claude mcp add --scope user bridge-mcp-server -- bridge-mcp-server
```

Alternatively, you can manually add the configuration block to your Claude configuration file (usually located at `~/.claude.json` or `~/.config/Claude/mcp.json`):
```json
{
  "mcpServers": {
    "bridge": {
      "command": "bridge-mcp-server"
    }
  }
}
```

---

## Step 3: Configure Antigravity Agent Rules
Copy the instructions from `~/.config/bridge/gemini_side/AGENT_RULES.md` into your Antigravity IDE agent's global rules or system memory. 

This ensures that the Gemini agent knows how to launch the tracked waiter loop to auto-wake itself when tasks are delegated.

---

## Step 4: Add Protocol to Project Workspace
Copy the protocol snippet from `templates/CLAUDE.md.snippet` into your project's `CLAUDE.md` file. This tells Claude Code how to interact with the bridge, set up monitors, and handle tool delegation timeouts.
