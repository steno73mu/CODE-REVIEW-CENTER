import tempfile
import unittest
from pathlib import Path

from review_core.projects import ProjectRegistry


class ProjectRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "projects.sqlite3"
        self.project_path = self.root / "sample-project"
        self.project_path.mkdir()
        self.registry = ProjectRegistry(self.database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registers_and_lists_a_project(self):
        project = self.registry.register("Sample", self.project_path)
        self.assertEqual(project.name, "Sample")
        self.assertEqual(project.path, str(self.project_path.resolve()))
        self.assertEqual(len(self.registry.list_projects()), 1)

    def test_rejects_duplicate_project_name_and_path(self):
        self.registry.register("Sample", self.project_path)
        with self.assertRaises(ValueError):
            self.registry.register("Sample", self.project_path)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaises(ValueError):
            self.registry.register("Sample", other)

    def test_requires_existing_directory_and_safe_name(self):
        with self.assertRaises(ValueError):
            self.registry.register("Missing", self.root / "missing")
        with self.assertRaises(ValueError):
            self.registry.register("../bad", self.project_path)

    def test_updates_name_without_changing_project_identity(self):
        project = self.registry.register("Sample", self.project_path)
        updated = self.registry.rename(project.project_id, "Renamed")
        self.assertEqual(updated.project_id, project.project_id)
        self.assertEqual(updated.name, "Renamed")

    def test_removes_project_by_id(self):
        project = self.registry.register("Sample", self.project_path)
        self.assertTrue(self.registry.remove(project.project_id))
        self.assertEqual(self.registry.list_projects(), [])
        self.assertFalse(self.registry.remove(project.project_id))


if __name__ == "__main__":
    unittest.main()
