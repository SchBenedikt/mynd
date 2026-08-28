import json
import logging
import os
import re
from pathlib import Path

from .llm import chat_with_tools

logger = logging.getLogger(__name__)


def _load_model_config():
    model = os.getenv('OLLAMA_MODEL', 'gemma3:latest')
    cfg_path = Path(__file__).resolve().parent.parent / 'data' / 'ai_config.json'
    if cfg_path.exists():
        try:
            c = json.loads(cfg_path.read_text())
            model = c.get('model', model)
        except Exception:
            pass
    return model


def _call_llm(model, messages, tools=None):
    resp = chat_with_tools(model, messages, tools or [])
    if 'error' in resp:
        logger.warning('LLM error in reasoning: %s', resp['error'])
        return None
    msg = resp.get('message', {})
    return msg.get('content', '')


def _extract_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass
    return None


def tree_of_thought(problem, branches=3, depth=3, model=None):
    model = model or _load_model_config()
    branches = max(1, min(5, int(branches)))
    depth = max(1, min(5, int(depth)))

    prompt = (
        f'Problem: {problem}\n\n'
        f'Generate {branches} distinct approaches or angles to solve this problem. '
        f'Each approach should be a fundamentally different way of thinking. '
        f'Return a JSON array of strings: ["approach 1", "approach 2", ...]'
    )
    content = _call_llm(model, [{'role': 'user', 'content': prompt}])
    approaches = _extract_json(content) if content else None
    if not isinstance(approaches, list):
        approaches = [f'Analyze: {problem}']

    all_paths = []
    for i, approach in enumerate(approaches):
        current = approach
        for level in range(depth):
            explore_prompt = (
                f'Problem: {problem}\n\n'
                f'Approach: {current}\n\n'
                f'Think deeper. What are the next logical steps, '
                f'potential issues, or insights? Expand the reasoning.'
            )
            result = _call_llm(model, [{'role': 'user', 'content': explore_prompt}])
            if result:
                current = result
        all_paths.append(current)

    evaluations = []
    for path in all_paths:
        eval_prompt = (
            f'Problem: {problem}\n\n'
            f'Reasoning:\n{path[:2000]}\n\n'
            f'Evaluate on a scale 0.0-1.0 for correctness, completeness, clarity. '
            f'Return JSON: {{"score": 0.0-1.0, "strengths": [...], "weaknesses": [...]}}'
        )
        ev = _call_llm(model, [{'role': 'user', 'content': eval_prompt}])
        parsed = _extract_json(ev) if ev else None
        evaluations.append(parsed or {'score': 0.5, 'strengths': [], 'weaknesses': ['Could not evaluate']})

    best_idx = 0
    best_score = -1
    for i, ev in enumerate(evaluations):
        s = ev.get('score', 0)
        if isinstance(s, (int, float)) and s > best_score:
            best_score = s
            best_idx = i

    best_path = all_paths[best_idx] if all_paths else ''

    summary_prompt = (
        f'Problem: {problem}\n\n'
        f'Best reasoning found:\n{best_path[:2000]}\n\n'
        f'Synthesize this into a clear, concise answer.'
    )
    summary = _call_llm(model, [{'role': 'user', 'content': summary_prompt}]) or best_path[:1000]

    return {
        'best_path': best_path,
        'all_paths': all_paths,
        'evaluations': evaluations,
        'summary': summary,
    }


def reason_step_by_step(problem, steps=None, model=None):
    model = model or _load_model_config()

    if not steps:
        prompt = (
            f'Problem: {problem}\n\n'
            f'Break this into 3-5 logical reasoning steps. '
            f'Return a JSON array: ["step 1", "step 2", ...]'
        )
        content = _call_llm(model, [{'role': 'user', 'content': prompt}])
        steps = _extract_json(content) if content else None
        if not isinstance(steps, list):
            steps = [f'Analyze: {problem}']

    step_results = []
    context = f'Problem: {problem}'

    for i, step in enumerate(steps):
        work_prompt = f'{context}\n\nStep {i + 1}/{len(steps)}: {step}\n\nWork through this step. What do you conclude?'
        conclusion = _call_llm(model, [{'role': 'user', 'content': work_prompt}]) or ''

        verify_prompt = (
            f'Step: {step}\nConclusion: {conclusion[:1000]}\n\n'
            f'Verify: is it logically sound? '
            f'Return JSON: {{"valid": true/false, "issues": "...", "confidence": 0.0-1.0}}'
        )
        v_raw = _call_llm(model, [{'role': 'user', 'content': verify_prompt}])
        verification = _extract_json(v_raw) if v_raw else {'valid': True, 'issues': '', 'confidence': 0.8}
        if not isinstance(verification, dict):
            verification = {'valid': True, 'issues': '', 'confidence': 0.8}

        step_results.append(
            {
                'step': step,
                'conclusion': conclusion,
                'verification': verification,
            }
        )
        context += f'\n\nStep {i + 1}: {step}\nConclusion: {conclusion[:500]}'

    all_text = '\n'.join(
        f'Step {i + 1}: {r["step"]}\nConclusion: {r["conclusion"][:500]}' for i, r in enumerate(step_results)
    )
    final_prompt = (
        f'Problem: {problem}\n\nReasoning:\n{all_text}\n\n'
        f'Synthesize a final answer. State your confidence as LOW/MEDIUM/HIGH and why.'
    )
    final_answer = _call_llm(model, [{'role': 'user', 'content': final_prompt}]) or ''

    confidence = 'MEDIUM'
    if final_answer:
        upper = final_answer.upper()
        if 'CONFIDENCE: HIGH' in upper or 'HIGH CONFIDENCE' in upper:
            confidence = 'HIGH'
        elif 'CONFIDENCE: LOW' in upper or 'LOW CONFIDENCE' in upper:
            confidence = 'LOW'

    return {
        'steps': step_results,
        'final_answer': final_answer,
        'confidence': confidence,
    }


def evaluate_reasoning(problem, reasoning, criteria=None, model=None):
    model = model or _load_model_config()
    criteria = criteria or ['clarity', 'correctness', 'completeness', 'actionability']

    criteria_str = '\n'.join(f'- {c}' for c in criteria)
    prompt = (
        f'Problem: {problem}\n\nReasoning:\n{reasoning[:3000]}\n\n'
        f'Evaluate each criterion (0.0-1.0):\n{criteria_str}\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "criteria_scores": {{"criterion": 0.0-1.0, ...}},\n'
        f'  "overall_score": 0.0-1.0,\n'
        f'  "strengths": ["..."],\n'
        f'  "weaknesses": ["..."],\n'
        f'  "suggestions": ["..."]\n'
        f'}}'
    )
    content = _call_llm(model, [{'role': 'user', 'content': prompt}])
    result = _extract_json(content) if content else None
    return result or {'overall_score': 0.5, 'criteria_scores': {}, 'strengths': [], 'weaknesses': [], 'suggestions': []}


def confidence_score(result, context='', model=None):
    model = model or _load_model_config()

    prompt = (
        f'Question: {context[:1000]}\n\nResult:\n{result[:2000]}\n\n'
        f'Assign a confidence level. Consider: does it answer the question? '
        f'Is there sufficient evidence? Any gaps?\n\n'
        f'Return JSON:\n'
        f'{{\n'
        f'  "confidence": "LOW"/"MEDIUM"/"HIGH",\n'
        f'  "score": 0.0-1.0,\n'
        f'  "reasoning": "...",\n'
        f'  "gaps": ["..."]\n'
        f'}}'
    )
    content = _call_llm(model, [{'role': 'user', 'content': prompt}])
    result_data = _extract_json(content) if content else None
    return result_data or {'confidence': 'MEDIUM', 'score': 0.5, 'reasoning': 'Could not evaluate', 'gaps': []}
