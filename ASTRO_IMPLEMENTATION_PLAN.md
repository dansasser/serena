# Astro Language Server Implementation Plan for Serena

## Executive Summary

This document provides a complete implementation blueprint for adding Astro language server support to the Serena codebase. Astro follows a hybrid architecture pattern similar to Vue, requiring both the Astro language server (@astrojs/language-server) and a companion TypeScript language server for handling TypeScript/JavaScript files within Astro components.

**Status**: Ready for implementation
**Target PR**: oraios/serena repository
**Estimated Complexity**: Medium (follows established Vue pattern)
**Files to Create**: 2 main files + test suite
**Files to Modify**: 2 files (ls_config.py, pyproject.toml)

---

## 1. Patterns & Conventions Found

### 1.1 Hybrid Language Server Architecture (Vue Pattern)

**File**: `src/solidlsp/language_servers/vue_language_server.py`

The Vue language server provides the exact architectural template for Astro:

#### Key Components:
1. **VueTypeScriptServer** (lines 36-122)
   - Extends TypeScriptLanguageServer
   - Configured with @vue/typescript-plugin
   - Returns Language.TYPESCRIPT enum
   - Custom language ID mapping for .vue files
   - Plugin initialization options

2. **VueLanguageServer** (lines 124-809)
   - Main orchestrator extending SolidLanguageServer
   - Manages dual server lifecycle:
     - Vue LS for .vue files
     - Companion TypeScript LS for .ts/.js files
   - File indexing for cross-file references
   - Request routing between servers

#### Critical Patterns:
```python
# Pattern 1: Companion TS server creation
def _start_typescript_server(self) -> None:
    # Create TypeScript server with plugin configuration
    # Start and wait for ready signal
    # Set flags for coordination

# Pattern 2: Reference deduplication
# Combines symbol refs from TS server + file refs from Vue server
# Deduplicates by (uri, line, character) tuple

# Pattern 3: Vue file indexing on TS server
# Opens all .vue files on TS server for cross-file type checking
# Maintains ref_count to prevent premature closure
```

### 1.2 Language Server Configuration (ls_config.py)

**File**: `src/solidlsp/ls_config.py`

#### Language Enum Pattern:
- Line 65: VUE = "vue" entry
- Priority system: Vue has priority=1 (superset language)
- File matcher: Includes .vue + all TypeScript/JavaScript extensions

#### FilenameMatcher Pattern:
```python
class FilenameMatcher:
    def __init__(self, *patterns: str) -> None:
        self.patterns = patterns

    def is_relevant_filename(self, fn: str) -> bool:
        # Uses fnmatch for pattern matching
```

### 1.3 Test Structure Pattern

**Directory**: `test/solidlsp/vue/`

#### Test Files:
1. `__init__.py` - Empty marker file
2. `test_vue_basic.py` - Core functionality tests
3. `test_vue_error_cases.py` - Error handling
4. `test_vue_rename.py` - Rename operations
5. `test_vue_symbol_retrieval.py` - Symbol operations

#### Test Markers (pyproject.toml):
```python
markers = [
    "vue: language server running for Vue (uses TypeScript LSP)",
]
```

#### Test Fixtures:
- Location: `test/resources/repos/vue/test_repo/`
- Structure: Full working project with package.json, tsconfig.json
- Components: src/components/, src/stores/, src/composables/
- 15 files total providing realistic test scenarios

### 1.4 Runtime Dependency Management

**Pattern from VueLanguageServer._setup_runtime_dependencies**:

```python
# 1. Check node/npm availability
# 2. Define RuntimeDependencyCollection with versioned packages
# 3. Version tracking via .installed_version file
# 4. Conditional installation based on version mismatch
# 5. Return executable paths (with .cmd extension for Windows)
```

---

## 2. Architecture Decision

### 2.1 Chosen Approach: Hybrid Dual-Server Architecture

**Rationale**:
- Astro files (.astro) contain HTML-like templates + JavaScript/TypeScript
- @astrojs/language-server handles .astro file parsing and features
- TypeScript language server provides type checking for embedded scripts
- Matches existing Vue pattern exactly

**Trade-offs**:
- [OK] Reuses proven Vue architecture
- [OK] Full TypeScript/JavaScript type support
- [OK] Cross-file reference resolution
- [OK] Minimal code duplication
- [WARN] Two language servers = higher memory usage (acceptable)
- [WARN] More complex startup sequence (mitigated by Vue patterns)

### 2.2 Alternative Approaches Rejected

1. **Standalone Astro LS only**
   - [FAIL] Limited TypeScript support in scripts
   - [FAIL] No cross-file type checking

2. **TypeScript LS only with Astro plugin**
   - [FAIL] May not exist as npm package
   - [FAIL] Less feature-complete than official @astrojs/language-server

---

## 3. Component Design

### 3.1 AstroTypeScriptServer

**File**: `src/solidlsp/language_servers/astro_language_server.py`
**Lines**: ~90 (similar to VueTypeScriptServer)

#### Responsibilities:
- Extend TypeScriptLanguageServer
- Configure TypeScript with Astro-specific settings
- Handle language ID mapping (.astro -> "astro", .ts -> "typescript", .js -> "javascript")
- Respond to workspace/configuration requests

#### Key Methods:
```python
@classmethod
def get_language_enum_instance(cls) -> Language:
    return Language.TYPESCRIPT  # Reports as TypeScript variant

def _get_language_id_for_file(self, relative_file_path: str) -> str:
    # Map .astro -> "astro", .ts -> "typescript", .js -> "javascript"

def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
    # Add Astro-specific initializationOptions if needed
```

### 3.2 AstroLanguageServer

**File**: `src/solidlsp/language_servers/astro_language_server.py`
**Lines**: ~700 (similar to VueLanguageServer)

#### Responsibilities:
- Main orchestrator for Astro language support
- Manage dual language server lifecycle
- Route requests to appropriate server (Astro vs TypeScript)
- Index .astro files on TypeScript server for cross-file references
- Deduplicate references from both servers

#### Key Methods:
```python
def __init__(self, config, repository_root_path, solidlsp_settings):
    # Setup runtime dependencies (Astro LS + TypeScript LS)
    # Initialize with Astro LS executable
    # Create threading events for coordination

def _start_typescript_server(self) -> None:
    # Create AstroTypeScriptServer instance
    # Start and wait for ready signal

def _find_all_astro_files(self) -> list[str]:
    # Recursively find .astro files
    # Exclude node_modules, dist, build

def _ensure_astro_files_indexed_on_ts_server(self) -> None:
    # Open all .astro files on TS server
    # Track URIs for cleanup

def request_references(self, relative_file_path, line, column) -> list[Location]:
    # Query TS server for symbol references
    # Combine with file-level references for .astro files
    # Deduplicate results

def request_definition(self, relative_file_path, line, column) -> list[Location]:
    # Delegate to TypeScript server

def request_rename_symbol_edit(self, relative_file_path, line, column, new_name):
    # Delegate to TypeScript server

@classmethod
def _setup_runtime_dependencies(cls, config, solidlsp_settings) -> tuple[list[str], str, list[str]]:
    # Install @astrojs/language-server
    # Install typescript
    # Install typescript-language-server
    # Return (astro_ls_cmd, tsdk_path, ts_ls_cmd)
```

#### Data Flow:
```
User Request (definition/references/rename)
    |
    v
AstroLanguageServer.request_*()
    |
    +-> .astro file: AstroTypeScriptServer (with open_file context)
    +-> .ts/.js file: AstroTypeScriptServer (direct)
    +-> Deduplicate results
    |
    v
Return Location[] to caller
```

### 3.3 Language Configuration Update

**File**: `src/solidlsp/ls_config.py`
**Modifications**:

#### Addition to Language Enum:
```python
class Language(str, Enum):
    # ... existing entries ...
    VUE = "vue"
    ASTRO = "astro"  # NEW
    POWERSHELL = "powershell"
    # ... rest of enum ...
```

#### Addition to get_priority():
```python
def get_priority(self) -> int:
    match self:
        case self.VUE:
            return 1
        case self.ASTRO:  # NEW
            return 1
        case _:
            return 2
```

#### Addition to get_source_fn_matcher():
```python
case self.ASTRO:
    path_patterns = ["*.astro"]
    # Include all TypeScript/JavaScript extensions
    for prefix in ["c", "m", ""]:
        for postfix in ["x", ""]:
            for base_pattern in ["ts", "js"]:
                path_patterns.append(f"*.{prefix}{base_pattern}{postfix}")
    return FilenameMatcher(*path_patterns)
```

#### Addition to get_ls_class():
```python
case self.ASTRO:
    from solidlsp.language_servers.astro_language_server import AstroLanguageServer
    return AstroLanguageServer
```

---

## 4. Implementation Map

### 4.1 Files to Create

#### File 1: `src/solidlsp/language_servers/astro_language_server.py`

**Size**: ~750 lines
**Template**: Copy from vue_language_server.py and adapt

**Changes from Vue**:
1. Class names: Vue -> Astro (VueLanguageServer -> AstroLanguageServer)
2. Package names: @vue/language-server -> @astrojs/language-server
3. File extensions: .vue -> .astro
4. Language IDs: "vue" -> "astro"
5. Plugin configuration: Remove @vue/typescript-plugin (Astro LS handles its own)
6. Version defaults:
   - astro_language_server_version: "2.15.7" (latest as of 2025)
   - typescript_version: "5.9.3" (same as Vue)
   - typescript_language_server_version: "5.1.3" (same as Vue)

#### File 2: `test/solidlsp/astro/__init__.py`

**Size**: 0 lines (empty marker file)

#### File 3: `test/solidlsp/astro/test_astro_basic.py`

**Size**: ~300 lines
**Template**: Copy from test_vue_basic.py

#### File 4: `test/solidlsp/astro/test_astro_symbol_retrieval.py`

**Size**: ~250 lines
**Template**: Adapt from test_vue_symbol_retrieval.py

#### File 5: `test/resources/repos/astro/test_repo/` (directory structure)

**Full structure**:
```
test_repo/
+-- package.json           # Astro + TypeScript dependencies
+-- tsconfig.json          # TypeScript configuration
+-- astro.config.mjs       # Astro configuration
+-- .gitignore
+-- src/
    +-- layouts/
    |   +-- Layout.astro   # Base layout component
    +-- components/
    |   +-- Header.astro   # Header component
    |   +-- Footer.astro   # Footer component
    +-- pages/
    |   +-- index.astro    # Main page
    +-- stores/
    |   +-- counter.ts     # TypeScript store
    +-- utils/
        +-- format.ts      # Utility functions
```

### 4.2 Files to Modify

#### File: `src/solidlsp/ls_config.py`

**Changes**:
1. Add `ASTRO = "astro"` to Language enum
2. Add `case self.ASTRO: return 1` to get_priority()
3. Add ASTRO case to get_source_fn_matcher()
4. Add ASTRO case to get_ls_class()

#### File: `pyproject.toml`

**Change**: Add pytest marker
```toml
markers = [
    # ... existing markers ...
    "astro: language server running for Astro (uses TypeScript LSP)",
]
```

---

## 5. Build Sequence

### Phase 1: Core Language Server Implementation
- [ ] Create `src/solidlsp/language_servers/astro_language_server.py`
- [ ] Implement AstroTypeScriptServer class
- [ ] Implement AstroLanguageServer class
- [ ] Implement _setup_runtime_dependencies()
- [ ] Implement _start_typescript_server()
- [ ] Implement _find_all_astro_files()
- [ ] Implement request_references() with deduplication
- [ ] Implement request_definition() delegation
- [ ] Implement request_rename_symbol_edit() delegation

### Phase 2: Configuration Integration
- [ ] Update `src/solidlsp/ls_config.py`:
  - [ ] Add Language.ASTRO enum entry
  - [ ] Add ASTRO case to get_priority()
  - [ ] Add ASTRO case to get_source_fn_matcher()
  - [ ] Add ASTRO case to get_ls_class()

### Phase 3: Test Infrastructure
- [ ] Create `test/solidlsp/astro/__init__.py`
- [ ] Create test repository structure:
  - [ ] `test/resources/repos/astro/test_repo/`
  - [ ] Add package.json
  - [ ] Add tsconfig.json
  - [ ] Add astro.config.mjs
  - [ ] Add .gitignore
- [ ] Create test fixtures:
  - [ ] src/layouts/Layout.astro
  - [ ] src/components/Header.astro
  - [ ] src/components/Footer.astro
  - [ ] src/pages/index.astro
  - [ ] src/stores/counter.ts
  - [ ] src/utils/format.ts

### Phase 4: Test Implementation
- [ ] Create `test/solidlsp/astro/test_astro_basic.py`
- [ ] Create `test/solidlsp/astro/test_astro_symbol_retrieval.py`

### Phase 5: Configuration Finalization
- [ ] Update `pyproject.toml` with "astro" pytest marker

### Phase 6: Validation
- [ ] Run `uv run poe format` (BLACK + RUFF formatting)
- [ ] Run `uv run poe type-check` (mypy validation)
- [ ] Run `uv run poe test -m astro` (Astro tests)
- [ ] Run `uv run poe test` (full test suite)
- [ ] Fix any formatting/type/test errors

### Phase 7: Documentation & PR
- [ ] Update README.md with Astro support mention
- [ ] Create PR with descriptive title and body

---

## 6. Critical Implementation Details

### 6.1 Error Handling Pattern

```python
# Startup error handling
try:
    self._ts_server = AstroTypeScriptServer(...)
    self._ts_server.start()
    if not self._ts_server.server_ready.wait(timeout=5.0):
        log.warning("Timeout waiting for TS server, proceeding anyway")
        self._ts_server.server_ready.set()
except Exception as e:
    log.error(f"Error starting TypeScript server: {e}")
    self._ts_server = None
    raise
```

### 6.2 State Management

```python
self.server_ready = threading.Event()  # Astro LS ready
self._ts_server_started = False        # TS server state
self._astro_files_indexed = False      # Indexing complete
self._indexed_astro_file_uris = []     # Track opened files
```

### 6.3 Timeout Values (from Vue)

```python
TS_SERVER_READY_TIMEOUT = 5.0
ASTRO_SERVER_READY_TIMEOUT = 3.0
ASTRO_INDEXING_WAIT_TIME = 4.0 if os.name == "nt" else 2.0
```

### 6.4 Ignored Directories

```python
def is_ignored_dirname(self, dirname: str) -> bool:
    return super().is_ignored_dirname(dirname) or dirname in [
        "node_modules",
        "dist",
        ".astro",
    ]
```

---

## 7. Test Fixtures

### package.json
```json
{
  "name": "astro-test-fixture",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "astro": "^5.1.0"
  },
  "devDependencies": {
    "@astrojs/language-server": "^2.15.7",
    "typescript": "~5.9.3"
  }
}
```

### astro.config.mjs
```javascript
import { defineConfig } from 'astro/config';

export default defineConfig({
  // Minimal config for testing
});
```

### tsconfig.json
```json
{
  "extends": "astro/tsconfigs/base",
  "compilerOptions": {
    "strict": true,
    "jsx": "preserve"
  }
}
```

### src/stores/counter.ts
```typescript
export interface CounterStore {
  count: number;
  increment: () => void;
  decrement: () => void;
}

export function createCounter(): CounterStore {
  let count = 0;

  return {
    get count() { return count; },
    increment() { count++; },
    decrement() { count--; }
  };
}
```

---

## 8. Next Steps

1. Start with Phase 1 - create astro_language_server.py stub
2. Progress through each phase sequentially
3. Run validation commands after each phase
4. Create PR when all phases complete
