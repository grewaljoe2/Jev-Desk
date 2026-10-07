"""Exact-project X observation boundary. Shadow only.

This module deliberately does not search for substitute accounts. A caller must
supply the exact cleaned handle recovered by the on-chain/token dossier.
"""
from typing import Protocol
from app.providers.savip_dossier import clean_handle

class XObservationProvider(Protocol):
    async def observe_exact(self,handle:str)->dict|None: ...

def exact_x_observation(expected_handle:str|None,observation:dict|None)->dict|None:
    expected=clean_handle(expected_handle)
    if not expected or not observation:return None
    observed=clean_handle(observation.get("x_handle"))
    if observed != expected:return None
    return {
      "x_handle":expected,
      "display_name":observation.get("display_name"),
      "bio":observation.get("bio"),
      "followers":observation.get("followers"),
      "following":observation.get("following"),
      "created_at":observation.get("created_at"),
      "recent_posts":observation.get("recent_posts") or [],
      "source":observation.get("source"),
      "exact_handle_verified":True,
    }

class NullExactXProvider:
    """Fail-closed until a server-side X data source is configured."""
    configured=False
    async def observe_exact(self,handle:str)->dict|None:
        return None
