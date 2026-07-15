# Contributing

Thank you for your interest in contributing!

## How to Contribute

1. **Fork** the repository
2. **Create a feature branch** (`git checkout -b feature/my-feature`)
3. **Make your changes**
4. **Run the linter/formatting** if applicable
5. **Commit** with a descriptive message
6. **Push** to your fork
7. Open a **Pull Request**

## Guidelines

- Follow existing code style (naming, structure, patterns)
- Keep scripts compatible with **Python 3.10+** and **Bash 3.2+**
- Do **not** hardcode project IDs, bucket names, or any credentials
- Use environment variables or CLI arguments for configurable values
- Test with `shellcheck` for shell scripts and `ruff` / `pylint` for Python
- Update `README.md` if you add or change functionality
