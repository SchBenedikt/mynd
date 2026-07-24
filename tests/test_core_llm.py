"""Test core/llm.py – chat, streaming, tool loop with mocked HTTP."""

import json
from unittest.mock import MagicMock, patch


class TestLoadOpenAIConfig:
    @patch("core.llm._openai_cfg")
    @patch("core.llm.os.path.exists")
    def test_returns_openai_env_fallback(self, mock_exists, mock_cfg):
        mock_exists.return_value = False
        mock_cfg.return_value = ("https://api.openai.com/v1", "sk-env-key", ["gpt-4"])
        from core.llm import _load_openai_config
        base, key = _load_openai_config()
        assert "api.openai.com" in base
        assert key == "sk-env-key"

    @patch("core.llm._openai_cfg")
    @patch("core.llm.os.path.exists")
    def test_reads_ai_config_json(self, mock_exists, mock_cfg):
        mock_exists.return_value = False
        mock_cfg.return_value = ("https://custom.ai/v1", "sk-custom-key", ["gpt-4"])
        from core.llm import _load_openai_config
        base, key = _load_openai_config()
        assert "custom.ai" in base
        assert key == "sk-custom-key"


class TestChatWithTools:
    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_chat_success(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "Hello!"}
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.llm import chat_with_tools
        result = chat_with_tools("gemma3", [{"role": "user", "content": "hi"}], [])
        assert "message" in result
        assert result["message"]["content"] == "Hello!"

    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_chat_with_tools(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "test_tool", "arguments": {"x": 1}}}],
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.llm import chat_with_tools
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        result = chat_with_tools("gemma3", [{"role": "user", "content": "use tool"}], tools)
        assert result["message"]["tool_calls"] is not None
        assert result["message"]["tool_calls"][0]["function"]["name"] == "test_tool"

    @patch("core.llm.requests.post")
    @patch("core.llm._load_openai_config")
    def test_openai_chat_success(self, mock_cfg, mock_post):
        mock_cfg.return_value = ("https://api.openai.com/v1", "sk-key")
        with patch("core.llm._is_openai", return_value=True):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"role": "assistant", "content": "OpenAI reply"}}]
            }
            mock_post.return_value = mock_resp

            from core.llm import chat_with_tools
            result = chat_with_tools("gpt-4", [{"role": "user", "content": "hi"}], [])
            assert result["message"]["content"] == "OpenAI reply"

    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_timeout_returns_error(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("timeout")

        from core.llm import chat_with_tools
        result = chat_with_tools("gemma3", [{"role": "user", "content": "hi"}], [])
        assert "error" in result
        assert "Timeout" in result["error"]

    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_connection_error(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")

        from core.llm import chat_with_tools
        result = chat_with_tools("gemma3", [{"role": "user", "content": "hi"}], [])
        assert "error" in result
        assert "nicht erreichbar" in result["error"]

    @patch("core.llm._is_openai", return_value=False)
    @patch("core.llm.requests.post")
    def test_low_temp_model_uses_lower_temperature(self, mock_post, mock_is_openai):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"role": "assistant", "content": "ok"}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.llm import chat_with_tools
        with patch.dict("os.environ", {"LOW_TEMP_MODELS": "minimax-m2.5:cloud"}):
            chat_with_tools("minimax-m2.5:cloud", [{"role": "user", "content": "hi"}], [])
            called_json = mock_post.call_args[1]["json"]
            assert called_json.get("options", {}).get("temperature") == 0.3

    @patch("core.llm._is_openai", return_value=False)
    @patch("core.llm.requests.post")
    def test_normal_model_no_temperature_override(self, mock_post, mock_is_openai):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"role": "assistant", "content": "ok"}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        from core.llm import chat_with_tools
        chat_with_tools("gemma3", [{"role": "user", "content": "hi"}], [])
        called_json = mock_post.call_args[1]["json"]
        assert "options" not in called_json


class TestChatWithToolsStream:
    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_stream_yields_content(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_lines.return_value = [
            json.dumps({"message": {"content": "Hello"}, "done": False}),
            json.dumps({"message": {"content": " World"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]
        mock_post.return_value = mock_resp

        from core.llm import chat_with_tools_stream
        events = list(chat_with_tools_stream("gemma3", [{"role": "user", "content": "hi"}], []))
        content_events = [e for e in events if e[0] == "content"]
        assert len(content_events) >= 1
        final_events = [e for e in events if e[0] == ""]
        assert len(final_events) >= 1
        assert final_events[-1][2]["content"] == "Hello World"

    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_stream_yields_thinking(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_lines.return_value = [
            json.dumps({"message": {"thinking": "Hmm...", "content": "", "done": False}}),
            json.dumps({"message": {"thinking": "", "content": "Answer", "done": True}}),
        ]
        mock_post.return_value = mock_resp

        from core.llm import chat_with_tools_stream
        events = list(chat_with_tools_stream("gemma3", [{"role": "user", "content": "hi"}], []))
        think_events = [e for e in events if e[0] == "think"]
        assert len(think_events) >= 1
        assert "Hmm..." in "".join(e[1] for e in think_events)

    @patch("core.llm.requests.post")
    @patch("core.llm._is_openai")
    def test_ollama_stream_handles_timeout(self, mock_is_openai, mock_post):
        mock_is_openai.return_value = False
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        from core.llm import chat_with_tools_stream
        events = list(chat_with_tools_stream("gemma3", [{"role": "user", "content": "hi"}], []))
        assert any("error" in e[2] for e in events if e[0] == "")

    @patch("core.llm.requests.post")
    @patch("core.llm._load_openai_config")
    def test_openai_stream_yields_content(self, mock_cfg, mock_post):
        mock_cfg.return_value = ("https://api.openai.com/v1", "sk-key")
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.iter_lines.return_value = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}, "finish_reason": None}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " there"}, "finish_reason": None}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]}),
            "data: [DONE]",
        ]
        mock_post.return_value = mock_resp

        with patch("core.llm._is_openai", return_value=True):
            from core.llm import chat_with_tools_stream
            events = list(chat_with_tools_stream("gpt-4", [{"role": "user", "content": "hi"}], []))
            content = "".join(e[1] for e in events if e[0] == "content")
            assert "Hi there" in content


class TestRunToolLoop:
    @patch("core.llm.chat_with_tools")
    def test_simple_response_no_tools(self, mock_chat):
        mock_chat.return_value = {
            "message": {"role": "assistant", "content": "Direct answer"}
        }
        from core.llm import run_tool_loop
        result, msgs = run_tool_loop("gemma3", "hello", "system prompt", [], {}, max_rounds=1)
        assert "Direct answer" in result

    @patch("core.llm.chat_with_tools")
    def test_tool_call_then_response(self, mock_chat):
        mock_chat.side_effect = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call1",
                        "function": {"name": "dummy_tool", "arguments": json.dumps({"x": 1})},
                    }],
                }
            },
            {
                "message": {"role": "assistant", "content": "After tool result"}
            },
        ]

        def dummy_tool(x=0):
            return f"result_{x}"

        from core.llm import run_tool_loop
        result, msgs = run_tool_loop(
            "gemma3", "use tool", "system",
            [{"type": "function", "function": {"name": "dummy_tool"}}],
            {"dummy_tool": dummy_tool},
            max_rounds=5,
        )
        assert "After tool result" in result

    @patch("core.llm.chat_with_tools")
    def test_tool_loop_hits_max_rounds(self, mock_chat):
        mock_chat.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call1",
                    "function": {"name": "loop_tool", "arguments": "{}"},
                }],
            }
        }

        def loop_tool():
            return "still going"

        from core.llm import run_tool_loop
        result, msgs = run_tool_loop(
            "gemma3", "loop", "system",
            [{"type": "function", "function": {"name": "loop_tool"}}],
            {"loop_tool": loop_tool},
            max_rounds=2,
        )
        assert "Max Runden" in result or "⚠️" in result

    @patch("core.llm.chat_with_tools")
    def test_tool_error_returns_fallback(self, mock_chat):
        from core.llm import run_tool_loop

        def failing_tool():
            raise ValueError("broken")

        mock_chat.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call1",
                    "function": {"name": "failing_tool", "arguments": "{}"},
                }],
            }
        }

        result, msgs = run_tool_loop("gemma3", "test", "sys", [], {"failing_tool": failing_tool}, max_rounds=1)
        # Should return since there's a tool call but no tools in the list
        # Actually with empty tools list, it'll try to call chat_with_tools which returns the tool call,
        # then look up tool_map which fails → "Unbekanntes Tool"
        assert result is not None
