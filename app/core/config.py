import os
from dataclasses import dataclass
@dataclass(frozen=True)
class Settings:
    app_name:str="Jev Cloud Shadow"
    version:str="0.4.0"
    shadow_only:bool=True
    live_execution_enabled:bool=False
    cycle_seconds:int=int(os.getenv("CYCLE_SECONDS","900"))
    db_path:str=os.getenv("DB_PATH","shadow.db")
    discovery_provider:str=os.getenv("DISCOVERY_PROVIDER","geckoterminal")
settings=Settings()
if settings.live_execution_enabled:raise RuntimeError("Safety invariant violated: live execution must remain disabled")
