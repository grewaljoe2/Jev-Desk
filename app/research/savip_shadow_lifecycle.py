"""PRICE -> SIZE -> FILLS -> BOOK shadow entry lifecycle. No real order transport."""
import asyncio
import os
import math
from app.research.savip_single_shadow_bridge import authorize_single_shadow
from app.storage.db import latest_accepted_savip_single_eligibility,savip_jev_event_by_id,commit_savip_single_shadow_entry
from datetime import datetime, timezone
from app.storage.db import latest_accepted_savip_pick,savip_pick_already_opened,log_savip_lifecycle,open_savip_positions,latest_savip_risk_price
from app.research.savip_book import open_book_position,close_book_position
from app.research.savip_shadow_execution import ticket_usd,simulated_market_fill
from app.research.savip_risk import risk_decision
from app.research.savip_pick import PickResult
from pydantic import ValidationError

class SavipShadowEntryWorker:
    def __init__(self,market_provider,seconds=60,bank_usd=1000.0):
        self.market_provider=market_provider;self.seconds=seconds;self.bank_usd=bank_usd;self.task=None;self.state="waiting";self.last_error=None
    async def run_cycle(self):
        if await open_savip_positions():
            self.state="position_held";return
        row=await latest_accepted_savip_pick()
        if not row or await savip_pick_already_opened(row["id"]):
            await self.run_single_entry();return
        created=row.get("created_at")
        if not created or (datetime.now(timezone.utc)-created.astimezone(timezone.utc)).total_seconds()>900:
            await self.run_single_entry();return
        p=row["payload_json"];evidence=(p.get("evidence") or {})
        pick=(p.get("pick") or {}).get("winner") or {}
        if not pick or pick.get("token_id")!=row["token_id"]:
            await self.run_single_entry();return
        try:
            decision=PickResult.model_validate(p.get("pick") or {})
            accepted,_=decision.accepted()
        except (ValidationError,ValueError,TypeError):
            accepted=False
        if not accepted:
            await self.run_single_entry();return
        market=await self.market_provider.observe(row["token_id"]) or {}
        price=market.get("price_usd");liq=market.get("liquidity_usd")
        if not price or not liq:
            self.state="waiting_for_price";return
        factor=pick.get("size_factor",0.0)
        social=evidence.get("social") or {}
        ticket=ticket_usd(self.bank_usd,liq,factor,missing_x=not bool(social.get("x_observation")))
        if ticket<=0:self.state="no_ticket";return
        fill=simulated_market_fill(ticket,price)
        pos=await open_book_position(row["token_id"],ticket,price,fill)
        if not pos:self.state="already_open";return
        await log_savip_lifecycle("SAVIP_SHADOW_ENTRY",row["token_id"],{"pick_event_id":row["id"],"position_id":pos,"price":price,"ticket_usd":ticket,"fill":fill,"real_execution":False})
        self.state="open"
    async def run_single_entry(self):
        if os.getenv("SAVIP_SINGLE_SHADOW_ENTRY_ENABLED","false").lower() not in ("true","1","yes"):
            self.state="single_entry_disabled";return
        row=await latest_accepted_savip_single_eligibility()
        if not row:
            self.state="waiting";return
        payload=row.get("payload_json") or {}
        jev=await savip_jev_event_by_id(payload.get("jev_event_id"))
        allowed,reason,factor,evidence=authorize_single_shadow(row,jev)
        if not allowed:
            self.state="single_blocked_"+reason;return
        if await open_savip_positions():
            self.state="position_held";return
        market=await self.market_provider.observe(row["token_id"]) or {}
        price=market.get("price_usd")
        liquidity=market.get("liquidity_usd")
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (price,liquidity)):
            self.state="single_waiting_for_market";return
        social=evidence.get("social") or {}
        ticket=ticket_usd(self.bank_usd,liquidity,factor,missing_x=not bool(social.get("x_observation")))
        if not math.isfinite(ticket) or ticket<=0:
            self.state="single_no_ticket";return
        fill=simulated_market_fill(ticket,price)
        if fill.get("net_asset_usd",0)<=0 or fill.get("quantity",0)<=0:
            self.state="single_fee_exceeds_ticket";return
        pos=await commit_savip_single_shadow_entry(row["id"],row["token_id"],ticket,price,fill,self.bank_usd)
        self.state="single_open" if pos else "single_duplicate_or_held"
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())

class SavipShadowRiskWorker:
    """5-minute published risk loop. Caller supplies fresh token market observations."""
    def __init__(self,market_provider,seconds=300):
        self.market_provider=market_provider;self.seconds=seconds;self.task=None;self.failures={};self.state="waiting";self.last_error=None
    async def run_cycle(self):
        positions=await open_savip_positions()
        if not positions:self.state="no_open_position";return
        for pos in positions:
            token=pos["token_id"];obs=None
            try:obs=await self.market_provider.observe(token)
            except Exception as e:self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            if obs and obs.get("volume_6h") is not None and obs.get("volume_24h") is not None:
                self.failures[token]=0
                decision=risk_decision(obs["volume_6h"],obs["volume_24h"])
            else:
                n=self.failures.get(token,0)+1;self.failures[token]=n
                decision=risk_decision(None,None,n)
            await log_savip_lifecycle("SAVIP_RISK",token,{"position_id":pos["id"],"decision":decision,"observation":obs,"real_execution":False})
            if decision["action"]=="close_100":
                price=(obs or {}).get("price_usd") or await latest_savip_risk_price(token)
                if price and await close_book_position(pos["id"],price):
                    await log_savip_lifecycle("SAVIP_SHADOW_EXIT",token,{"position_id":pos["id"],"exit_price":price,"reason":decision["reason"],"deadline_seconds":decision.get("deadline_seconds"),"real_execution":False})
                    self.failures.pop(token,None);self.state="closed"
                elif not price:self.state="close_waiting_for_price"
            else:self.state=decision["action"]
    async def loop(self):
        while True:
            try:await self.run_cycle()
            except Exception as e:self.state="failed";self.last_error=f"{type(e).__name__}: {str(e)[:160]}"
            await asyncio.sleep(self.seconds)
    def start(self):
        if not self.task:self.task=asyncio.create_task(self.loop())
