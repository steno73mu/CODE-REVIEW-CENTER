import unittest

from review_core.desktop import _is_scan_completion_event


class DesktopEventRoutingTests(unittest.TestCase):
    def test_only_scan_completion_events_release_scan_controls(self):
        self.assertTrue(_is_scan_completion_event("success"))
        self.assertTrue(_is_scan_completion_event("scan_error"))
        self.assertFalse(_is_scan_completion_event("review_success"))
        self.assertFalse(_is_scan_completion_event("review_error"))


if __name__ == "__main__":
    unittest.main()
