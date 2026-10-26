"""Reserved-stage authorization must preserve the committed development freeze."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run13


class ReservedFreezeContracts(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.research = self.root / 'integrations/webots/research'
        self.results = self.root / 'integrations/webots/results'
        self.freeze = 'a' * 40
        self.protocol = copy.deepcopy(run13.P)
        self.protocol['student_seeds'] = [701, 802, 903]
        self.source_names = ['revision13/gate13.py', 'revision13/dynamics13.py', 'core.py']
        self.sources = [self.research / name for name in self.source_names]
        self.models = [self.results / f'revision8-student/students/{seed}' / name
                       for seed in self.protocol['student_seeds']
                       for name in ('student.pt', 'normalization.npz', 'complete.json')]
        self.archived = {}
        for index, artifact in enumerate(self.sources + self.models):
            artifact.parent.mkdir(parents=True, exist_ok=True)
            content = f'Frozen artifact {index}\n'.encode()
            artifact.write_bytes(content)
            self.archived[str(artifact.relative_to(self.root))] = content
        self.path = self.results / 'revision13-development/selection.json'
        self.path.parent.mkdir(parents=True)
        self.chosen = 'balanced_light_fixed_p004'
        self.selection = dict(
            phase='development', protocol=self.protocol, selected_candidate=self.chosen,
            assessments={self.chosen: {'eligible': True}},
            native_candidate={'variant': 2, 'residual_rad': .04},
            source_commit=self.freeze)
        self.write_selection(self.selection, committed=True)
        # Exit patches before removing the temporary repository.
        for name, value in (('ROOT', self.root), ('RESEARCH', self.research),
                            ('RESULTS', self.results), ('P', self.protocol)):
            patched = patch.object(run13, name, value)
            patched.start()
            self.addCleanup(patched.stop)
        source_patch = patch.object(run13, 'sources', return_value=self.source_names)
        source_patch.start()
        self.addCleanup(source_patch.stop)
        git_patch = patch.object(run13.subprocess, 'check_output', side_effect=self.git_show)
        self.git = git_patch.start()
        self.addCleanup(git_patch.stop)

    def write_selection(self, selection, *, committed):
        self.path.write_text(json.dumps(selection, sort_keys=True) + '\n')
        if committed:
            self.committed_selection = self.path.read_bytes()

    def git_show(self, command, *, cwd):
        self.assertEqual(command[:2], ['git', 'show'])
        self.assertEqual(cwd, self.root)
        revision, relative = command[2].split(':', 1)
        if revision == 'HEAD':
            if relative == str(self.path.relative_to(self.root)):
                return self.committed_selection
            # HEAD can contain a newly committed implementation. Selection
            # must still compare executable/model bytes with the older freeze.
            return (self.root / relative).read_bytes()
        self.assertEqual(revision, self.freeze)
        return self.archived[relative]

    def test_valid_selection_checks_every_frozen_source_and_model(self):
        value, digest = run13.load_selection(self.path)
        self.assertEqual(value, self.selection)
        self.assertEqual(digest, hashlib.sha256(self.path.read_bytes()).hexdigest())
        shown = [call.args[0][2] for call in self.git.call_args_list]
        self.assertEqual(shown[0], 'HEAD:' + str(self.path.relative_to(self.root)))
        self.assertEqual(set(shown[1:]), {self.freeze + ':' + name for name in self.archived})
        self.assertEqual(len(shown), 1 + len(self.sources) + len(self.models))

    def test_uncommitted_selection_is_rejected_even_when_semantically_identical(self):
        self.path.write_bytes(self.committed_selection + b'\n')
        with self.assertRaisesRegex(ValueError, 'commit the exact development selection'):
            run13.load_selection(self.path)
        self.assertEqual(self.git.call_count, 1)

    def test_eligibility_requires_boolean_true(self):
        for invalid in (False, 0, 1, 'true', 'False', None, []):
            with self.subTest(eligible=invalid):
                value = copy.deepcopy(self.selection)
                value['assessments'][self.chosen]['eligible'] = invalid
                self.write_selection(value, committed=True)
                with self.assertRaisesRegex(ValueError, 'did not pass development'):
                    run13.load_selection(self.path)
        self.git.assert_not_called()

    def test_invalid_stage_protocol_candidate_identity_and_freeze_are_rejected(self):
        invalid = (
            ('phase', 'reserved', 'frozen development protocol'),
            ('protocol', {}, 'frozen development protocol'),
            ('selected_candidate', 'balanced_light_student', 'no eligible balanced candidate'),
            ('native_candidate', {'variant': 3, 'residual_rad': .04}, 'controller identity mismatch'),
            ('native_candidate', {'variant': 2, 'residual_rad': -.04}, 'controller identity mismatch'),
            ('source_commit', 'a' * 7, 'executable freeze is missing'),
            ('source_commit', 'z' * 40, 'executable freeze is missing'),
            ('source_commit', '', 'executable freeze is missing'),
        )
        for key, changed, message in invalid:
            with self.subTest(field=key, value=changed):
                value = copy.deepcopy(self.selection)
                value[key] = changed
                self.write_selection(value, committed=True)
                with self.assertRaisesRegex(ValueError, message):
                    run13.load_selection(self.path)

    def test_newly_committed_source_drift_does_not_replace_development_freeze(self):
        for artifact in self.sources:
            with self.subTest(source=artifact.name):
                original = artifact.read_bytes()
                artifact.write_bytes(original + b'changed after development\n')
                try:
                    with self.assertRaisesRegex(ValueError, 'selected source/model changed'):
                        run13.load_selection(self.path)
                finally:
                    artifact.write_bytes(original)

    def test_every_student_checkpoint_normalization_and_completion_is_frozen(self):
        for artifact in self.models:
            with self.subTest(seed=artifact.parent.name, artifact=artifact.name):
                original = artifact.read_bytes()
                artifact.write_bytes(original + b'changed after development\n')
                try:
                    with self.assertRaisesRegex(ValueError, 'selected source/model changed'):
                        run13.load_selection(self.path)
                finally:
                    artifact.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
