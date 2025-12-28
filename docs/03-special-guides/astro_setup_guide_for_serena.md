# Astro Setup Guide for Serena

Serena provides full support for [Astro](https://astro.build/) projects using the official
`@astrojs/language-server` with a companion TypeScript server for cross-file type resolution.

---

## Prerequisites

- **Node.js** (v18 or later recommended)
- **npm** (comes with Node.js)

Both must be available in your PATH. Serena will automatically download and install the required
language server packages on first use.

---

## Automatic Setup

When you first open an Astro project with Serena, it will automatically:

1. Install `@astrojs/language-server` (default: v2.16.2)
2. Install `@astrojs/ts-plugin` for TypeScript integration (default: v2.1.0)
3. Install `typescript` and `typescript-language-server` for the companion TS server

These packages are installed to `~/.serena/ls-resources/astro-lsp/` and are shared across all projects.

---

## Configuration (Optional)

You can customize versions in your `~/.serena/serena_config.yml`:

```yaml
ls_specific_settings:
  astro:
    astro_language_server_version: "2.16.2"
    astro_ts_plugin_version: "2.1.0"
  typescript:
    typescript_version: "5.9.3"
    typescript_language_server_version: "5.1.3"
```

---

## Supported File Types

- `.astro` - Astro components (frontmatter + template)
- `.ts`, `.tsx`, `.mts`, `.cts` - TypeScript files
- `.js`, `.jsx`, `.mjs`, `.cjs` - JavaScript files

---

## Features

- **Document Symbols**: Extract symbols from .astro and TypeScript files
- **Go to Definition**: Navigate to symbol definitions across files
- **Find References**: Find all usages of a symbol
- **Rename Symbol**: Rename symbols across the codebase
- **Cross-file Resolution**: TypeScript server with @astrojs/ts-plugin understands .astro imports

---

## Architecture

Serena uses a dual-server architecture for Astro projects:

1. **Astro Language Server**: Handles .astro file features (frontmatter, template syntax)
2. **Companion TypeScript Server**: Configured with `@astrojs/ts-plugin` for cross-file type resolution and references

This architecture ensures full IDE-like functionality for both Astro components and TypeScript modules.

---

## Troubleshooting

### Language server not starting

1. Verify Node.js is installed: `node --version`
2. Verify npm is installed: `npm --version`
3. Check logs for installation errors

### Missing cross-file references

The TypeScript server needs time to index .astro files. Wait a few seconds after opening a project
for full cross-file reference support.

### Version conflicts

If you encounter issues, try clearing the language server cache:

```bash
rm -rf ~/.serena/ls-resources/astro-lsp/
```

Serena will reinstall the packages on next startup.
