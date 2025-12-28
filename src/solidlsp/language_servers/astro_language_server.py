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

from overrides import override

from solidlsp import ls_types
from solidlsp.language_servers.common import RuntimeDependency, RuntimeDependencyCollection
from solidlsp.language_servers.typescript_language_server import (
    TypeScriptLanguageServer,
    prefer_non_node_modules_definition,
)
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_exceptions import SolidLSPException
from solidlsp.ls_utils import PathUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)

# Thread-local storage for passing executable path to classmethod during __init__
_astro_ts_thread_local = threading.local()


class AstroTypeScriptServer(TypeScriptLanguageServer):
    """TypeScript LS companion for Astro files.

    Unlike VueTypeScriptServer, this doesn't require @vue/typescript-plugin.
    Astro's language server handles TypeScript natively, but we still need
    a companion TypeScript server for cross-file type resolution.
    """

    @classmethod
    @override
    def get_language_enum_instance(cls) -> Language:
        """Return TYPESCRIPT since this is a TypeScript language server variant."""
        return Language.TYPESCRIPT

    @classmethod
    @override
    def _setup_runtime_dependencies(cls, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings) -> list[str]:
        # Use thread-local storage for thread-safe passing of executable path from __init__
        executable = getattr(_astro_ts_thread_local, "executable", None)
        if executable is not None:
            return executable
        return ["typescript-language-server", "--stdio"]

    @override
    def _get_language_id_for_file(self, relative_file_path: str) -> str:
        """Return the correct language ID for files.

        Astro files must be opened with language ID "astro" for proper processing.
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

    def __init__(
        self,
        config: LanguageServerConfig,
        repository_root_path: str,
        solidlsp_settings: SolidLSPSettings,
        astro_plugin_path: str,
        tsdk_path: str,
        ts_ls_executable_path: list[str],
    ):
        self._astro_plugin_path = astro_plugin_path
        self._custom_tsdk_path = tsdk_path
        # Use thread-local for thread-safe passing to classmethod
        _astro_ts_thread_local.executable = ts_ls_executable_path
        try:
            super().__init__(config, repository_root_path, solidlsp_settings)
        finally:
            _astro_ts_thread_local.executable = None

    @override
    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        params = super()._get_initialize_params(repository_absolute_path)

        # Configure Astro TypeScript plugin so tsserver understands .astro files
        params["initializationOptions"] = {
            "plugins": [
                {
                    "name": "@astrojs/ts-plugin",
                    "location": self._astro_plugin_path,
                    "languages": ["astro"],
                }
            ],
            "tsserver": {
                "path": self._custom_tsdk_path,
            },
        }

        if "workspace" in params["capabilities"]:
            params["capabilities"]["workspace"]["executeCommand"] = {"dynamicRegistration": True}

        return params

    @override
    def _start_server(self) -> None:
        def workspace_configuration_handler(params: dict) -> list:
            items = params.get("items", [])
            return [{} for _ in items]

        self.server.on_request("workspace/configuration", workspace_configuration_handler)
        super()._start_server()


class AstroLanguageServer(SolidLanguageServer):
    """
    Language server for Astro components using @astrojs/language-server with companion TypeScript LS.

    You can pass the following entries in ls_specific_settings["astro"]:
        - astro_language_server_version: Version of @astrojs/language-server to install (default: "2.16.2")

    Note: TypeScript versions are configured via ls_specific_settings["typescript"]:
        - typescript_version: Version of TypeScript to install (default: "5.9.3")
        - typescript_language_server_version: Version of typescript-language-server to install (default: "5.1.3")
    """

    TS_SERVER_READY_TIMEOUT = 5.0
    ASTRO_SERVER_READY_TIMEOUT = 3.0
    ASTRO_INDEXING_WAIT_TIME = 4.0 if os.name == "nt" else 2.0

    def __init__(self, config: LanguageServerConfig, repository_root_path: str, solidlsp_settings: SolidLSPSettings):
        astro_lsp_executable_path, self.tsdk_path, self._ts_ls_cmd = self._setup_runtime_dependencies(config, solidlsp_settings)
        self._astro_ls_dir = os.path.join(self.ls_resources_dir(solidlsp_settings), "astro-lsp")
        super().__init__(
            config,
            repository_root_path,
            ProcessLaunchInfo(cmd=astro_lsp_executable_path, cwd=repository_root_path),
            "astro",
            solidlsp_settings,
        )
        self.server_ready = threading.Event()
        self._ts_server: AstroTypeScriptServer | None = None
        self._ts_server_started = False
        self._astro_files_indexed = False
        self._indexed_astro_file_uris: list[str] = []

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        return super().is_ignored_dirname(dirname) or dirname in [
            "node_modules",
            "dist",
            ".astro",
        ]

    @override
    def _get_language_id_for_file(self, relative_file_path: str) -> str:
        ext = os.path.splitext(relative_file_path)[1].lower()
        if ext == ".astro":
            return "astro"
        elif ext in (".ts", ".tsx", ".mts", ".cts"):
            return "typescript"
        elif ext in (".js", ".jsx", ".mjs", ".cjs"):
            return "javascript"
        else:
            return "astro"

    def _is_typescript_file(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")

    def _find_all_astro_files(self) -> list[str]:
        astro_files = []
        repo_path = Path(self.repository_root_path)

        for astro_file in repo_path.rglob("*.astro"):
            try:
                relative_path = str(astro_file.relative_to(repo_path))
                if "node_modules" not in relative_path and not relative_path.startswith("."):
                    astro_files.append(relative_path)
            except Exception as e:
                log.debug(f"Error processing Astro file {astro_file}: {e}")

        return astro_files

    def _ensure_astro_files_indexed_on_ts_server(self) -> None:
        if self._astro_files_indexed:
            return

        if self._ts_server is None:
            raise SolidLSPException("TypeScript server not started - cannot index Astro files")
        log.info("Indexing .astro files on TypeScript server for cross-file references")
        astro_files = self._find_all_astro_files()
        log.debug(f"Found {len(astro_files)} .astro files to index")

        for astro_file in astro_files:
            try:
                with self._ts_server.open_file(astro_file) as file_buffer:
                    file_buffer.ref_count += 1
                    self._indexed_astro_file_uris.append(file_buffer.uri)
            except Exception as e:
                log.debug(f"Failed to open {astro_file} on TS server: {e}")

        self._astro_files_indexed = True
        log.info("Astro file indexing on TypeScript server complete")

        sleep(self._get_astro_indexing_wait_time())
        log.debug("Wait period after Astro file indexing complete")

    def _get_astro_indexing_wait_time(self) -> float:
        return self.ASTRO_INDEXING_WAIT_TIME

    def _send_ts_references_request(self, relative_file_path: str, line: int, column: int) -> list[ls_types.Location]:
        if self._ts_server is None:
            raise SolidLSPException("TypeScript server not initialized - cannot send references request")
        uri = PathUtils.path_to_uri(os.path.join(self.repository_root_path, relative_file_path))
        request_params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
            "context": {"includeDeclaration": True},
        }

        with self._ts_server.open_file(relative_file_path):
            response = self._ts_server.handler.send.references(request_params)  # type: ignore[arg-type]

        result: list[ls_types.Location] = []
        if response is not None:
            for item in response:
                abs_path = PathUtils.uri_to_path(item["uri"])
                if not Path(abs_path).is_relative_to(self.repository_root_path):
                    log.debug(f"Found reference outside repository: {abs_path}, skipping")
                    continue

                rel_path = Path(abs_path).relative_to(self.repository_root_path)
                if self.is_ignored_path(str(rel_path)):
                    log.debug(f"Ignoring reference in {rel_path}")
                    continue

                new_item: dict = {}
                new_item.update(item)  # type: ignore[arg-type]
                new_item["absolutePath"] = str(abs_path)
                new_item["relativePath"] = str(rel_path)
                result.append(ls_types.Location(**new_item))  # type: ignore

        return result

    @override
    def request_references(self, relative_file_path: str, line: int, column: int) -> list[ls_types.Location]:
        if not self.server_started:
            log.error("request_references called before Language Server started")
            raise SolidLSPException("Language Server not started")

        if not self._has_waited_for_cross_file_references:
            sleep(self._get_wait_time_for_cross_file_referencing())
            self._has_waited_for_cross_file_references = True

        self._ensure_astro_files_indexed_on_ts_server()
        return self._send_ts_references_request(relative_file_path, line=line, column=column)

    @override
    def request_definition(self, relative_file_path: str, line: int, column: int) -> list[ls_types.Location]:
        if not self.server_started:
            log.error("request_definition called before Language Server started")
            raise SolidLSPException("Language Server not started")

        if self._ts_server is None:
            raise SolidLSPException("TypeScript server not started - cannot request definition")
        with self._ts_server.open_file(relative_file_path):
            return self._ts_server.request_definition(relative_file_path, line, column)

    @override
    def request_rename_symbol_edit(self, relative_file_path: str, line: int, column: int, new_name: str) -> ls_types.WorkspaceEdit | None:
        if not self.server_started:
            log.error("request_rename_symbol_edit called before Language Server started")
            raise SolidLSPException("Language Server not started")

        if self._ts_server is None:
            raise SolidLSPException("TypeScript server not started - cannot request rename")
        with self._ts_server.open_file(relative_file_path):
            return self._ts_server.request_rename_symbol_edit(relative_file_path, line, column, new_name)

    @classmethod
    def _setup_runtime_dependencies(
        cls, config: LanguageServerConfig, solidlsp_settings: SolidLSPSettings
    ) -> tuple[list[str], str, list[str]]:
        is_node_installed = shutil.which("node") is not None
        if not is_node_installed:
            raise RuntimeError("node is not installed or isn't in PATH. Please install NodeJS and try again.")
        is_npm_installed = shutil.which("npm") is not None
        if not is_npm_installed:
            raise RuntimeError("npm is not installed or isn't in PATH. Please install npm and try again.")

        # Get TypeScript version settings from TypeScript language server settings
        typescript_config = solidlsp_settings.get_ls_specific_settings(Language.TYPESCRIPT)
        typescript_version = typescript_config.get("typescript_version", "5.9.3")
        typescript_language_server_version = typescript_config.get("typescript_language_server_version", "5.1.3")
        astro_config = solidlsp_settings.get_ls_specific_settings(Language.ASTRO)
        astro_language_server_version = astro_config.get("astro_language_server_version", "2.16.2")
        astro_ts_plugin_version = astro_config.get("astro_ts_plugin_version", "2.1.0")

        deps = RuntimeDependencyCollection(
            [
                RuntimeDependency(
                    id="astro-language-server",
                    description="Astro language server package",
                    command=["npm", "install", "--prefix", "./", f"@astrojs/language-server@{astro_language_server_version}"],
                    platform_id="any",
                ),
                RuntimeDependency(
                    id="astro-ts-plugin",
                    description="Astro TypeScript plugin for tsserver",
                    command=["npm", "install", "--prefix", "./", f"@astrojs/ts-plugin@{astro_ts_plugin_version}"],
                    platform_id="any",
                ),
                RuntimeDependency(
                    id="typescript",
                    description="TypeScript (required for tsdk)",
                    command=["npm", "install", "--prefix", "./", f"typescript@{typescript_version}"],
                    platform_id="any",
                ),
                RuntimeDependency(
                    id="typescript-language-server",
                    description="TypeScript language server",
                    command=[
                        "npm",
                        "install",
                        "--prefix",
                        "./",
                        f"typescript-language-server@{typescript_language_server_version}",
                    ],
                    platform_id="any",
                ),
            ]
        )

        astro_ls_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "astro-lsp")
        astro_executable_path = os.path.join(astro_ls_dir, "node_modules", ".bin", "astro-ls")
        ts_ls_executable_path = os.path.join(astro_ls_dir, "node_modules", ".bin", "typescript-language-server")

        if os.name == "nt":
            astro_executable_path += ".cmd"
            ts_ls_executable_path += ".cmd"

        tsdk_path = os.path.join(astro_ls_dir, "node_modules", "typescript", "lib")

        # Check if installation is needed based on executables AND version
        version_file = os.path.join(astro_ls_dir, ".installed_version")
        expected_version = (
            f"{astro_language_server_version}_{astro_ts_plugin_version}_{typescript_version}_{typescript_language_server_version}"
        )

        needs_install = False
        if not os.path.exists(astro_executable_path) or not os.path.exists(ts_ls_executable_path):
            log.info("Astro/TypeScript Language Server executables not found.")
            needs_install = True
        elif os.path.exists(version_file):
            with open(version_file, encoding="utf-8") as f:
                installed_version = f.read().strip()
            if installed_version != expected_version:
                log.info(
                    f"Astro Language Server version mismatch: installed={installed_version}, expected={expected_version}. Reinstalling..."
                )
                needs_install = True
        else:
            # No version file exists, assume old installation needs refresh
            log.info("Astro Language Server version file not found. Reinstalling to ensure correct version...")
            needs_install = True

        if needs_install:
            log.info("Installing Astro/TypeScript Language Server dependencies...")
            deps.install(astro_ls_dir)
            # Write version marker file
            with open(version_file, "w", encoding="utf-8") as f:
                f.write(expected_version)
            log.info("Astro language server dependencies installed successfully")

        if not os.path.exists(astro_executable_path):
            raise FileNotFoundError(
                f"astro-ls executable not found at {astro_executable_path}, something went wrong with the installation."
            )

        if not os.path.exists(ts_ls_executable_path):
            raise FileNotFoundError(
                f"typescript-language-server executable not found at {ts_ls_executable_path}, something went wrong with the installation."
            )

        return [astro_executable_path, "--stdio"], tsdk_path, [ts_ls_executable_path, "--stdio"]

    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "locale": "en",
            "capabilities": {
                "textDocument": {
                    "synchronization": {"didSave": True, "dynamicRegistration": True},
                    "completion": {"dynamicRegistration": True, "completionItem": {"snippetSupport": True}},
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "signatureHelp": {"dynamicRegistration": True},
                    "codeAction": {"dynamicRegistration": True},
                    "rename": {"dynamicRegistration": True, "prepareSupport": True},
                },
                "workspace": {
                    "workspaceFolders": True,
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "symbol": {"dynamicRegistration": True},
                },
            },
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
            "initializationOptions": {
                "typescript": {
                    "tsdk": self.tsdk_path,
                },
            },
        }
        return initialize_params  # type: ignore

    def _start_typescript_server(self) -> None:
        try:
            # Find the Astro TypeScript plugin path
            astro_ts_plugin_path = os.path.join(self._astro_ls_dir, "node_modules", "@astrojs", "ts-plugin")

            ts_config = LanguageServerConfig(
                code_language=Language.TYPESCRIPT,
                trace_lsp_communication=False,
            )

            log.info("Creating companion AstroTypeScriptServer")
            self._ts_server = AstroTypeScriptServer(
                config=ts_config,
                repository_root_path=self.repository_root_path,
                solidlsp_settings=self._solidlsp_settings,
                astro_plugin_path=astro_ts_plugin_path,
                tsdk_path=self.tsdk_path,
                ts_ls_executable_path=self._ts_ls_cmd,
            )

            log.info("Starting companion TypeScript server")
            self._ts_server.start()

            log.info("Waiting for companion TypeScript server to be ready...")
            if not self._ts_server.server_ready.wait(timeout=self.TS_SERVER_READY_TIMEOUT):
                log.warning(
                    f"Timeout waiting for companion TypeScript server to be ready after {self.TS_SERVER_READY_TIMEOUT} seconds, proceeding anyway"
                )
                self._ts_server.server_ready.set()

            self._ts_server_started = True
            log.info("Companion TypeScript server ready")
        except Exception as e:
            log.error(f"Error starting TypeScript server: {e}")
            self._ts_server = None
            self._ts_server_started = False
            raise

    def _cleanup_indexed_astro_files(self) -> None:
        if not self._indexed_astro_file_uris or self._ts_server is None:
            return

        log.debug(f"Cleaning up {len(self._indexed_astro_file_uris)} indexed Astro files")
        for uri in self._indexed_astro_file_uris:
            try:
                if uri in self._ts_server.open_file_buffers:
                    file_buffer = self._ts_server.open_file_buffers[uri]
                    file_buffer.ref_count -= 1

                    if file_buffer.ref_count == 0:
                        self._ts_server.server.notify.did_close_text_document({"textDocument": {"uri": uri}})
                        del self._ts_server.open_file_buffers[uri]
                        log.debug(f"Closed indexed Astro file: {uri}")
            except Exception as e:
                log.debug(f"Error closing indexed Astro file {uri}: {e}")

        self._indexed_astro_file_uris.clear()

    def _stop_typescript_server(self) -> None:
        if self._ts_server is not None:
            try:
                log.info("Stopping companion TypeScript server")
                self._ts_server.stop()
            except Exception as e:
                log.warning(f"Error stopping TypeScript server: {e}")
            finally:
                self._ts_server = None
                self._ts_server_started = False

    @override
    def _start_server(self) -> None:
        self._start_typescript_server()

        def register_capability_handler(params: dict) -> None:
            # Accept dynamic capability registrations from the server
            return

        def configuration_handler(params: dict) -> list:
            items = params.get("items", [])
            return [{} for _ in items]

        def do_nothing(params: dict) -> None:
            return

        def window_log_message(msg: dict) -> None:
            log.info(f"LSP: window/logMessage: {msg}")
            message_text = msg.get("message", "")
            if "initialized" in message_text.lower() or "ready" in message_text.lower():
                log.info("Astro language server ready signal detected")
                self.server_ready.set()
                self.completions_available.set()

        self.server.on_request("client/registerCapability", register_capability_handler)
        self.server.on_request("workspace/configuration", configuration_handler)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        log.info("Starting Astro server process")
        self.server.start()
        initialize_params = self._get_initialize_params(self.repository_root_path)

        log.info("Sending initialize request from LSP client to LSP server and awaiting response")
        init_response = self.server.send.initialize(initialize_params)
        log.debug(f"Received initialize response from Astro server: {init_response}")

        text_doc_sync = init_response.get("capabilities", {}).get("textDocumentSync")
        if text_doc_sync not in [1, 2]:
            log.warning(f"Unexpected textDocumentSync value: {text_doc_sync}. Expected 1 (Full) or 2 (Incremental).")

        self.server.notify.initialized({})

        log.info("Waiting for Astro language server to be ready...")
        if not self.server_ready.wait(timeout=self.ASTRO_SERVER_READY_TIMEOUT):
            log.info("Timeout waiting for Astro server ready signal, proceeding anyway")
            self.server_ready.set()
            self.completions_available.set()
        else:
            log.info("Astro server initialization complete")

    def _find_tsconfig_for_file(self, file_path: str) -> str | None:
        if not file_path:
            tsconfig_path = os.path.join(self.repository_root_path, "tsconfig.json")
            return tsconfig_path if os.path.exists(tsconfig_path) else None

        current_dir = os.path.dirname(file_path)
        repo_root = os.path.abspath(self.repository_root_path)

        while current_dir and current_dir.startswith(repo_root):
            tsconfig_path = os.path.join(current_dir, "tsconfig.json")
            if os.path.exists(tsconfig_path):
                return tsconfig_path
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent

        tsconfig_path = os.path.join(repo_root, "tsconfig.json")
        return tsconfig_path if os.path.exists(tsconfig_path) else None

    @override
    def _get_wait_time_for_cross_file_referencing(self) -> float:
        return 5.0

    @override
    def stop(self, shutdown_timeout: float = 5.0) -> None:
        self._cleanup_indexed_astro_files()
        self._stop_typescript_server()
        super().stop(shutdown_timeout)

    @override
    def _get_preferred_definition(self, definitions: list[ls_types.Location]) -> ls_types.Location:
        return prefer_non_node_modules_definition(definitions)
