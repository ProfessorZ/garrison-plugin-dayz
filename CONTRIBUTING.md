# Contributing to garrison-plugin-dayz

Contributions are welcome! Here's how to get started.

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/garrison-plugin-dayz.git
   cd garrison-plugin-dayz
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b my-feature
   ```

## Making Changes

- Keep changes focused — one feature or fix per PR.
- Follow the existing code style (type hints, dataclasses, async/await patterns).
- Test against a real DayZ server or a BattlEye RCON mock if possible.
- Update `schema.py` if adding or modifying commands.
- Update `README.md` if your change affects usage or setup.

## Submitting a Pull Request

1. **Commit** your changes with a clear message:
   ```bash
   git commit -m "Add feature X"
   ```
2. **Push** to your fork:
   ```bash
   git push origin my-feature
   ```
3. **Open a Pull Request** against the `main` branch of the upstream repository.
4. Describe what your PR does and why.

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Server and plugin version info

## Code of Conduct

Be respectful and constructive. We're all here to build something useful.
