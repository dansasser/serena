"""
Basic tests for Astro language server functionality.

Tests cover:
- Symbol tree extraction from .astro files
- Cross-file reference finding between Astro and TypeScript
- Dual server coordination
- Reference deduplication

Template: test_vue_basic.py
"""

import os

import pytest

from solidlsp import SolidLanguageServer
from solidlsp.ls_config import Language
from solidlsp.ls_utils import SymbolUtils


@pytest.mark.astro
class TestAstroLanguageServer:
    """Core Astro language server functionality tests."""

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_astro_files_in_symbol_tree(self, language_server: SolidLanguageServer) -> None:
        """Test that .astro files appear in the symbol tree."""
        # TODO: Implement once AstroLanguageServer is complete
        # symbols = language_server.request_full_symbol_tree()
        # assert SymbolUtils.symbol_tree_contains_name(symbols, "Layout")
        # assert SymbolUtils.symbol_tree_contains_name(symbols, "Header")
        # assert SymbolUtils.symbol_tree_contains_name(symbols, "Footer")
        pytest.skip("AstroLanguageServer not yet implemented")

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_typescript_files_in_symbol_tree(self, language_server: SolidLanguageServer) -> None:
        """Test that TypeScript files in Astro project appear in symbol tree."""
        # TODO: Implement once AstroLanguageServer is complete
        # symbols = language_server.request_full_symbol_tree()
        # assert SymbolUtils.symbol_tree_contains_name(symbols, "createCounter")
        # assert SymbolUtils.symbol_tree_contains_name(symbols, "CounterStore")
        pytest.skip("AstroLanguageServer not yet implemented")

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_find_referencing_symbols(self, language_server: SolidLanguageServer) -> None:
        """Test cross-file reference finding between Astro components and TypeScript."""
        # TODO: Implement once AstroLanguageServer is complete
        # store_file = os.path.join("src", "stores", "counter.ts")
        # symbols = language_server.request_document_symbols(store_file).get_all_symbols_and_roots()
        # ... assertions for cross-file references
        pytest.skip("AstroLanguageServer not yet implemented")


@pytest.mark.astro
class TestAstroDualLspArchitecture:
    """Tests for TypeScript server coordination in Astro."""

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_typescript_server_starts(self, language_server: SolidLanguageServer) -> None:
        """Test that companion TypeScript server starts successfully."""
        # TODO: Verify TypeScript server is running
        pytest.skip("AstroLanguageServer not yet implemented")

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_astro_files_indexed_on_ts_server(self, language_server: SolidLanguageServer) -> None:
        """Test that .astro files are indexed on TypeScript server."""
        # TODO: Verify astro files are opened on TS server for cross-file refs
        pytest.skip("AstroLanguageServer not yet implemented")

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_reference_deduplication(self, language_server: SolidLanguageServer) -> None:
        """Test that references from both servers are deduplicated."""
        # TODO: Verify no duplicate references when querying
        pytest.skip("AstroLanguageServer not yet implemented")


@pytest.mark.astro
class TestAstroEdgeCases:
    """Edge case tests for Astro language server."""

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_empty_astro_file(self, language_server: SolidLanguageServer) -> None:
        """Test handling of empty .astro files."""
        pytest.skip("AstroLanguageServer not yet implemented")

    @pytest.mark.parametrize("language_server", [Language.ASTRO], indirect=True)
    def test_astro_without_frontmatter(self, language_server: SolidLanguageServer) -> None:
        """Test .astro files without frontmatter section."""
        pytest.skip("AstroLanguageServer not yet implemented")
