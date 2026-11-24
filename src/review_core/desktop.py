from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import uuid


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog, ttk
    except ImportError as exc:
        raise SystemExit(
            "Tkinter is not available. On Debian/Pop!_OS install python3-tk, then retry."
        ) from exc

    from .cli import data_directory
    from .configuration import ProviderConfigStore, ProviderProfile, ScannerConfigStore, ScannerProfile
    from .providers import AIReviewClient
    from .finding import Finding
    from .application import scan_project
    from .projects import ProjectRegistry
    from .storage import ScanStore

    data_directory().mkdir(parents=True, exist_ok=True)
    database = data_directory() / "review.sqlite3"
    projects = ProjectRegistry(database)
    scanners = ScannerConfigStore(database)
    providers = ProviderConfigStore(database)
    history = ScanStore(database)

    root = tk.Tk()
    root.title("CODE-REVIEW-CENTER")
    root.geometry("1180x760")
    root.minsize(900, 600)

    project_rows = []
    scanner_rows = []
    provider_rows = []
    cancellation = threading.Event()
    events: queue.Queue = queue.Queue()

    outer = ttk.Frame(root, padding=12)
    outer.pack(fill="both", expand=True)
    header = ttk.Frame(outer)
    header.pack(fill="x", pady=(0, 10))
    ttk.Label(header, text="CODE-REVIEW-CENTER", font=("TkDefaultFont", 18, "bold")).pack(side="left")
    status_var = tk.StringVar(value="Local workspace ready")
    ttk.Label(header, textvariable=status_var).pack(side="right")

    panes = ttk.Panedwindow(outer, orient="horizontal")
    panes.pack(fill="both", expand=True)
    sidebar = ttk.Frame(panes, padding=(0, 0, 10, 0), width=280)
    workspace = ttk.Frame(panes)
    panes.add(sidebar, weight=1)
    panes.add(workspace, weight=4)

    ttk.Label(sidebar, text="PROJECTS", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
    project_list = tk.Listbox(sidebar, height=10, exportselection=False)
    project_list.pack(fill="x", pady=(4, 6))
    project_buttons = ttk.Frame(sidebar)
    project_buttons.pack(fill="x")
    ttk.Button(project_buttons, text="Add folder", command=lambda: add_project()).pack(side="left")
    ttk.Button(project_buttons, text="Remove", command=lambda: remove_project()).pack(side="left", padx=4)

    ttk.Separator(sidebar).pack(fill="x", pady=12)
    ttk.Label(sidebar, text="SCANNER PROFILES", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
    scanner_list = tk.Listbox(sidebar, height=10, exportselection=False)
    scanner_list.pack(fill="x", pady=(4, 6))
    scanner_buttons = ttk.Frame(sidebar)
    scanner_buttons.pack(fill="x")
    ttk.Button(scanner_buttons, text="Add profile", command=lambda: add_scanner()).pack(side="left")
    ttk.Button(scanner_buttons, text="Remove", command=lambda: remove_scanner()).pack(side="left", padx=4)

    ttk.Separator(sidebar).pack(fill="x", pady=12)
    ttk.Label(sidebar, text="AI REVIEWERS", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
    provider_list = tk.Listbox(sidebar, height=6, exportselection=False)
    provider_list.pack(fill="x", pady=(4, 6))
    provider_buttons = ttk.Frame(sidebar)
    provider_buttons.pack(fill="x")
    ttk.Button(provider_buttons, text="Add provider", command=lambda: add_provider()).pack(side="left")
    ttk.Button(provider_buttons, text="Remove", command=lambda: remove_provider()).pack(side="left", padx=4)

    actions = ttk.Frame(workspace)
    actions.pack(fill="x", pady=(0, 8))
    scan_button = ttk.Button(actions, text="Run review", command=lambda: start_scan())
    scan_button.pack(side="left")
    cancel_button = ttk.Button(actions, text="Cancel", command=lambda: cancellation.set(), state="disabled")
    cancel_button.pack(side="left", padx=6)

    notebook = ttk.Notebook(workspace)
    notebook.pack(fill="both", expand=True)
    findings_tab = ttk.Frame(notebook, padding=6)
    history_tab = ttk.Frame(notebook, padding=6)
    notebook.add(findings_tab, text="Findings")
    notebook.add(history_tab, text="History")

    finding_columns = ("severity", "tool", "rule", "path", "line", "message")
    finding_tree = ttk.Treeview(findings_tab, columns=finding_columns, show="headings")
    for column, width in (("severity", 90), ("tool", 100), ("rule", 150), ("path", 180), ("line", 60), ("message", 440)):
        finding_tree.heading(column, text=column.title())
        finding_tree.column(column, width=width, anchor="w")
    finding_tree.pack(fill="both", expand=True)

    history_columns = ("session_id", "created_at", "status", "duration_seconds")
    history_actions = ttk.Frame(history_tab)
    history_actions.pack(fill="x", pady=(0, 6))
    ttk.Button(history_actions, text="AI review selected session", command=lambda: review_selected()).pack(side="left")
    history_tree = ttk.Treeview(history_tab, columns=history_columns, show="headings", height=12)
    for column, width in (("session_id", 280), ("created_at", 240), ("status", 120), ("duration_seconds", 120)):
        history_tree.heading(column, text=column.replace("_", " ").title())
        history_tree.column(column, width=width, anchor="w")
    history_tree.pack(fill="both", expand=True)
    history_tree.bind("<<TreeviewSelect>>", lambda _event: show_history())

    footer = ttk.Label(
        outer,
        text="Only trusted local scanner executables are launched. Project scripts and hooks are never run.",
        foreground="#555555",
    )
    footer.pack(anchor="w", pady=(8, 0))

    def selected_project():
        selection = project_list.curselection()
        return project_rows[selection[0]] if selection else None

    def selected_scanner():
        selection = scanner_list.curselection()
        return scanner_rows[selection[0]] if selection else None

    def refresh_projects():
        nonlocal project_rows
        project_rows = projects.list_projects()
        project_list.delete(0, "end")
        for item in project_rows:
            project_list.insert("end", f"{item.name}  ·  {Path(item.path).name}")

    def refresh_scanners():
        nonlocal scanner_rows
        scanner_rows = scanners.list_profiles()
        scanner_list.delete(0, "end")
        for item in scanner_rows:
            marker = "●" if item.enabled else "○"
            scanner_list.insert("end", f"{marker} {item.name}  [{item.parser}]")

    def refresh_history():
        for item in history_tree.get_children():
            history_tree.delete(item)
        for item in history.list_sessions(limit=100):
            history_tree.insert(
                "",
                "end",
                iid=item["session_id"],
                values=(item["session_id"], item["created_at"], item["status"], f"{item['duration_seconds']:.2f}"),
            )

    def add_project():
        path = filedialog.askdirectory(title="Select source repository")
        if not path:
            return
        name = simpledialog.askstring("Project name", "Name this project:", initialvalue=Path(path).name)
        if not name:
            return
        try:
            projects.register(name, path)
            refresh_projects()
            status_var.set("Project registered")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Project", str(exc))

    def remove_project():
        item = selected_project()
        if item is None:
            return
        if messagebox.askyesno("Remove project", f"Remove {item.name} from this workspace? Source files will not be changed."):
            projects.remove(item.project_id)
            refresh_projects()

    def add_scanner():
        scanner_id = simpledialog.askstring("Scanner profile", "Profile ID (e.g. semgrep-local):")
        if not scanner_id:
            return
        name = simpledialog.askstring("Scanner profile", "Display name:")
        if not name:
            return
        parser_name = simpledialog.askstring("Scanner profile", "Parser: semgrep, gitleaks, or sarif", initialvalue="semgrep")
        command_text = simpledialog.askstring(
            "Scanner profile",
            'Command as JSON argument array, e.g. ["semgrep","scan","--json","{project_path}"]',
        )
        if not parser_name or not command_text:
            return
        exit_text = simpledialog.askstring("Scanner profile", "Accepted exit codes (comma-separated):", initialvalue="0")
        timeout = simpledialog.askinteger("Scanner profile", "Timeout in seconds:", initialvalue=300, minvalue=1)
        try:
            command = json.loads(command_text)
            codes = tuple(int(part.strip()) for part in (exit_text or "0").split(","))
            profile = ScannerProfile(
                scanner_id=scanner_id,
                name=name,
                parser=parser_name.strip().lower(),
                command=tuple(command) if isinstance(command, list) else command,
                accepted_exit_codes=codes,
                timeout_seconds=timeout or 300,
            )
            scanners.save(profile)
            refresh_scanners()
            status_var.set("Scanner profile saved")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            messagebox.showerror("Scanner profile", str(exc))

    def remove_scanner():
        item = selected_scanner()
        if item is None:
            return
        if messagebox.askyesno("Remove scanner", f"Remove profile {item.name}?"):
            scanners.remove(item.scanner_id)
            refresh_scanners()

    def render_findings(findings):
        for item in finding_tree.get_children():
            finding_tree.delete(item)
        for index, finding in enumerate(findings):
            finding_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    finding.severity.value,
                    finding.tool,
                    finding.rule_id or "",
                    finding.path or "",
                    finding.start_line or "",
                    finding.message,
                ),
            )

    def start_scan():
        project = selected_project()
        if project is None:
            messagebox.showinfo("Scan", "Select a project first.")
            return
        profiles = scanners.list_profiles(enabled_only=True)
        if not profiles:
            messagebox.showinfo("Scan", "Add and enable at least one scanner profile.")
            return
        cancellation.clear()
        scan_button.configure(state="disabled")
        cancel_button.configure(state="normal")
        status_var.set(f"Scanning {project.name}…")
        threading.Thread(
            target=scan_worker,
            args=(project, profiles),
            daemon=True,
        ).start()

    def scan_worker(project, profiles):
        try:
            batch = scan_project(project, profiles, cancel_event=cancellation)
            session_id = str(uuid.uuid4())
            history.save_batch(session_id, batch)
            events.put(("success", session_id, batch))
        except Exception as exc:
            events.put(("error", type(exc).__name__, str(exc)))

    def show_history():
        selection = history_tree.selection()
        if not selection:
            return
        record = history.get_batch(selection[0])
        if record is None:
            return
        for item in finding_tree.get_children():
            finding_tree.delete(item)
        for index, finding in enumerate(record["findings"]):
            finding_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    finding["severity"],
                    finding["tool"],
                    finding["rule_id"] or "",
                    finding["path"] or "",
                    finding["start_line"] or "",
                    finding["message"],
                ),
            )
        notebook.select(findings_tab)

    def poll_events():
        try:
            while True:
                event = events.get_nowait()
                scan_button.configure(state="normal")
                cancel_button.configure(state="disabled")
                if event[0] == "success":
                    _, session_id, batch = event
                    render_findings(batch.findings)
                    refresh_history()
                    succeeded = sum(item.status.value == "succeeded" for item in batch.jobs)
                    status_var.set(f"Scan saved · {len(batch.findings)} unique findings · {len(batch.correlations)} correlation groups · {succeeded}/{len(batch.jobs)} scanners succeeded")
                    notebook.select(findings_tab)
                else:
                    _, error_type, message = event
                    status_var.set("Scan failed")
                    messagebox.showerror("Scan failed", f"{error_type}: {message}")
        except queue.Empty:
            pass
        root.after(100, poll_events)

    refresh_projects()
    refresh_scanners()
    refresh_history()
    root.after(100, poll_events)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
