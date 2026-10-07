"""Exact-project X observation boundary and free public reader. Shadow only.

The reader never searches for an account. It receives the exact handle recovered
from the token dossier, reads that handle only, then verifies the returned
screen_name before any observation is accepted.
"""
from typing import Protocol
import httpx
from app.providers.savip_dossier import clean_handle

class XObservationProvider(Protocol):
    async def observe_exact(self,handle:str)->dict|None: ...

def exact_x_observation(expected_handle:str|None,observation:dict|None)->dict|None:
    expected=clean_handle(expected_handle)
    if not expected or not observation:return None
    observed=clean_handle(observation.get("x_handle"))
    if not observed or observed.lower()!=expected.lower():return None
    return {
      "x_handle":expected,
      "display_name":observation.get("display_name"),
      "bio":observation.get("bio"),
      "followers":observation.get("followers"),
      "following":observation.get("following"),
      "posts_count":observation.get("posts_count"),
      "created_at":observation.get("created_at"),
      "website":observation.get("website"),
      "recent_posts":observation.get("recent_posts") or [],
      "source":observation.get("source"),
      "exact_handle_verified":True,
    }

class FreeExactXProvider:
    """No-key public X reader via FxTwitter/FxEmbed.

    FxTwitter is a third-party public-data proxy, so any outage or malformed
    response fails closed. No search/fuzzy account lookup is ever attempted.
    """
    BASE="https://api.fxtwitter.com/2"
    configured=True
    def __init__(self,timeout=15):
        self.client=httpx.AsyncClient(timeout=timeout,headers={"Accept":"application/json","User-Agent":"JevDesk/0.6.3"})
        self.last_error=None
    async def _json(self,url):
        r=await self.client.get(url)
        r.raise_for_status()
        return r.json()
    async def observe_exact(self,handle:str)->dict|None:
        expected=clean_handle(handle)
        if not expected:return None
        try:
            profile=await self._json(f"{self.BASE}/profile/{expected}")
            user=profile.get("user") or {}
            returned=clean_handle(user.get("screen_name"))
            if not returned or returned.lower()!=expected.lower():
                self.last_error="x_handle_mismatch";return None
            timeline=await self._json(f"{self.BASE}/profile/{expected}/statuses?count=10")
            posts=[]
            for p in (timeline.get("results") or [])[:10]:
                author=(p.get("author") or {})
                ph=clean_handle(author.get("screen_name")) if author else expected
                if ph and ph.lower()!=expected.lower():continue
                posts.append({
                  "id":p.get("id"),"text":p.get("text"),"created_at":p.get("created_at"),
                  "likes":p.get("likes"),"reposts":p.get("reposts"),
                  "quotes":p.get("quotes"),"replies":p.get("replies"),"views":p.get("views"),
                })
            website=user.get("website")
            if isinstance(website,dict):website=website.get("url") or website.get("display_url")
            self.last_error=None
            return exact_x_observation(expected,{
              "x_handle":returned,"display_name":user.get("name"),"bio":user.get("description"),
              "followers":user.get("followers"),"following":user.get("following"),
              "posts_count":user.get("statuses"),"created_at":user.get("joined"),
              "website":website,"recent_posts":posts,"source":"fxtwitter_public_v2",
            })
        except Exception as e:
            self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            return None

class NullExactXProvider:
    configured=False
    async def observe_exact(self,handle:str)->dict|None:return None
