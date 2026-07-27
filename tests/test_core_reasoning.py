import json
from unittest.mock import patch


def _mock_response(content, error=False):
    if error:
        return {"error": "Mock error"}
    return {"message": {"role": "assistant", "content": content}}


class TestTreeOfThought:
    def test_generates_and_evaluates_branches(self):
        approaches = json.dumps(["approach A", "approach B"])
        path_a = "Path A reasoning result"
        path_b = "Path B reasoning result"
        eval_a = json.dumps({"score": 0.9, "strengths": ["clear"], "weaknesses": []})
        eval_b = json.dumps({"score": 0.7, "strengths": [], "weaknesses": ["vague"]})
        summary = "Final synthesized answer"

        call_count = [0]
        def _side_effect(model, msgs, tools=None):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _mock_response(approaches)
            elif n == 2:
                return _mock_response(path_a)
            elif n == 3:
                return _mock_response(path_b)
            elif n == 4:
                return _mock_response(eval_a)
            elif n == 5:
                return _mock_response(eval_b)
            else:
                return _mock_response(summary)

        with patch('core.reasoning.chat_with_tools', side_effect=_side_effect):
            from core.reasoning import tree_of_thought
            result = tree_of_thought("test problem", branches=2, depth=1)

        assert "best_path" in result
        assert "all_paths" in result
        assert len(result["all_paths"]) == 2
        assert "summary" in result
        assert result["summary"] == summary
        assert result["best_path"] == path_a  # 0.9 > 0.7

    def test_handles_empty_approaches(self):
        calls = [0]
        def side(model, msgs, tools=None):
            calls[0] += 1
            if calls[0] == 1:
                return _mock_response("invalid")
            return _mock_response("explored deeply")
        with patch('core.reasoning.chat_with_tools', side_effect=side):
            from core.reasoning import tree_of_thought
            result = tree_of_thought("problem", branches=2, depth=1)
            assert len(result["all_paths"]) == 1

    def test_handles_llm_error(self):
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response("", error=True)):
            from core.reasoning import tree_of_thought
            result = tree_of_thought("problem", branches=2, depth=1)
            assert len(result["all_paths"]) == 1

    def test_clamps_branches_and_depth(self):
        calls = [0]
        def side(model, msgs, tools=None):
            calls[0] += 1
            n = calls[0]
            if n == 1:
                return _mock_response(json.dumps(["approach a"]))
            if n == 2:
                return _mock_response("explored a")
            return _mock_response(json.dumps({"score": 0.5, "strengths": [], "weaknesses": []}))
        with patch('core.reasoning.chat_with_tools', side_effect=side):
            from core.reasoning import tree_of_thought
            result = tree_of_thought("problem", branches=999, depth=999)
            assert len(result["all_paths"]) >= 1

    def test_non_json_approach_response(self):
        calls = [0]
        def side(model, msgs, tools=None):
            calls[0] += 1
            n = calls[0]
            if n == 1:
                return _mock_response(
                    '["approach 1: use X", "approach 2: use Y"]'
                )
            return _mock_response("some reasoning")
        with patch('core.reasoning.chat_with_tools', side_effect=side):
            from core.reasoning import tree_of_thought
            result = tree_of_thought("problem", branches=2, depth=1)
            assert len(result["all_paths"]) == 2


class TestReasonStepByStep:
    def test_generates_steps_and_reasons(self):
        steps_json = json.dumps(["step 1", "step 2"])
        call_count = [0]
        def _side_effect(model, msgs, tools=None):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _mock_response(steps_json)
            elif n == 2:
                return _mock_response("conclusion 1")
            elif n == 3:
                return _mock_response(json.dumps({"valid": True, "issues": "", "confidence": 0.9}))
            elif n == 4:
                return _mock_response("conclusion 2")
            elif n == 5:
                return _mock_response(json.dumps({"valid": True, "issues": "", "confidence": 0.8}))
            else:
                return _mock_response("Final answer. HIGH CONFIDENCE.")

        with patch('core.reasoning.chat_with_tools', side_effect=_side_effect):
            from core.reasoning import reason_step_by_step
            result = reason_step_by_step("test problem")

        assert len(result["steps"]) == 2
        assert result["steps"][0]["step"] == "step 1"
        assert result["steps"][0]["conclusion"] == "conclusion 1"
        assert result["steps"][0]["verification"]["valid"] is True
        assert "final_answer" in result
        assert result["confidence"] == "HIGH"

    def test_uses_provided_steps(self):
        steps = ["custom step 1", "custom step 2"]
        call_count = [0]
        def _side_effect(model, msgs, tools=None):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _mock_response("c1")
            elif n == 2:
                return _mock_response(json.dumps({"valid": True, "issues": ""}))
            elif n == 3:
                return _mock_response("c2")
            elif n == 4:
                return _mock_response(json.dumps({"valid": True, "issues": ""}))
            else:
                return _mock_response("OK")

        with patch('core.reasoning.chat_with_tools', side_effect=_side_effect):
            from core.reasoning import reason_step_by_step
            result = reason_step_by_step("problem", steps=steps)

        assert len(result["steps"]) == 2
        assert result["steps"][0]["step"] == "custom step 1"

    def test_handles_empty_llm_response(self):
        def _side(model, msgs, tools=None):
            return _mock_response("", error=True)

        with patch('core.reasoning.chat_with_tools', side_effect=_side):
            from core.reasoning import reason_step_by_step
            result = reason_step_by_step("problem")
            assert len(result["steps"]) >= 1

    def test_detects_low_confidence(self):
        call_count = [0]
        def _side(model, msgs, tools=None):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _mock_response(json.dumps(["step 1"]))
            elif n == 2:
                return _mock_response("maybe conclusion")
            elif n == 3:
                return _mock_response(json.dumps({"valid": False, "issues": "uncertain"}))
            else:
                return _mock_response("Not sure. LOW CONFIDENCE.")

        with patch('core.reasoning.chat_with_tools', side_effect=_side):
            from core.reasoning import reason_step_by_step
            result = reason_step_by_step("problem")
            assert result["confidence"] == "LOW"

    def test_defaults_to_medium_confidence(self):
        call_count = [0]
        def _side(model, msgs, tools=None):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:
                return _mock_response(json.dumps(["step 1"]))
            elif n == 2:
                return _mock_response("conclusion")
            elif n == 3:
                return _mock_response(json.dumps({"valid": True, "issues": ""}))
            else:
                return _mock_response("Just an answer without confidence marker.")

        with patch('core.reasoning.chat_with_tools', side_effect=_side):
            from core.reasoning import reason_step_by_step
            result = reason_step_by_step("problem")
            assert result["confidence"] == "MEDIUM"


class TestEvaluateReasoning:
    def test_returns_scored_evaluation(self):
        eval_json = json.dumps({
            "overall_score": 0.85,
            "criteria_scores": {"clarity": 0.9, "correctness": 0.8},
            "strengths": ["well-structured"],
            "weaknesses": ["missing detail"],
            "suggestions": ["add more examples"],
        })
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response(eval_json)):
            from core.reasoning import evaluate_reasoning
            result = evaluate_reasoning("problem", "some reasoning")
        assert result["overall_score"] == 0.85
        assert "clarity" in result["criteria_scores"]

    def test_handles_llm_error(self):
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response("", error=True)):
            from core.reasoning import evaluate_reasoning
            result = evaluate_reasoning("problem", "reasoning")
        assert result["overall_score"] == 0.5

    def test_handles_non_json_response(self):
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response("everything is fine")):
            from core.reasoning import evaluate_reasoning
            result = evaluate_reasoning("problem", "reasoning")
        assert result["overall_score"] == 0.5

    def test_uses_default_criteria(self):
        eval_json = json.dumps({
            "overall_score": 0.9,
            "criteria_scores": {"clarity": 0.9},
            "strengths": [], "weaknesses": [], "suggestions": []
        })
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response(eval_json)):
            from core.reasoning import evaluate_reasoning
            result = evaluate_reasoning("problem", "reasoning")
        assert result["overall_score"] == 0.9


class TestConfidenceScore:
    def test_returns_structured_confidence(self):
        conf_json = json.dumps({
            "confidence": "HIGH",
            "score": 0.95,
            "reasoning": "well-supported",
            "gaps": [],
        })
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response(conf_json)):
            from core.reasoning import confidence_score
            result = confidence_score("result", "context")
        assert result["confidence"] == "HIGH"
        assert result["score"] == 0.95

    def test_handles_llm_error(self):
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response("", error=True)):
            from core.reasoning import confidence_score
            result = confidence_score("result", "context")
        assert result["confidence"] == "MEDIUM"
        assert result["score"] == 0.5

    def test_handles_non_json(self):
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response("looks good")):
            from core.reasoning import confidence_score
            result = confidence_score("result", "context")
        assert result["confidence"] == "MEDIUM"

    def test_includes_gaps(self):
        conf_json = json.dumps({
            "confidence": "LOW",
            "score": 0.3,
            "reasoning": "missing data",
            "gaps": ["need more info", "source unclear"],
        })
        with patch('core.reasoning.chat_with_tools', return_value=_mock_response(conf_json)):
            from core.reasoning import confidence_score
            result = confidence_score("result", "question?")
        assert len(result["gaps"]) == 2
        assert "need more info" in result["gaps"]


class TestExtractJson:
    def test_extracts_from_mixed_text(self):
        from core.reasoning import _extract_json
        text = 'Here is the result: {"score": 0.5, "name": "test"} and more'
        result = _extract_json(text)
        assert result is not None
        assert result["score"] == 0.5
        assert result["name"] == "test"

    def test_extracts_array(self):
        from core.reasoning import _extract_json
        text = 'Some text ["a", "b", "c"] trailing'
        result = _extract_json(text)
        assert result == ["a", "b", "c"]

    def test_returns_none_on_no_json(self):
        from core.reasoning import _extract_json
        result = _extract_json("no json here at all")
        assert result is None

    def test_returns_none_on_none_input(self):
        from core.reasoning import _extract_json
        assert _extract_json(None) is None

    def test_handles_nested_json(self):
        from core.reasoning import _extract_json
        text = 'nested {"outer": {"inner": [1, 2]}} end'
        result = _extract_json(text)
        assert result is not None
        assert result["outer"]["inner"] == [1, 2]
