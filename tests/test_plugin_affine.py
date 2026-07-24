"""Test AFFiNE plugin – Yjs binary generation, markdown parsing, cache helpers."""


from y_py import YDoc

from data.plugins.affine import (
    PROMPT_EXTRA,
    TOOL_MAP,
    TOOLS,
    _chunk_text,
    _decode_ydoc,
    _extract_all_text,
    _extract_title,
    _make_page_yjs_binary,
)

# ── Yjs Binary Generation ─────────────────────────────────────

class TestMakePageYjsBinary:
    def test_simple_markdown_creates_page_block(self):
        doc_id, binary, err = _make_page_yjs_binary("Test Title", "Hello World")
        assert err is None
        assert doc_id.startswith("mynd-")
        assert len(binary) > 50

        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        page = blocks.get(doc_id)
        assert page is not None
        assert page.get("sys:flavour") == "affine:page"
        assert page.get("prop:title") == "Test Title"

    def test_heading_block_creates_affine_heading(self):
        doc_id, binary, err = _make_page_yjs_binary("H", "# Big Heading")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:heading"
        assert block.get("prop:text") == "Big Heading"
        assert block.get("prop:level") == 1

    def test_todo_checked_creates_todo_block(self):
        doc_id, binary, err = _make_page_yjs_binary("T", "- [x] done task")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:list"
        assert block.get("prop:type") == "todo"
        assert block.get("prop:checked") is True

    def test_todo_unchecked_creates_todo_block(self):
        doc_id, binary, err = _make_page_yjs_binary("T", "- [ ] pending task")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:list"
        assert block.get("prop:type") == "todo"
        assert block.get("prop:checked") is False

    def test_bullet_list_creates_list_block(self):
        doc_id, binary, err = _make_page_yjs_binary("L", "- item one\n* item two")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        b0 = blocks.get(f"{doc_id}-b0")
        b1 = blocks.get(f"{doc_id}-b1")
        assert b0.get("sys:flavour") == "affine:list"
        assert b0.get("prop:type") == "bulleted"
        assert b0.get("prop:text") == "item one"
        assert b1.get("sys:flavour") == "affine:list"
        assert b1.get("prop:text") == "item two"

    def test_callout_block(self):
        doc_id, binary, err = _make_page_yjs_binary("C", "> note callout")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:callout"

    def test_divider_block(self):
        doc_id, binary, err = _make_page_yjs_binary("D", "---")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:divider"

    def test_code_block_with_language(self):
        doc_id, binary, err = _make_page_yjs_binary("C", "```python\nprint('hi')\n```")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:code"
        assert block.get("prop:language") == "python"
        assert "print('hi')" in block.get("prop:text", "")

    def test_paragraph_is_default(self):
        doc_id, binary, err = _make_page_yjs_binary("P", "just a paragraph")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        block = blocks.get(f"{doc_id}-b0")
        assert block.get("sys:flavour") == "affine:paragraph"

    def test_children_array_linked_correctly(self):
        doc_id, binary, err = _make_page_yjs_binary("T", "line1\nline2\nline3")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        page = blocks.get(doc_id)
        children = list(page.get("sys:children"))
        assert len(children) == 3
        for i, cid in enumerate(children):
            assert cid == f"{doc_id}-b{i}"
            assert blocks.get(cid) is not None

    def test_empty_markdown_produces_title_only(self):
        doc_id, binary, err = _make_page_yjs_binary("Empty", "")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        page = blocks.get(doc_id)
        children = list(page.get("sys:children") or [])
        assert len(children) == 0

    def test_heading_levels_preserved(self):
        doc_id, binary, err = _make_page_yjs_binary("HL", "# H1\n## H2\n### H3")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        for i, level in enumerate([1, 2, 3], 1):
            bid = f"{doc_id}-b{i-1}"
            b = blocks.get(bid)
            assert b.get("prop:level") == i, f"heading h{i} should have level {i}"


# ── Chunking ──────────────────────────────────────────────────

class TestChunkText:
    def test_single_chunk_under_limit(self):
        chunks = _chunk_text("hello world", title="t", size=600)
        assert len(chunks) == 1
        assert "hello world" in chunks[0]["text"]

    def test_chunk_splitting_respects_size(self):
        text = "\n".join([f"line {i}" for i in range(200)])
        chunks = _chunk_text(text, title="t", size=200)
        assert len(chunks) >= 2
        for c in chunks:
            assert c["title"] == "t"

    def test_headings_tracked_in_chunks(self):
        text = "# Intro\nsome content\n## Details\nmore here"
        chunks = _chunk_text(text, title="t", size=600)
        assert len(chunks) == 1
        headings = chunks[0]["headings"]
        assert len(headings) >= 2
        assert headings[0]["text"] == "Intro"
        assert headings[1]["text"] == "Details"

    def test_overlap_between_chunks(self):
        text = "\n".join([f"line_{i}" for i in range(100)])
        chunks = _chunk_text(text, title="t", size=150)
        assert len(chunks) >= 2
        # Overlap preserves last size//5 characters from previous chunk
        # With size=150, overlap is ~30 chars → ~4 lines of 7 bytes each
        if len(chunks) >= 2:
            c0_lines = chunks[0]["text"].split("\n")
            c1_lines = chunks[1]["text"].split("\n")
            # The first few lines of chunk 1 should match the end of chunk 0
            overlap_found = any(c1_lines[0] == c0_lines[-i] for i in range(1, 6))
            assert overlap_found, "Expected overlap between chunks"


# ── Yjs Decode & Extract ─────────────────────────────────────

class TestYjsHelpers:
    def test_decode_ydoc_valid_binary(self):
        doc_id, binary, err = _make_page_yjs_binary("D", "test")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        assert blocks.get(doc_id) is not None

    def test_decode_ydoc_invalid_binary(self):
        ydoc, blocks, err = _decode_ydoc(b"invalid data here")
        assert err is not None or blocks is None

    def test_extract_title_from_page(self):
        doc_id, binary, err = _make_page_yjs_binary("MyPageTitle", "")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        title = _extract_title(blocks)
        assert title == "MyPageTitle"

    def test_extract_title_no_page_block(self):
        ydoc = YDoc()
        blocks = ydoc.get_map("blocks")
        assert _extract_title(blocks) is None

    def test_extract_all_text_concatenates(self):
        doc_id, binary, err = _make_page_yjs_binary("T", "first\nsecond")
        assert err is None
        ydoc, blocks, decode_err = _decode_ydoc(binary)
        assert decode_err is None
        text = _extract_all_text(blocks)
        assert "first" in text
        assert "second" in text


# ── Cache Helpers ─────────────────────────────────────────────

class TestCacheHelpers:
    def test_content_cache_roundtrip(self, tmp_path):
        import data.plugins.affine as aff
        from data.plugins.affine import _load_content_cache, _save_content_cache
        orig = aff.CONTENT_CACHE_FILE
        test_file = tmp_path / "affine_content_cache_test.json"
        aff.CONTENT_CACHE_FILE = test_file
        try:
            _save_content_cache({"contents": {"doc1": {"title": "Test"}}})
            loaded = _load_content_cache()
            assert loaded["contents"]["doc1"]["title"] == "Test"
        finally:
            aff.CONTENT_CACHE_FILE = orig

    def test_cache_returns_empty_for_missing_file(self, tmp_path):
        import data.plugins.affine as aff
        orig = aff.CONTENT_CACHE_FILE
        test_file = tmp_path / "nonexistent.json"
        aff.CONTENT_CACHE_FILE = test_file
        try:
            from data.plugins.affine import _load_content_cache
            loaded = _load_content_cache()
            assert loaded == {"contents": {}}
        finally:
            aff.CONTENT_CACHE_FILE = orig


# ── Tool Schemas & Registration ───────────────────────────────

class TestToolSchemas:
    def test_all_tools_have_required_fields(self):
        for t in TOOLS:
            assert t["type"] == "function"
            fn = t["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["name"].startswith("affine_")

    def test_all_tool_names_unique(self):
        names = [t["function"]["name"] for t in TOOLS]
        assert len(names) == len(set(names))

    def test_tool_map_has_all_tools(self):
        for t in TOOLS:
            name = t["function"]["name"]
            assert name in TOOL_MAP, f"{name} missing from TOOL_MAP"
            assert callable(TOOL_MAP[name])

    def test_read_only_tools_have_no_parameters(self):
        for t in TOOLS:
            name = t["function"]["name"]
            if name in ("affine_list_workspaces", "affine_workspace_info",
                        "affine_list_pages", "affine_index_all", "affine_index_status"):
                assert t["function"]["parameters"]["properties"] == {}

    def test_search_tools_have_query_parameter(self):
        for t in TOOLS:
            name = t["function"]["name"]
            if name in ("affine_search", "affine_search_content"):
                params = t["function"]["parameters"]["properties"]
                assert "query_text" in params

    def test_create_tool_has_title_and_content(self):
        for t in TOOLS:
            name = t["function"]["name"]
            if name == "affine_create_page":
                params = t["function"]["parameters"]["properties"]
                assert "title" in params
                assert "content" in params
                assert "workspace_id" in params

    def test_delete_tool_has_page_id(self):
        for t in TOOLS:
            name = t["function"]["name"]
            if name == "affine_delete_page":
                params = t["function"]["parameters"]["properties"]
                assert "page_id" in params


# ── PROMPT_EXTRA ──────────────────────────────────────────────

class TestPromptExtra:
    def test_prompt_extra_mentions_all_tools(self):
        for t in TOOLS:
            name = t["function"]["name"]
            assert name in PROMPT_EXTRA, f"{name} not mentioned in PROMPT_EXTRA"

    def test_prompt_extra_has_workflow_instructions(self):
        assert "search_documents()" in PROMPT_EXTRA
        assert "affine_search_content" in PROMPT_EXTRA
        assert "affine_index_all()" in PROMPT_EXTRA

    def test_prompt_extra_prioritizes_affine_over_web(self):
        assert "NICHT sofort das Internet" in PROMPT_EXTRA
        assert "1. **affine_search()**" in PROMPT_EXTRA
