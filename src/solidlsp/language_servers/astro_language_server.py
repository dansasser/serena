"""
Astro Language Server implementation using @astrojs/language-server with companion TypeScript LS.

This implementation follows the same hybrid architecture as Vue:
- AstroTypeScriptServer: TypeScript LS for type checking and cross-file references
- AstroLanguageServer: Astro LS for .astro file features + coordination

Reference: vue_language_server.py for the pattern template.
"""

import logging
import os
import pathlib
import shutil
import threading
from pathlib import Path
from time import sleep
from typing import Any

from overrides import override

from solidlsp import ls_types
from solidlsp.language_servers.common import RuntimeDependency, RuntimeDependencyCollection
from solidlsp.language_servers.typescript_language_server import (
    TypeScriptLanguageServer,
    prefer_non_node_modules_definition,
)
from solidlsp.ls import LSPFileBuffer, SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_exceptions import SolidLSPException
from solidlsp.ls_types import Location
from solidlsp.ls_utils import PathUtils
from solidlsp.lsp_protocol_handler import lsp_types
from solidlsp.lsp_protocol_handler.lsp_types import DocumentSymbol, InitializeParams, SymbolInformation
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings


log = logging.getLogger(__name__)


class AstroTypeScriptServer(TypeScriptLanguageServer):
    """
    TypeScript Language Server companion for Astro files.

    Provides type checking and cross-file reference resolution for TypeScript/JavaScript
    code within Astro components. Similar to VueTypeScriptServer.

    TODO: Implement following vue_language_server.py pattern:
    - Override get_language_enum_instance() to return Language.TYPESCRIPT
    - Override _get_language_id_for_file() for .astro -> "astro" mapping
    - Override _get_initialize_params() for Astro-specific initialization
    - Handle workspace/configuration requests
    """

    def __init__(
        self,
        config: LanguageServerConfig,
        repository_root_path: str,
        solidlsp_settings: SolidLSPSettings,
        tsdk_path: str,
    ) -> None:
        # TODO: Initialize with Astro-specific TypeScript configuration
        # See VueTypeScriptServer.__init__ for pattern
        raise NotImplementedError("AstroTypeScriptServer not yet implemented")

    @classmethod
    def get_language_enum_instance(cls) -> Language:
        """Return TYPESCRIPT since this is a TypeScript variant server."""
        return Language.TYPESCRIPT

    def _get_language_id_for_file(self, relative_file_path: str) -> str:
        """
        Map file extensions to language IDs.

        .astro -> "astro"
        .ts/.tsx/.mts/.cts -> "typescript"
        .js/.jsx/.mjs/.cjs -> "javascript"
        """
        ext = os.path.splitext(relative_file_path)[1].lower()
        if ext == ".astro":
            return "astro"
        elif ext in (".ts", ".tsx", ".mts", ".cts"):
            return "typescript"
        elif ext in (".js", ".jsx", ".mjs", ".cjs"):
            return "javascript"
        else:
            return "typescript"

    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        """Get initialization parameters for Astro TypeScript server."""
        # TODO: Implement Astro-specific initialization options
        raise NotImplementedError()


class AstroLanguageServer(SolidLanguageServer):
    """
    Language server for Astro components with companion TypeScript LS.

    Architecture:
    - Main Astro LS: Handles .astro file features (syntax, completions, etc.)
    - Companion TypeScript LS: Provides type checking and cross-file references

    This follows the same dual-server pattern as VueLanguageServer.

    TODO: Implement following vue_language_server.py pattern:
    - __init__: Setup runtime dependencies and threading events
    - _setup_runtime_dependencies: Install @astrojs/language-server + typescript
    - _start_typescript_server: Create and start AstroTypeScriptServer
    - _find_all_astro_files: Recursively find .astro files
    - _ensure_astro_files_indexed_on_ts_server: Index files for cross-file refs
    - request_references: Combine refs from both servers, deduplicate
    - request_definition: Delegate to TypeScript server
    - request_rename_symbol_edit: Delegate to TypeScript server
    """

    # Version defaults for runtime dependencies
    DEFAULT_ASTRO_LS_VERSION = "2.15.7"
    DEFAULT_TYPESCRIPT_VERSION = "5.9.3"
    DEFAULT_TS_LS_VERSION = "5.1.3"

    # Timeout values
    TS_SERVER_READY_TIMEOUT = 5.0
    ASTRO_SERVER_READY_TIMEOUT = 3.0
    ASTRO_INDEXING_WAIT_TIME = 4.0 if os.name == "nt" else 2.0

    def __init__(
        self,
        config: LanguageServerConfig,
        repository_root_path: str,
        solidlsp_settings: SolidLSPSettings,
    ) -> None:
        """
        Initialize Astro language server with dual-server architecture.

        TODO: Implement following vue_language_server.py __init__ pattern:
        1. Call _setup_runtime_dependencies to get executables
        2. Create ProcessLaunchInfo for Astro LS
        3. Initialize threading events for coordination
        4. Call super().__init__
        5. Store TS server config for later creation
        """
        raise NotImplementedError("AstroLanguageServer not yet implemented")

    @classmethod
    def get_language_enum_instance(cls) -> Language:
        """Return ASTRO language enum."""
        return Language.ASTRO

    @classmethod
    def _setup_runtime_dependencies(
        cls,
        config: LanguageServerConfig,
        solidlsp_settings: SolidLSPSettings,
    ) -> tuple[list[str], str, list[str]]:
        """
        Install runtime dependencies and return executable paths.

        Returns:
            Tuple of (astro_ls_cmd, tsdk_path, ts_ls_cmd)

        TODO: Implement following vue_language_server.py pattern:
        1. Check node/npm availability
        2. Get versions from config or defaults
        3. Create RuntimeDependencyCollection with:
           - @astrojs/language-server
           - typescript
           - typescript-language-server
        4. Check .installed_version for cached installs
        5. Install if needed
        6. Return executable paths (handle .cmd for Windows)
        """
        raise NotImplementedError()

    def _start_typescript_server(self) -> None:
        """
        Create and start the companion TypeScript server.

        TODO: Implement following vue_language_server.py pattern:
        1. Create AstroTypeScriptServer instance
        2. Start the server
        3. Wait for server_ready event with timeout
        4. Set _ts_server_started flag
        """
        raise NotImplementedError()

    def _find_all_astro_files(self) -> list[str]:
        """
        Recursively find all .astro files in the repository.

        Returns:
            List of relative paths to .astro files

        TODO: Implement:
        1. Walk repository_root_path
        2. Filter for .astro extension
        3. Exclude node_modules, dist, .astro directories
        4. Return relative paths
        """
        raise NotImplementedError()

    def _ensure_astro_files_indexed_on_ts_server(self) -> None:
        """
        Open all .astro files on TypeScript server for cross-file type checking.

        TODO: Implement following vue_language_server.py pattern:
        1. If already indexed, return early
        2. Find all astro files
        3. Open each on TypeScript server
        4. Track URIs for later cleanup
        5. Set _astro_files_indexed flag
        """
        raise NotImplementedError()

    @override
    def request_references(
        self,
        relative_file_path: str,
        line: int,
        column: int,
    ) -> list[Location]:
        """
        Find all references to symbol at position.

        Combines references from:
        1. TypeScript server (symbol references)
        2. Astro server (file references for .astro files)

        Deduplicates by (uri, line, character) tuple.

        TODO: Implement following vue_language_server.py pattern
        """
        raise NotImplementedError()

    @override
    def request_definition(
        self,
        relative_file_path: str,
        line: int,
        column: int,
    ) -> list[Location]:
        """
        Find definition of symbol at position.

        Delegates to TypeScript server for type-aware definition lookup.

        TODO: Implement following vue_language_server.py pattern
        """
        raise NotImplementedError()

    @override
    def request_rename_symbol_edit(
        self,
        relative_file_path: str,
        line: int,
        column: int,
        new_name: str,
    ) -> lsp_types.WorkspaceEdit | None:
        """
        Rename symbol at position across all files.

        Delegates to TypeScript server for cross-file rename.

        TODO: Implement following vue_language_server.py pattern
        """
        raise NotImplementedError()

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        """Check if directory should be ignored during file scanning."""
        return super().is_ignored_dirname(dirname) or dirname in [
            "node_modules",
            "dist",
            ".astro",
        ]

    def stop(self, shutdown_timeout: float = 5.0) -> None:
        """
        Shutdown both Astro and TypeScript servers.

        TODO: Implement:
        1. Cleanup indexed astro files
        2. Stop TypeScript server
        3. Call super().stop()
        """
        raise NotImplementedError()
