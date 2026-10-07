from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    app_name: str = "Jev Cloud Shadow"
    version: str = "0.3.0"
    shadow_only: bool = True
    live_execution_enabled: bool = False
    cycle_seconds: int = 900
    db_path: str = "shadow.db"

settings = Settings()

if settings.live_execution_enabled:
    raise RuntimeError("Safety invariant violated: live execution must remain disabled")
