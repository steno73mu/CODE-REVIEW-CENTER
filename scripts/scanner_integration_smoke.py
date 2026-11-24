from __future__ import annotations

from pathlib import Path
import tempfile

from review_core.adapters import parse_gitleaks, parse_semgrep
from review_core.scanning import run_scanner


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="crc-scanner-smoke-") as temporary:
        root = Path(temporary)
        project = root / "fixture"
        project.mkdir()

        (project / "unsafe.py").write_text(
            "def evaluate_untrusted(value):\n    return eval(value)\n",
            encoding="utf-8",
        )
        semgrep_config = root / "semgrep.yml"
        semgrep_config.write_text(
            "rules:\n"
            "  - id: crc.integration.eval\n"
            "    languages: [python]\n"
            "    message: Avoid eval in this integration fixture\n"
            "    severity: ERROR\n"
            "    pattern: eval(...)\n",
            encoding="utf-8",
        )

        semgrep = run_scanner(
            [
                "semgrep", "scan", "--config", str(semgrep_config),
                "--json", "--quiet", "--metrics=off", str(project),
            ],
            parser=parse_semgrep,
            accepted_exit_codes=(0,),
            timeout_seconds=120,
            cwd=str(project),
        )
        if not any(item.rule_id.endswith("crc.integration.eval") for item in semgrep.findings):
            raise RuntimeError(
                "Semgrep did not report the expected local fixture finding; "
                f"exit={semgrep.process_result.returncode}; "
                f"stdout={semgrep.process_result.stdout[:2000]!r}; "
                f"stderr={semgrep.process_result.stderr[:2000]!r}"
            )

        test_access_key = "ghp_0123456789abcdef0123456789abcdef0123"
        (project / "credentials.txt").write_text(
            f"AWS_ACCESS_KEY_ID={test_access_key}\n",
            encoding="utf-8",
        )
        gitleaks = run_scanner(
            [
                "gitleaks", "dir",
                "--report-format", "json",
                "--report-path", "-",
                "--redact=100",
                "--no-banner",
                "--no-color",
                "--log-level", "fatal",
                str(project),
            ],
            parser=parse_gitleaks,
            accepted_exit_codes=(0, 1),
            timeout_seconds=60,
            cwd=str(project),
        )
        if not gitleaks.findings:
            raise RuntimeError(
                "Gitleaks did not report the expected fake token fixture; "
                f"exit={gitleaks.process_result.returncode}; "
                f"stdout={gitleaks.process_result.stdout[:2000]!r}; "
                f"stderr={gitleaks.process_result.stderr[:2000]!r}"
            )
        if test_access_key in gitleaks.process_result.stdout:
            raise RuntimeError("Gitleaks emitted an unredacted test secret to stdout")
        if any(test_access_key in item.message for item in gitleaks.findings):
            raise RuntimeError("Gitleaks adapter retained the fake access-key value")

        print(
            "Scanner integration passed: "
            f"Semgrep findings={len(semgrep.findings)}, "
            f"Gitleaks findings={len(gitleaks.findings)}, "
            "Gitleaks output redacted."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
