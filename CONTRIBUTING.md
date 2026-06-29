# Contributing to EdgarMCP

Thanks for your interest in improving EdgarMCP! Contributions of all kinds are
welcome — bug reports, fixes, new data tools, and documentation.

## Reporting bugs & requesting features

Open an [issue](https://github.com/birthday-tools/edgarmcp/issues) using the
templates provided. For security vulnerabilities, **do not** open a public issue —
see [SECURITY.md](SECURITY.md).

A good bug report includes the EdgarMCP version (`pip show mcp-edgar`), the tool
you called, the arguments, and what you expected versus what happened.

## Development setup

EdgarMCP uses [uv](https://docs.astral.sh/uv/) and targets Python 3.11+.

```bash
git clone https://github.com/birthday-tools/edgarmcp
cd edgarmcp
uv sync
```

Run the test suite and linter before opening a PR:

```bash
uv run pytest
uv run ruff check .
```

## Pull requests

- Keep PRs focused — one logical change per PR.
- Add or update tests for any behavior change.
- Make sure `pytest` and `ruff` pass.
- Follow the existing code style and the conventions you see in nearby code.
- Describe the motivation and the change in the PR body (the template will prompt you).

By contributing you agree that your contributions are licensed under the
project's [MIT License](LICENSE).

## Data sources

EdgarMCP wraps several external APIs (SEC EDGAR, FRED, OpenFIGI, Tradernet).
When adding or changing a tool, please respect each source's terms of use and
rate limits, and set a descriptive User-Agent where the source requires one.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you are expected to uphold it.
