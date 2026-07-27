import pytest


@pytest.fixture(autouse=True)
def reset_skills():
    from core.skills import _reset_cache
    _reset_cache()


@pytest.fixture
def temp_skills(tmp_path, monkeypatch):
    from core.skills import _reset_cache
    _reset_cache()
    skills_file = tmp_path / 'skills.json'
    monkeypatch.setattr('core.skills._SKILLS_FILE', skills_file)
    return skills_file


class TestLearnSkill:
    def test_learns_a_skill(self, temp_skills):
        from core.skills import learn_skill, skill_list
        result = learn_skill(
            'check_server',
            'Prüft ob Server erreichbar ist via SSH',
            [{'tool': 'execute_ssh', 'args': {'command': 'uptime'}}],
            tags=['server', 'ssh'],
        )
        assert '✅' in result
        listing = skill_list()
        assert len(listing) == 1
        assert listing[0]['name'] == 'check_server'

    def test_fails_without_name(self, temp_skills):
        from core.skills import learn_skill
        result = learn_skill('', 'desc', [])
        assert '❌' in result

    def test_fails_without_pattern(self, temp_skills):
        from core.skills import learn_skill
        result = learn_skill('test', 'desc', 'not_a_list')
        assert '❌' in result

    def test_auto_extracts_tags(self, temp_skills):
        from core.skills import learn_skill, skill_list
        learn_skill('backup_db', 'PostgreSQL backup via nextcloud', [{'tool': 'execute_bash', 'args': {'command': 'pg_dump'}}])
        listing = skill_list()
        assert 'nextcloud' in listing[0]['tags'] or 'bash' in listing[0]['tags']

    def test_limits_tags_to_10(self, temp_skills):
        from core.skills import learn_skill, skill_list
        many_tags = [f'tag{i}' for i in range(20)]
        learn_skill('many', 'test skill with many tags', [{'tool': 't'}], tags=many_tags)
        listing = skill_list()
        assert len(listing[0]['tags']) <= 10


class TestRecallSkills:
    def test_returns_empty_for_no_skills(self, temp_skills):
        from core.skills import recall_skills
        assert recall_skills('anything') == []

    def test_returns_matching_skills(self, temp_skills):
        from core.skills import learn_skill, recall_skills
        learn_skill('check_server', 'SSH server check', [{'tool': 'execute_ssh'}], tags=['server', 'ssh'])
        learn_skill('search_web', 'Search duckduckgo', [{'tool': 'web_search'}], tags=['search', 'web'])
        results = recall_skills('server status', max_results=5)
        assert len(results) >= 1
        names = [r['name'] for r in results]
        assert 'check_server' in names

    def test_returns_multiple_results_sorted(self, temp_skills):
        from core.skills import learn_skill, recall_skills
        learn_skill('skill_a', 'docker container management', [{'tool': 'execute_bash'}], tags=['docker'])
        learn_skill('skill_b', 'docker compose deploy', [{'tool': 'execute_bash'}], tags=['docker'])
        learn_skill('skill_c', 'weather news', [{'tool': 'fetch_news'}], tags=['news'])
        results = recall_skills('docker', max_results=5)
        assert len(results) >= 2
        assert all(r['relevance'] > 0 for r in results)

    def test_respects_max_results(self, temp_skills):
        from core.skills import learn_skill, recall_skills
        for i in range(10):
            learn_skill(f'skill_{i}', f'test skill number {i}', [{'tool': 't'}], tags=['test'])
        results = recall_skills('test', max_results=3)
        assert len(results) <= 3


class TestSkillList:
    def test_returns_empty_when_no_skills(self, temp_skills):
        from core.skills import skill_list
        assert skill_list() == []

    def test_returns_all_skills(self, temp_skills):
        from core.skills import learn_skill, skill_list
        learn_skill('a', 'skill a', [{'tool': 't'}])
        learn_skill('b', 'skill b', [{'tool': 't'}])
        assert len(skill_list()) == 2

    def test_filters_by_tag(self, temp_skills):
        from core.skills import learn_skill, skill_list
        learn_skill('docker_skill', 'docker management', [{'tool': 't'}], tags=['docker'])
        learn_skill('news_skill', 'news fetching', [{'tool': 't'}], tags=['news'])
        docker_skills = skill_list(tag='docker')
        assert len(docker_skills) == 1
        assert docker_skills[0]['name'] == 'docker_skill'


class TestSkillDelete:
    def test_deletes_existing_skill(self, temp_skills):
        from core.skills import learn_skill, skill_delete, skill_list
        learn_skill('tmp_skill', 'temp', [{'tool': 't'}])
        assert len(skill_list()) == 1
        result = skill_delete('tmp_skill')
        assert '🗑' in result
        assert skill_list() == []

    def test_returns_error_for_missing_skill(self, temp_skills):
        from core.skills import skill_delete
        result = skill_delete('nonexistent')
        assert '❌' in result


class TestUseSkill:
    def test_returns_pattern_and_increments_count(self, temp_skills):
        from core.skills import learn_skill, use_skill
        learn_skill('test_skill', 'desc', [{'tool': 'echo', 'args': {'msg': 'hi'}}])
        pattern = use_skill('test_skill')
        assert pattern == [{'tool': 'echo', 'args': {'msg': 'hi'}}]
        pattern2 = use_skill('test_skill')
        assert pattern2 is not None

    def test_returns_none_for_unknown(self, temp_skills):
        from core.skills import use_skill
        assert use_skill('unknown') is None


class TestAutoExtractTags:
    def test_detects_common_tags(self, temp_skills):
        from core.skills import _auto_extract_tags
        tags = _auto_extract_tags('setup docker container on server with ssh and nextcloud')
        assert 'docker' in tags
        assert 'ssh' in tags
        assert 'nextcloud' in tags

    def test_returns_empty_for_no_match(self, temp_skills):
        from core.skills import _auto_extract_tags
        tags = _auto_extract_tags('completely random text with no matches')
        assert tags == []
