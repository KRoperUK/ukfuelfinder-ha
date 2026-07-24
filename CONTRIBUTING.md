# Contributing to UK Fuel Finder

Thank you for your interest in contributing to the UK Fuel Finder Home Assistant integration!

## Reporting Issues

- Use the [GitHub issue tracker](https://github.com/KRoperUK/ukfuelfinder-ha/issues)
- Search existing issues before creating a new one
- Include Home Assistant version, integration version, and logs
- Describe steps to reproduce the issue

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ukfuelfinder-ha.git
   cd ukfuelfinder-ha
   ```

3. Install development dependencies:
   ```bash
   pip install -r requirements_test.txt
   ```

4. Install the pre-commit hooks (lint + type check on commit, tests with
   coverage on push):
   ```bash
   pre-commit install --hook-type pre-commit --hook-type pre-push
   ```

5. Create a branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Code Standards

- Follow Home Assistant coding standards
- Use type hints (checked with mypy)
- Add docstrings to all functions and classes
- Keep line length to 100 characters
- Use Ruff for linting and formatting (the pre-commit hooks run it automatically):
  ```bash
  ruff check custom_components tests
  ruff format custom_components tests
  ```

## Testing

- Add tests for new functionality
- Ensure all tests pass:
  ```bash
  pytest
  ```
- Keep coverage at or above the enforced floor (currently 70%)

## Pull Request Process

1. Update documentation if needed
2. Use a [Conventional Commits](https://www.conventionalcommits.org/) PR title
   (e.g. `feat: add per-sensor location`) — CHANGELOG.md and versioning are
   automated by release-please, so no manual changelog edits
3. Ensure all tests pass
4. Create a pull request with a clear description
5. Link any related issues

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## Questions?

Open an issue for questions or discussion.
