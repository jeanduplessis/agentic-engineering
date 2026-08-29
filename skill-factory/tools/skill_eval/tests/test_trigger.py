"""Offline protocol tests. Fake Pi responses are not model-behavior evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

from tools.skill_eval.regression import promote_failures_to_regression_cases
from tools.skill_eval.runner import run_suite
from tools.skill_eval.trigger import grade_trigger, inspect_trigger_trace


FAKE_PI = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
from xml.sax.saxutils import escape
args = sys.argv[1:]
path = args[args.index('--skill') + 1]
mode = os.environ.get('TEST_MODE', 'normal')
prompt = args[-1]
def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)
emit({'type': 'session'})
emit({'type': 'agent_start'})
if mode != 'no-catalog':
    context = {'type': 'skill_eval_context', 'version': 1,
          'catalogs': ['<available_skills><skill><name>demo</name><description>Demo tasks</description><location>' + escape(path) + '</location></skill></available_skills>'],
          'tools': ['read'], 'read_source': 'builtin', 'model': 'test-model', 'provider': 'test-provider', 'thinking': 'low'}
    observer_config = json.loads(Path(os.environ['SKILL_EVAL_OBSERVER_CONFIG']).read_text())
    if mode == 'observer-on-stderr':
        print(json.dumps(context), file=sys.stderr)
    else:
        Path(observer_config['context_path']).write_text('not-json' if mode == 'malformed-observer' else json.dumps(context) + '\\n')
if mode == 'stderr-diagnostic':
    print('Extension diagnostic, not a model event.', file=sys.stderr)
if prompt.startswith('positive') or mode == 'false-positive':
    emit({'type': 'message_end', 'message': {'role': 'assistant', 'model': 'test-model', 'provider': 'test-provider', 'stopReason': 'toolUse', 'content': [{'type': 'text', 'text': 'Before reading.'}, {'type': 'toolCall', 'id': 'r1', 'name': 'read', 'arguments': {'path': path}}]}})
    emit({'type': 'tool_execution_start', 'toolName': 'read', 'toolCallId': 'r1', 'args': {'path': path}})
    if mode != 'incomplete-read':
        emit({'type': 'tool_execution_end', 'toolName': 'read', 'toolCallId': 'r1', 'isError': mode == 'read-error',
              'result': {'content': [{'type': 'text', 'text': Path(path).read_text()}]}})
        emit({'type': 'message_end', 'message': {'role': 'toolResult', 'toolCallId': 'r1', 'toolName': 'read', 'isError': mode == 'read-error', 'content': [{'type': 'text', 'text': Path(path).read_text()}]}})
emit({'type': 'message_end', 'message': {'role': 'assistant', 'model': 'test-model', 'provider': 'test-provider', 'stopReason': 'error' if mode == 'assistant-error' else 'stop',
      'content': [{'type': 'thinking', 'thinking': 'not output'}, {'type': 'text', 'text': 'Answer.\\u2028Editorial note.'}]}})
if mode != 'incomplete':
    emit({'type': 'agent_end'})
if mode == 'mutate':
    Path(path).write_text('changed')
if mode == 'malformed':
    print('not-json')
if mode == 'exit-error':
    sys.exit(2)
'''


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'SKILL.md'
        self.skill.write_text('---\nname: demo\ndescription: Demo tasks\n---\nFollow the task.\n')
        self.fake = self.root / 'fake-pi'
        self.fake.write_text(FAKE_PI)
        self.fake.chmod(0o700)
        self.manifest = self.root / 'manifest.json'
        self.data = {
            'schema_version': 1, 'skill': {'name': 'demo', 'path': 'SKILL.md'},
            'suites': [{'name': 'trigger', 'type': 'trigger', 'mode': 'natural', 'cases': [
                {'id': 'yes', 'prompt': 'positive task', 'should_trigger': True, 'expected_skill': 'demo'},
                {'id': 'no', 'prompt': 'ordinary task', 'should_trigger': False, 'expected_skill': None},
            ]}],
            'configurations': {'with_skill': {'harness': 'pi', 'force_skill': True}, 'without_skill': {'harness': 'pi', 'force_skill': False}},
        }
        self.save()
        self.config = {'harness': 'pi', 'executable': str(self.fake), 'allow_live': True,
                       'model': 'test-model', 'provider': 'test-provider', 'thinking': 'low'}
        self.live_env = patch.dict(os.environ, {'SKILL_EVAL_ALLOW_LIVE': '0', 'SKILL_EVAL_ALLOW_LIVE_PI': '0'})
        self.live_env.start()
        self.addCleanup(self.live_env.stop)

    def save(self):
        self.manifest.write_text(json.dumps(self.data))

    def run_probe(self, mode='normal', **overrides):
        config = {**self.config, 'env': {'TEST_MODE': mode}, **overrides}
        return run_suite(self.manifest, 'trigger', self.root / f'results-{mode}', {'discovery': config}, require_real=True)

    def test_natural_selection_and_avoidance_capture_real_protocol_evidence(self):
        summary = self.run_probe()
        self.assertEqual([r['trigger_outcome'] for r in summary['runs']], ['true_positive', 'true_negative'])
        metrics = summary['benchmark']['configurations']['discovery']['trigger']
        self.assertEqual((metrics['activation_rate'], metrics['avoidance_rate']), (1, 1))
        plan = json.loads((self.root / 'results-normal/plan.json').read_text())
        self.assertEqual(plan['process_run_count'], 2)
        self.assertEqual(Path(plan['skill_path']).read_bytes(), self.skill.read_bytes())
        for run in summary['runs']:
            folder = Path(run['run_dir'])
            raw = json.loads((folder / 'raw_output.json').read_text())
            command = raw['command']
            self.assertEqual(command.count('--skill'), 1)
            self.assertEqual(command[command.index('--skill') + 1], plan['skill_path'])
            self.assertIn('--no-skills', command)
            self.assertIn('--no-context-files', command)
            self.assertIn('--no-approve', command)
            self.assertIn('--no-extensions', command)
            self.assertEqual(command[command.index('--tools') + 1], 'read')
            self.assertEqual(command[command.index('--mode') + 1], 'json')
            self.assertEqual(command[command.index('--system-prompt') + 1], '')
            self.assertEqual(command[command.index('--append-system-prompt') + 1], '')
            self.assertEqual(command[-1], run['prompt'])
            metadata = json.loads((folder / 'metadata.json').read_text())
            self.assertEqual(metadata['skill_paths_advertised'], [plan['skill_path']])
            self.assertEqual(bool(metadata['skill_paths_loaded']), run['should_trigger'])
            response = (folder / 'response.md').read_text()
            self.assertIn('Answer.\u2028Editorial note.', response)
            self.assertNotIn('not output', response)
            if run['should_trigger']:
                self.assertTrue(response.startswith('Before reading.'))
            self.assertEqual((folder / 'pi-events.jsonl').read_text(), raw['stdout'])
            self.assertTrue((folder / 'observer-context.jsonl').is_file())
            self.assertNotIn('skill_eval_context', raw['stdout'])

    def test_execution_and_observation_failures_never_pass_avoidance(self):
        for mode in ('no-catalog', 'observer-on-stderr', 'malformed-observer', 'incomplete', 'incomplete-read', 'assistant-error', 'malformed', 'exit-error', 'mutate'):
            with self.subTest(mode=mode):
                runs = self.run_probe(mode)['runs']
                affected = runs[:1] if mode == 'incomplete-read' else runs
                for run in affected:
                    self.assertIsNone(run['passed'])
                    self.assertEqual(run['trigger_outcome'], 'invalid')
                if mode == 'exit-error':
                    self.assertTrue(all(r['status'] == 'process_failed' for r in runs))

    def test_observer_sidecar_survives_extension_stderr_diagnostics(self):
        summary = self.run_probe('stderr-diagnostic')
        self.assertTrue(all(run['passed'] for run in summary['runs']))
        for run in summary['runs']:
            raw = json.loads((Path(run['run_dir']) / 'raw_output.json').read_text())
            self.assertIn('Extension diagnostic', raw['stderr'])
            self.assertNotIn('skill_eval_context', raw['stdout'])

    def test_failed_read_is_loading_error_for_positive_but_not_successful_avoidance(self):
        summary = self.run_probe('read-error')
        self.assertEqual(summary['runs'][0]['trigger_outcome'], 'load_error')
        self.assertIsNone(summary['runs'][0]['passed'])
        observation = {'valid': True, 'advertised': True, 'attempted': True, 'loaded': False, 'errors': []}
        self.assertEqual(grade_trigger(observation, False)['outcome'], 'false_positive')
        metrics = summary['benchmark']['configurations']['discovery']['trigger']
        self.assertIsNone(metrics['activation_rate'])
        self.assertEqual(metrics['invalid_rate'], 0.5)

    def test_negative_selection_is_a_behavioral_failure_not_process_failure(self):
        run = self.run_probe('false-positive')['runs'][1]
        self.assertEqual(run['status'], 'passed')
        self.assertIs(run['passed'], False)
        self.assertEqual(run['trigger_outcome'], 'false_positive')

    def test_timeout_retains_partial_json_and_does_not_grade_it(self):
        timeout = subprocess.TimeoutExpired(['fake-pi'], 2, output=b'{"type":"tool_execution_start"}\n')
        with patch('tools.skill_eval.runner.subprocess.run', side_effect=timeout):
            run = self.run_probe('timeout')['runs'][0]
        self.assertEqual(run['status'], 'process_failed')
        self.assertIsNone(run['passed'])
        raw = json.loads((Path(run['run_dir']) / 'raw_output.json').read_text())
        self.assertEqual(raw['error'], 'timeout')
        self.assertIn('tool_execution_start', raw['stdout'])

    def test_missing_live_opt_in_skips_without_starting_pi_or_inheriting_controls(self):
        summary = run_suite(self.manifest, 'trigger', self.root / 'skipped', require_real=True)
        self.assertEqual({r['configuration'] for r in summary['runs']}, {'discovery'})
        self.assertTrue(all(r['status'] == 'skipped' and r['passed'] is None for r in summary['runs']))
        metrics = summary['benchmark']['configurations']['discovery']['trigger']
        self.assertIsNone(metrics['avoidance_rate'])
        self.assertEqual(metrics['invalid'], 2)

    def test_invalid_contracts_reject_before_process_execution(self):
        for config in ({**self.config, 'harness': 'kilo'}, {**self.config, 'force_skill': False},
                       {**self.config, 'timeout_seconds': 0}, {**self.config, 'allow_live': 'false'},
                       {**self.config, 'extensions': ['https://invalid.test/provider.ts']}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                run_suite(self.manifest, 'trigger', self.root / 'invalid', {'discovery': config})
        self.data['suites'][0]['cases'][0]['should_trigger'] = 'true'
        self.save()
        with self.assertRaises(ValueError):
            self.run_probe()
        self.assertFalse((self.root / 'results-normal').exists())

    def test_process_start_failure_is_preserved_without_a_behavior_grade(self):
        self.fake.chmod(0o600)
        runs = self.run_probe()['runs']
        self.assertTrue(all(r['status'] == 'process_failed' and r['passed'] is None for r in runs))
        raw = json.loads((Path(runs[0]['run_dir']) / 'raw_output.json').read_text())
        self.assertEqual(raw['error'], 'process_start_failed')

    def test_prior_results_are_not_overwritten_or_promoted_to_wrong_regression_mode(self):
        self.run_probe()
        before = self.manifest.read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_probe()
        with self.assertRaises(ValueError):
            promote_failures_to_regression_cases(manifest_path=self.manifest, result_root=self.root / 'results-normal')
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_cli_selects_suite_local_profiles_and_requires_separate_live_opt_in(self):
        self.data['suites'][0]['configurations'] = {'one': {**self.config, 'allow_live': False}, 'two': {**self.config, 'allow_live': False}}
        self.save()
        command = [sys.executable, '-m', 'tools.skill_eval', str(self.manifest), 'trigger', '--results', str(self.root / 'cli'), '--configuration', 'two', '--require-real']
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        summary = json.loads(completed.stdout)
        self.assertEqual({r['configuration'] for r in summary['runs']}, {'two'})
        self.assertTrue(all(r['status'] == 'skipped' for r in summary['runs']))

    def test_catalog_and_tool_trace_invariants(self):
        summary = self.run_probe()
        folder = Path(summary['runs'][0]['run_dir'])
        plan = json.loads((self.root / 'results-normal/plan.json').read_text())
        raw = json.loads((folder / 'raw_output.json').read_text())
        events = [json.loads(line) for line in raw['stdout'].split('\n') if line]
        sandbox = Path(raw['cwd'])
        for mutation in ('wrong-name', 'wrong-model', 'no-read-tool', 'duplicate-end', 'unmatched-end', 'missing-all-tool-events', 'false-load-claim'):
            changed = json.loads(json.dumps(events))
            context = json.loads((folder / 'observer-context.jsonl').read_text())
            if mutation == 'wrong-name':
                context['catalogs'][0] = context['catalogs'][0].replace('<name>demo</name>', '<name>other</name>')
            elif mutation == 'wrong-model':
                context['model'] = 'another-model'
            elif mutation == 'no-read-tool':
                context['tools'] = []
            elif mutation == 'duplicate-end':
                end = next(e for e in changed if e['type'] == 'tool_execution_end')
                changed.insert(changed.index(end), dict(end))
            elif mutation == 'unmatched-end':
                next(e for e in changed if e['type'] == 'tool_execution_end')['toolCallId'] = 'missing'
            else:
                changed = [e for e in changed if not e['type'].startswith('tool_execution')]
                if mutation == 'false-load-claim':
                    changed = [e for e in changed if e.get('message', {}).get('role') != 'toolResult' and e.get('message', {}).get('stopReason') != 'toolUse']
                    next(e for e in changed if e['type'] == 'message_end')['message']['content'] = [{'type': 'text', 'text': 'I loaded the demo skill.'}]
            observation = inspect_trigger_trace('\n'.join(json.dumps(e) for e in changed), plan=plan, sandbox=sandbox,
                                                config=self.config, observer_output=json.dumps(context))
            if mutation == 'false-load-claim':
                self.assertEqual(grade_trigger(observation, True)['outcome'], 'false_negative')
            else:
                self.assertFalse(observation['valid'], mutation)

    def test_fixture_is_frozen_and_symlinks_are_rejected(self):
        fixture = self.root / 'fixture'
        fixture.mkdir()
        (fixture / 'design.md').write_text('Retry limit: two.\n')
        self.data['suites'][0]['fixture'] = {'type': 'copy', 'path': 'fixture'}
        self.save()
        summary = self.run_probe()
        plan = json.loads((self.root / 'results-normal/plan.json').read_text())
        (fixture / 'design.md').write_text('Changed after the run.\n')
        self.assertEqual((Path(plan['fixture']['path']) / 'design.md').read_text(), 'Retry limit: two.\n')
        self.assertTrue(all(r['passed'] for r in summary['runs']))
        (fixture / 'external').symlink_to(self.skill)
        with self.assertRaises(ValueError):
            self.run_probe('symlink')
        with self.assertRaisesRegex(ValueError, 'outside the source fixture'):
            run_suite(self.manifest, 'trigger', fixture / 'results', {'discovery': self.config})


if __name__ == '__main__':
    unittest.main()
