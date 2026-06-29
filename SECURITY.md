# Security Policy

## Reporting a vulnerability

Please report security issues privately to **info+sec@birthday.tools**.

Do **not** open a public GitHub issue for security vulnerabilities.

Include where relevant:
- a description of the issue and its impact,
- steps to reproduce (or a proof of concept),
- affected version(s).

We aim to acknowledge reports within a few business days and will keep you updated
as we work on a fix. We'll credit reporters who wish to be named once a fix ships.

## Supported versions

EdgarMCP is distributed on PyPI as [`mcp-edgar`](https://pypi.org/project/mcp-edgar/).
Security fixes target the **latest released version**. Please upgrade before reporting:

```bash
pip install --upgrade mcp-edgar
```

## Scope notes

EdgarMCP is a local stdio MCP server that calls public financial data sources
(SEC EDGAR, FRED, OpenFIGI, Tradernet). It stores no credentials beyond the
optional API keys you supply via environment variables, and telemetry is
**opt-in and off by default** (no IP addresses or query content are ever sent).
