"""Test counts are derived from bounded report bytes, never runner exit alone."""
from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def load_tool(name):
    path = ROOT / "tools" / (name + ".py")
    assert path.exists(), "bounded test report parser is missing"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="icode-test-report-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def report(self, xml, **kwargs):
        path = self.root / "report.xml"
        path.write_bytes(xml.encode("utf-8") if isinstance(xml, str) else xml)
        return load_tool("test_result_summary").summarize_report(path, self.root, **kwargs)

    def assert_rejected(self, xml, message, **kwargs):
        api = load_tool("test_result_summary")
        with self.assertRaisesRegex(api.ReportError, message):
            self.report(xml, **kwargs)

    def test_zero_cases_is_inconclusive(self):
        result = self.report('<testsuite tests="0" failures="0"/>')
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertEqual(result["total"], 0)

    def test_all_skipped_is_inconclusive(self):
        result = self.report('<testsuite tests="2" skipped="2"><testcase><skipped/></testcase>'
                             '<testcase><skipped/></testcase></testsuite>')
        self.assertEqual(result["outcome"], "inconclusive")
        self.assertEqual((result["total"], result["passed"], result["skipped"]), (2, 0, 2))

    def test_unexecuted_status_markers_cannot_be_passing_cases(self):
        for attrs in ('status="notrun"', 'status="notrun" result="suppressed"', 'result="skipped"'):
            with self.subTest(attrs=attrs):
                result = self.report('<testsuite><testcase ' + attrs + '/></testsuite>')
                self.assertEqual((result["passed"], result["skipped"], result["outcome"]), (0, 1, "inconclusive"))

    def test_disabled_and_runtime_skipped_counters_stay_distinct(self):
        result = self.report('<testsuites tests="3" disabled="1"><testsuite tests="3" disabled="1" skipped="1">'
                             '<testcase status="run" result="completed"/>'
                             '<testcase status="notrun" result="suppressed"/>'
                             '<testcase status="run" result="skipped"><skipped/></testcase>'
                             '</testsuite></testsuites>')
        self.assertEqual((result["total"], result["passed"], result["skipped"]), (3, 1, 2))
        ctest = self.report('<testsuite tests="1" disabled="0" skipped="1">'
                            '<testcase status="notrun"><skipped/></testcase></testsuite>')
        self.assertEqual(ctest["outcome"], "inconclusive")

    def test_unknown_and_conflicting_status_markers_are_rejected(self):
        for attrs in ('status="unknown"', 'result="unknown"', 'status="notrun" result="completed"'):
            with self.subTest(attrs=attrs):
                self.assert_rejected('<testsuite><testcase ' + attrs + '/></testsuite>', "status|result")

    def test_disabled_counter_conflicts_are_rejected(self):
        self.assert_rejected('<testsuite tests="1" disabled="0">'
                             '<testcase status="notrun" result="suppressed"/></testsuite>', "count mismatch")

    def test_disabled_metadata_does_not_hide_forced_execution(self):
        result = self.report('<testsuite tests="1" disabled="1" skipped="0">'
                             '<testcase status="run" result="completed"/></testsuite>')
        self.assertEqual((result["passed"], result["skipped"], result["outcome"]), (1, 0, "pass"))
        self.assert_rejected('<testsuite tests="0" disabled="1"/>', "count mismatch")

    def test_actual_case_counts_and_original_report_identity(self):
        xml = '<testsuite><testcase name="ok"/><testcase><failure/></testcase>' \
              '<testcase><error/></testcase><testcase><skipped/></testcase></testsuite>'
        result = self.report(xml)
        self.assertEqual({key: result[key] for key in ("total", "passed", "failed", "errors", "skipped")},
                         {"total": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1})
        self.assertEqual(result["outcome"], "fail")
        self.assertEqual(result["report"], {"path": str((self.root / "report.xml").resolve()),
                         "sha256": hashlib.sha256(xml.encode()).hexdigest(), "bytes": len(xml.encode())})

    def test_nested_suite_aggregates_are_not_double_counted(self):
        result = self.report('<testsuites tests="3" failures="1" skipped="1"><testsuite tests="3" failures="1" skipped="1">'
                             '<testsuite tests="2" failures="1"><testcase/><testcase><failure/></testcase></testsuite>'
                             '<testcase><skipped/></testcase></testsuite></testsuites>')
        self.assertEqual((result["total"], result["passed"], result["failed"], result["skipped"]), (3, 1, 1, 1))

    def test_namespace_and_utf16_reports_are_counted(self):
        xml = '<?xml version="1.0" encoding="utf-16"?><testsuites xmlns="urn:junit"><testsuite tests="1">' \
              '<testcase name="ok"/></testsuite></testsuites>'
        self.assertEqual(self.report(xml.encode("utf-16"))["outcome"], "pass")

    def test_partial_skips_with_passing_cases_is_report_scoped_pass(self):
        result = self.report('<testsuite><testcase/><testcase><skipped/></testcase></testsuite>')
        self.assertEqual((result["outcome"], result["passed"], result["skipped"]), ("pass", 1, 1))

    def test_missing_case_details_cannot_authenticate_claimed_pass(self):
        self.assert_rejected('<testsuite tests="10" failures="0"/>', "count mismatch")

    def test_suite_and_root_counter_conflicts_are_rejected(self):
        for xml in ('<testsuite tests="0"><testcase/></testsuite>',
                    '<testsuite failures="0"><testcase><failure/></testcase></testsuite>',
                    '<testsuites tests="2"><testsuite><testcase/></testsuite></testsuites>',
                    '<testsuite skipped="1"><testcase/></testsuite>'):
            with self.subTest(xml=xml):
                self.assert_rejected(xml, "count mismatch")

    def test_invalid_declared_counts_are_rejected(self):
        for value in ("-1", "1.0", "NaN", "true", "", "9" * 100):
            with self.subTest(value=value):
                self.assert_rejected('<testsuite tests="' + value + '"/>', "count")

    def test_malformed_and_unsupported_roots_are_rejected(self):
        self.assert_rejected('<testsuite><testcase></testsuite>', "malformed")
        self.assert_rejected('<html/>', "root")

    def test_unsupported_xml_encodings_are_controlled_errors(self):
        for encoding in ('unrecognized-icode-encoding', 'utf-32', 'shift_jis', 'utf-7'):
            with self.subTest(encoding=encoding):
                self.assert_rejected('<?xml version="1.0" encoding="' + encoding + '"?><testsuite/>', "encoding|malformed")

    def test_supported_single_byte_encoding_remains_parseable(self):
        xml = '<?xml version="1.0" encoding="iso-8859-1"?><testsuite><testcase name="café"/></testsuite>'
        self.assertEqual(self.report(xml.encode('iso-8859-1'))["outcome"], "pass")

    def test_conflicting_case_outcomes_cannot_hide_failure(self):
        self.assert_rejected('<testsuite><testcase><failure/><skipped/></testcase></testsuite>', "conflicting")

    def test_misplaced_cases_and_failure_tags_are_rejected(self):
        for xml in ('<testsuite><properties><testcase/></properties></testsuite>',
                    '<testsuite><failure/></testsuite>',
                    '<testsuite><testcase><testsuite/></testcase></testsuite>'):
            with self.subTest(xml=xml):
                self.assert_rejected(xml, "structure")

    def test_dtd_and_entity_declarations_are_rejected_in_all_encodings(self):
        xml = '<?xml version="1.0"?><!DOCTYPE testsuite [<!ENTITY x "expanded">]>' \
              '<testsuite><testcase name="&x;"/></testsuite>'
        for data in (xml.encode(), xml.replace('version="1.0"', 'version="1.0" encoding="utf-16"').encode("utf-16"),
                     b'<!DOCTYPE testsuite SYSTEM "https://invalid.example/report.dtd"><testsuite/>'):
            with self.subTest(data=data[:20]):
                self.assert_rejected(data, "DTD|entity")

    def test_file_element_depth_and_case_budgets_are_enforced(self):
        self.assert_rejected('<testsuite><testcase/></testsuite>', "byte", limits={"max_bytes": 10})
        self.assert_rejected('<testsuite><testcase/></testsuite>', "element", limits={"max_elements": 1})
        self.assert_rejected('<testsuites><testsuite><testcase/></testsuite></testsuites>', "depth", limits={"max_depth": 2})
        self.assert_rejected('<testsuite><testcase/><testcase/></testsuite>', "test count", limits={"max_tests": 1})
        self.assert_rejected('<testsuite tests="2"/>', "test count", limits={"max_tests": 1})

    def test_timeout_and_invalid_budgets_are_controlled_errors(self):
        api = load_tool("test_result_summary")
        # Exercise elapsed time explicitly, independent of the host clock resolution.
        with patch.object(api.time, "monotonic", side_effect=(0.0, 2.0)):
            self.assert_rejected('<testsuite/>', "timeout", limits={"timeout_seconds": 1.0})
        for limits in ({"max_bytes": 0}, {"max_depth": True}, {"timeout_seconds": float("nan")}, {"other": 1}):
            with self.subTest(limits=limits):
                self.assert_rejected('<testsuite/>', "limit", limits=limits)

    def test_directory_missing_and_private_paths_are_rejected(self):
        api = load_tool("test_result_summary")
        for path in (self.root, self.root / "missing.xml"):
            with self.subTest(path=path), self.assertRaises(api.ReportError):
                api.summarize_report(path, self.root)
        private = self.root / ".git"
        private.mkdir()
        (private / "report.xml").write_text('<testsuite/>')
        with self.assertRaisesRegex(api.ReportError, "private"):
            api.summarize_report(private / "report.xml", self.root)

    def test_symlink_reports_are_rejected_when_supported(self):
        path = self.root / "real.xml"
        path.write_text('<testsuite/>')
        link = self.root / "link.xml"
        try:
            link.symlink_to(path)
        except OSError as exc:
            self.skipTest("host cannot create symlinks: " + str(exc))
        api = load_tool("test_result_summary")
        with self.assertRaisesRegex(api.ReportError, "symlink"):
            api.summarize_report(link, self.root)

    def test_report_outside_project_root_is_not_read_as_evidence(self):
        outside = self.root.with_suffix(".xml")
        outside.write_text("<testsuite><testcase/></testsuite>")
        self.addCleanup(outside.unlink)
        api = load_tool("test_result_summary")
        with self.assertRaisesRegex(api.ReportError, "inside the project"):
            api.summarize_report(outside, self.root)

