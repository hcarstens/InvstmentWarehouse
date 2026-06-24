"""Research sandbox path validation — client data stays isolated."""

from pathlib import Path

from warehouse.config import Settings, get_settings, repo_root


def resolve_research_path(path: Path, settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    sandbox = (repo_root() / cfg.research_sandbox_path).resolve()
    resolved = path.resolve()
    if resolved == sandbox or sandbox in resolved.parents:
        return resolved
    raise ValueError(f"Research path must stay under {sandbox}")


def copy_to_research_sandbox(source: Path, settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    sandbox = (repo_root() / cfg.research_sandbox_path).resolve()
    sandbox.mkdir(parents=True, exist_ok=True)
    target = sandbox / source.name
    target.write_bytes(source.read_bytes())
    resolve_research_path(target, cfg)
    return target
