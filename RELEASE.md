# Release Process

## Versioning Scheme

This project uses [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

## Creating a Release

### Option 1: Using the release script (recommended)

```bash
# Patch release (0.1.0 -> 0.1.1)
./scripts/release.sh patch

# Minor release (0.1.0 -> 0.2.0)
./scripts/release.sh minor

# Major release (0.1.0 -> 1.0.0)
./scripts/release.sh major
```

### Option 2: Manual process

1. Update `VERSION` file with new version number
2. Commit the change:
   ```bash
   git add VERSION
   git commit -m "chore: release v0.1.0"
   ```
3. Create a git tag:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   ```
4. Push to remote:
   ```bash
   git push origin master
   git push origin v0.1.0
   ```

## Current Version

See the `VERSION` file for the current version number.

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2026-03-07 | Initial release |
