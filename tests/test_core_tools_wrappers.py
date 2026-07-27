import json
from unittest.mock import patch


class TestPlannerWrappers:
    @patch("core.tools._plan_create", return_value=("plan-id-1", "Plan: step1\nstep2"))
    def test_create_plan_returns_formatted_output(self, mock_create):
        from core.tools import create_plan

        result = create_plan(steps="step1\nstep2", description="test")
        assert "plan-id-1" in result
        assert "📋" in result
        mock_create.assert_called_once_with("step1\nstep2", description="test")

    @patch("core.tools._plan_create", return_value=("", "Direct error message"))
    def test_create_plan_passthrough_when_no_id(self, mock_create):
        from core.tools import create_plan

        result = create_plan(steps="x", description="")
        assert result == "Direct error message"

    @patch("core.tools._plan_create", side_effect=Exception("internal error"))
    def test_create_plan_handles_exception(self, mock_create):
        from core.tools import create_plan

        result = create_plan(steps="step1", description="test")
        assert "❌" in result
        assert "fehlgeschlagen" in result

    @patch("core.tools._plan_create")
    def test_create_plan_validates_steps_length(self, mock_create):
        from core.tools import create_plan

        result = create_plan(steps="x" * 50001, description="test")
        assert "❌" in result
        mock_create.assert_not_called()

    @patch("core.tools._plan_create")
    def test_create_plan_validates_description_length(self, mock_create):
        from core.tools import create_plan

        result = create_plan(steps="step1", description="x" * 5001)
        assert "❌" in result
        mock_create.assert_not_called()

    @patch("core.tools._plan_get", return_value=(None, "Plan details here"))
    def test_get_plan_returns_result(self, mock_get):
        from core.tools import get_plan

        result = get_plan("plan-123")
        assert "Plan details here" in result
        mock_get.assert_called_once_with("plan-123")

    @patch("core.tools._plan_get", side_effect=Exception("fail"))
    def test_get_plan_handles_exception(self, mock_get):
        from core.tools import get_plan

        result = get_plan("plan-123")
        assert "❌" in result

    @patch("core.tools._plan_update")
    def test_update_plan_step_passes_correct_args(self, mock_update):
        from core.tools import update_plan_step

        update_plan_step("plan-1", 3, "completed", result="all good")
        mock_update.assert_called_once_with("plan-1", 3, "completed", result="all good")

    @patch("core.tools._plan_update")
    def test_update_plan_step_converts_step_id(self, mock_update):
        from core.tools import update_plan_step

        update_plan_step("plan-1", "3", "completed")
        mock_update.assert_called_once_with("plan-1", 3, "completed", result="")

    @patch("core.tools._plan_update", side_effect=Exception("fail"))
    def test_update_plan_step_handles_exception(self, mock_update):
        from core.tools import update_plan_step

        result = update_plan_step("plan-1", 1, "done")
        assert "❌" in result

    @patch("core.tools._plan_list", return_value=[
        {"id": "p1", "status": "active", "progress": "2/5", "description": "a test plan"},
    ])
    def test_list_plans_formats_output(self, mock_list):
        from core.tools import list_plans

        result = list_plans(status="active")
        assert "p1" in result
        assert "active" in result
        assert "📋" in result
        mock_list.assert_called_once_with(status="active")

    @patch("core.tools._plan_list", return_value=[])
    def test_list_plans_empty(self, mock_list):
        from core.tools import list_plans

        result = list_plans()
        assert "Keine" in result

    @patch("core.tools._plan_list", side_effect=Exception("fail"))
    def test_list_plans_handles_exception(self, mock_list):
        from core.tools import list_plans

        result = list_plans()
        assert "❌" in result

    @patch("core.tools._plan_delete")
    def test_delete_plan_calls_underlying(self, mock_delete):
        from core.tools import delete_plan

        delete_plan("plan-1")
        mock_delete.assert_called_once_with("plan-1")

    @patch("core.tools._plan_delete", side_effect=Exception("fail"))
    def test_delete_plan_handles_exception(self, mock_delete):
        from core.tools import delete_plan

        result = delete_plan("plan-1")
        assert "❌" in result


class TestReflectionWrappers:
    @patch("core.tools.get_failure_analysis", return_value="Analysis: tool x failed 3 times")
    def test_reflect_on_failure_returns_analysis(self, mock_analysis):
        from core.tools import reflect_on_failure

        result = reflect_on_failure(tool_name="tool_x", max_recent=3)
        assert result == "Analysis: tool x failed 3 times"
        mock_analysis.assert_called_once_with(tool_name="tool_x", max_recent=3)

    @patch("core.tools.get_failure_analysis", return_value="")
    def test_reflect_on_failure_no_patterns(self, mock_analysis):
        from core.tools import reflect_on_failure

        result = reflect_on_failure(tool_name="tool_x")
        assert "Keine" in result

    @patch("core.tools.get_tool_performance", return_value={
        "tool_a": {"success_rate": 85.0, "calls": 20, "avg_ms": 150.0, "max_ms": 500},
        "tool_b": {"success_rate": 40.0, "calls": 5, "avg_ms": 2000.0, "max_ms": 8000},
    })
    def test_analyze_performance_formats_output(self, mock_perf):
        from core.tools import analyze_performance

        result = analyze_performance(tool_name="tool_a")
        assert "tool_a" in result or "tool_b" in result
        assert "85%" in result
        assert "📊" in result
        mock_perf.assert_called_once_with(tool_name="tool_a")

    @patch("core.tools.get_tool_performance", return_value={})
    def test_analyze_performance_no_data(self, mock_perf):
        from core.tools import analyze_performance

        result = analyze_performance()
        assert "Keine" in result

    @patch("core.tools.get_tool_performance", side_effect=Exception("fail"))
    def test_analyze_performance_handles_exception(self, mock_perf):
        from core.tools import analyze_performance

        result = analyze_performance()
        assert "❌" in result

    @patch("core.tools._reflection_suggestions", return_value="Suggestion: refactor tool X")
    def test_get_improvement_suggestions(self, mock_suggest):
        from core.tools import get_improvement_suggestions

        result = get_improvement_suggestions()
        assert result == "Suggestion: refactor tool X"

    @patch("core.tools._reflection_suggestions", side_effect=Exception("fail"))
    def test_get_improvement_suggestions_handles_exception(self, mock_suggest):
        from core.tools import get_improvement_suggestions

        result = get_improvement_suggestions()
        assert "❌" in result

    @patch("core.tools._reflection_daily", return_value="Daily: 42 calls, 95% success")
    def test_get_daily_summary(self, mock_daily):
        from core.tools import get_daily_summary

        result = get_daily_summary()
        assert result == "Daily: 42 calls, 95% success"

    @patch("core.tools._reflection_daily", side_effect=Exception("fail"))
    def test_get_daily_summary_handles_exception(self, mock_daily):
        from core.tools import get_daily_summary

        result = get_daily_summary()
        assert "❌" in result

    @patch("core.tools._reflection_prune")
    def test_prune_history_passes_days(self, mock_prune):
        from core.tools import prune_history

        prune_history(days=60)
        mock_prune.assert_called_once_with(days=60)

    @patch("core.tools._reflection_prune", side_effect=Exception("fail"))
    def test_prune_history_handles_exception(self, mock_prune):
        from core.tools import prune_history

        result = prune_history()
        assert "❌" in result


class TestResetFailures:
    @patch("core.reflection._load")
    @patch("core.reflection._save", create=True)
    def test_reset_failures_all(self, mock_save, mock_load):
        mock_load.return_value = {"consecutive_failures": {"t1": 3, "t2": 1}}
        from core.tools import reset_failures

        result = reset_failures()
        assert "✅" in result
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["consecutive_failures"] == {}

    @patch("core.reflection._load")
    @patch("core.reflection._save", create=True)
    def test_reset_failures_single_tool(self, mock_save, mock_load):
        mock_load.return_value = {"consecutive_failures": {"t1": 3, "t2": 1}}
        from core.tools import reset_failures

        result = reset_failures(tool_name="t1")
        assert "✅" in result
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert "t1" not in saved["consecutive_failures"]
        assert saved["consecutive_failures"]["t2"] == 1

    @patch("core.reflection._load")
    @patch("core.reflection._save", create=True)
    def test_reset_failures_unknown_tool(self, mock_save, mock_load):
        mock_load.return_value = {"consecutive_failures": {"t1": 3}}
        from core.tools import reset_failures

        result = reset_failures(tool_name="nonexistent")
        assert "✅" in result
        saved = mock_save.call_args[0][0]
        assert "t1" in saved["consecutive_failures"]

    @patch("core.reflection._load")
    @patch("core.reflection._save", create=True)
    def test_reset_failures_empty_data(self, mock_save, mock_load):
        mock_load.return_value = {"consecutive_failures": {}}
        from core.tools import reset_failures

        result = reset_failures(tool_name="t1")
        assert "✅" in result


class TestSkillWrappers:
    @patch("core.tools._learn_skill")
    def test_learn_skill_passthrough(self, mock_learn):
        from core.tools import learn_skill

        learn_skill("my_skill", "A skill", [{"tool": "bash"}], tags="tag1,tag2", context="ctx")
        mock_learn.assert_called_once_with(
            "my_skill", "A skill", [{"tool": "bash"}], tags=["tag1", "tag2"], context="ctx"
        )

    @patch("core.tools._learn_skill")
    def test_learn_skill_parses_json_steps(self, mock_learn):
        from core.tools import learn_skill

        steps_json = '[{"tool": "bash", "args": {"command": "ls"}}]'
        learn_skill("s", "d", steps_json)
        mock_learn.assert_called_once_with(
            "s", "d", [{"tool": "bash", "args": {"command": "ls"}}], tags=[], context=""
        )

    @patch("core.tools._learn_skill")
    def test_learn_skill_rejects_invalid_json_steps(self, mock_learn):
        from core.tools import learn_skill

        result = learn_skill("s", "d", "not valid json")
        assert "❌" in result
        mock_learn.assert_not_called()

    @patch("core.tools._learn_skill")
    def test_learn_skill_validates_name(self, mock_learn):
        from core.tools import learn_skill

        result = learn_skill("x" * 501, "d", [])
        assert "❌" in result
        mock_learn.assert_not_called()

    @patch("core.tools._recall_skills", return_value=[
        {"name": "s1", "description": "desc1", "relevance": 8.0, "tags": ["t1"], "pattern": [1, 2]},
    ])
    def test_recall_skills_formats_output(self, mock_recall):
        from core.tools import recall_skills

        result = recall_skills("find files", max_results=3)
        assert "s1" in result
        assert "desc1" in result
        assert "⭐" in result
        assert "Schritte" in result
        mock_recall.assert_called_once_with("find files", max_results=3)

    @patch("core.tools._recall_skills", return_value=[])
    def test_recall_skills_no_results(self, mock_recall):
        from core.tools import recall_skills

        result = recall_skills("nothing")
        assert "Keine" in result

    @patch("core.tools._recall_skills")
    def test_recall_skills_validates_context(self, mock_recall):
        from core.tools import recall_skills

        result = recall_skills("x" * 100001)
        assert "❌" in result
        mock_recall.assert_not_called()

    @patch("core.tools._skill_list", return_value=[
        {"name": "s1", "description": "desc1", "tags": []},
        {"name": "s2", "description": "desc2", "tags": ["bash"]},
    ])
    def test_list_skills_formats_output(self, mock_list):
        from core.tools import list_skills

        result = list_skills(tag="bash")
        assert "s1" in result
        assert "s2" in result
        assert "Skills" in result
        assert "📋" in result

    @patch("core.tools._skill_list", return_value=[])
    def test_list_skills_empty(self, mock_list):
        from core.tools import list_skills

        result = list_skills()
        assert "Keine" in result

    @patch("core.tools._skill_delete")
    def test_delete_skill(self, mock_delete):
        from core.tools import delete_skill

        delete_skill("my_skill")
        mock_delete.assert_called_once_with("my_skill")

    @patch("core.tools._skill_delete")
    def test_delete_skill_validates_name(self, mock_delete):
        from core.tools import delete_skill

        result = delete_skill(123)
        assert "❌" in result
        mock_delete.assert_not_called()


class TestToolCreatorWrappers:
    @patch("core.tools._create_tool")
    def test_create_tool_passthrough(self, mock_create):
        from core.tools import create_tool

        create_tool("my_tool", "Does X", {"param1": "str"}, "def run(): pass")
        mock_create.assert_called_once_with("my_tool", "Does X", {"param1": "str"}, "def run(): pass")

    @patch("core.tools._create_tool")
    def test_create_tool_validates_name(self, mock_create):
        from core.tools import create_tool

        result = create_tool(123, "desc", {}, "code")
        assert "❌" in result
        mock_create.assert_not_called()

    @patch("core.tools._create_tool")
    def test_create_tool_validates_description(self, mock_create):
        from core.tools import create_tool

        result = create_tool("n", "x" * 5001, {}, "code")
        assert "❌" in result
        mock_create.assert_not_called()

    @patch("core.tools._create_tool")
    def test_create_tool_validates_code(self, mock_create):
        from core.tools import create_tool

        result = create_tool("n", "desc", {}, "x" * 100001)
        assert "❌" in result
        mock_create.assert_not_called()

    @patch("core.tools._delete_tool")
    def test_delete_tool(self, mock_delete):
        from core.tools import delete_tool

        delete_tool("my_tool")
        mock_delete.assert_called_once_with("my_tool")

    @patch("core.tools._delete_tool")
    def test_delete_tool_validates_name(self, mock_delete):
        from core.tools import delete_tool

        result = delete_tool(123)
        assert "❌" in result
        mock_delete.assert_not_called()

    @patch("core.tools._list_created_tools", return_value=["tool1", "tool2"])
    def test_list_created_tools(self, mock_list):
        from core.tools import list_created_tools

        result = list_created_tools()
        assert result == ["tool1", "tool2"]
        mock_list.assert_called_once()


class TestMemoryWrappers:
    def test_memory_get_with_key(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text(json.dumps({"foo": "bar"}))
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_get

        result = memory_get(key="foo")
        assert result == "bar"

    def test_memory_get_no_key_returns_all(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text(json.dumps({"a": "1", "b": "2"}))
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_get

        result = memory_get(key="")
        assert "a" in result
        assert "b" in result

    def test_memory_get_empty_store(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text("{}")
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_get

        result = memory_get(key="")
        assert "leer" in result

    def test_memory_get_not_found(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text("{}")
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_get

        result = memory_get(key="nonexistent")
        assert result == ""

    def test_memory_get_missing_file(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_get

        result = memory_get(key="foo")
        assert result == ""

    def test_memory_get_corrupt_file(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text("invalid json{{{")
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_get

        result = memory_get(key="foo")
        assert "❌" in result

    def test_memory_set_stores_value(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text("{}")
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_set

        result = memory_set(key="test_key", value="test_value")
        assert "✅" in result
        assert json.loads(mem_file.read_text())["test_key"] == "test_value"

    def test_memory_set_creates_file_if_missing(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_set

        result = memory_set(key="k", value="v")
        assert "✅" in result
        assert mem_file.exists()
        assert json.loads(mem_file.read_text()) == {"k": "v"}

    def test_memory_set_overwrites_existing(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text(json.dumps({"old": "data"}))
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_set

        result = memory_set(key="old", value="updated")
        assert "✅" in result
        assert json.loads(mem_file.read_text())["old"] == "updated"

    def test_memory_set_validates_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.tools.MEMORY_FILE", tmp_path / "memory.json")
        from core.tools import memory_set

        result = memory_set(key=123, value="v")
        assert "❌" in result

    def test_memory_set_validates_value_length(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.tools.MEMORY_FILE", tmp_path / "memory.json")
        from core.tools import memory_set

        result = memory_set(key="k", value="x" * 100001)
        assert "❌" in result

    def test_memory_delete_removes_key(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text(json.dumps({"foo": "bar"}))
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_delete

        result = memory_delete(key="foo")
        assert "gelöscht" in result
        assert json.loads(mem_file.read_text()) == {}

    def test_memory_delete_not_found(self, tmp_path, monkeypatch):
        mem_file = tmp_path / "memory.json"
        mem_file.write_text("{}")
        monkeypatch.setattr("core.tools.MEMORY_FILE", mem_file)
        from core.tools import memory_delete

        result = memory_delete(key="nonexistent")
        assert "❌" in result
        assert "nicht" in result


class TestVaultWrappers:
    def test_vault_get_with_key(self):
        from core.tools import vault_get

        with patch("core.vault.load_vault", return_value={"test/key": "secret"}):
            result = vault_get("test/key")
            assert result == "secret"

    def test_vault_get_no_key_lists_groups(self):
        from core.tools import vault_get

        with patch("core.vault.load_vault", return_value={"a/x": "1", "b/y": "2"}):
            result = vault_get()
            assert "a" in result
            assert "b" in result
            assert "***" in result

    def test_vault_get_error(self):
        from core.tools import vault_get

        with patch("core.vault.load_vault", side_effect=OSError("fail")):
            result = vault_get("key")
            assert "❌" in result

    def test_vault_set(self):
        from core.tools import vault_set

        with (
            patch("core.vault.load_vault", return_value={}),
            patch("core.vault.save_vault") as mock_save,
        ):
            result = vault_set("new/key", "value123")
            assert "✅" in result
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved["new/key"] == "value123"

    def test_vault_set_overwrites(self):
        from core.tools import vault_set

        with (
            patch("core.vault.load_vault", return_value={"old/key": "old_val"}),
            patch("core.vault.save_vault") as mock_save,
        ):
            result = vault_set("old/key", "new_val")
            assert "✅" in result
            saved = mock_save.call_args[0][0]
            assert saved["old/key"] == "new_val"

    def test_vault_delete_existing(self):
        from core.tools import vault_delete

        with (
            patch("core.vault.load_vault", return_value={"del/key": "val"}),
            patch("core.vault.save_vault") as mock_save,
        ):
            result = vault_delete("del/key")
            assert "gelöscht" in result
            mock_save.assert_called_once()

    def test_vault_delete_not_found(self):
        from core.tools import vault_delete

        with (
            patch("core.vault.load_vault", return_value={}),
            patch("core.vault.save_vault"),
        ):
            result = vault_delete("missing")
            assert "❌" in result
            assert "nicht" in result

    def test_vault_delete_error(self):
        from core.tools import vault_delete

        with patch("core.vault.load_vault", side_effect=ValueError("fail")):
            result = vault_delete("key")
            assert "❌" in result

    def test_vault_list_shows_groups(self):
        from core.tools import vault_list

        with patch("core.vault.load_vault", return_value={"g/k1": "v1", "g/k2": "v2"}):
            result = vault_list()
            assert "g" in result
            assert "***" in result

    def test_vault_list_empty(self):
        from core.tools import vault_list

        with patch("core.vault.load_vault", return_value={}):
            result = vault_list()
            assert "leer" in result

    def test_vault_list_with_group_filter(self):
        from core.tools import vault_list

        with patch("core.vault.load_vault", return_value={"g/k1": "v1", "other/k": "v"}):
            result = vault_list(group="g")
            assert "k1" in result
            assert "other" not in result

    def test_vault_list_group_empty(self):
        from core.tools import vault_list

        with patch("core.vault.load_vault", return_value={"g/k1": "v1"}):
            result = vault_list(group="nonexistent")
            assert "leer" in result


class TestThink:
    def test_simple_thought_returns_note(self):
        from core.tools import think

        with patch("core.tools.create_plan") as mock_plan:
            result = think("Einfache Überlegung")
            assert result.startswith("📝")
            mock_plan.assert_not_called()

    def test_multi_line_thought_creates_plan(self):
        from core.tools import think

        with patch("core.tools.create_plan", return_value="MOCK PLAN") as mock_plan:
            result = think("Schritt 1\nSchritt 2\nSchritt 3")
            assert result.startswith("📋")
            mock_plan.assert_called_once()

    def test_complex_keyword_creates_plan(self):
        from core.tools import think

        with patch("core.tools.create_plan", return_value="MOCK PLAN") as mock_plan:
            result = think("analysiere das Problem")
            assert result.startswith("📋")
            mock_plan.assert_called_once()

    def test_auto_plan_triggers_plan(self):
        from core.tools import think

        with patch("core.tools.create_plan", return_value="MOCK PLAN") as mock_plan:
            result = think("simple thought", auto_plan=True)
            assert result.startswith("📋")
            mock_plan.assert_called_once()

    def test_think_validates_thought(self):
        from core.tools import think

        result = think(123)
        assert "❌" in result

    def test_think_includes_original_thought(self):
        from core.tools import think

        with patch("core.tools.create_plan", return_value="MOCK PLAN"):
            result = think("analysiere die Architektur")
            assert "Architektur" in result
