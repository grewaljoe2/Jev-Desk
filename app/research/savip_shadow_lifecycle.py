"""PRICE -> SIZE -> FILLS -> BOOK shadow entry lifecycle. No real order transport."""
import asyncio
from app.storage.db import latest_accepted_savip_pick,savip_pick_already_opened,log_savip_lifecycle,open_savip_positions,latest_savip_risk_price
from app.research.savip_book import open_book_position,close_book_position
from app.research.savip_shadow_execution import ticket_usd,simulated_market_fill
from app.research.savip_risk import risk_decision

class SavipShadowEntryWorker:
    def __init__(self,seconds=60,bank_usd=1000.0):
        self.seconds=seconds;self.bank_usd=bank_usd;self.task=None;self.state="waiting";self.last_error=None
    async def run_cycle(self):
        row=await latest_accepted_savip_pick()
        if not row or await savip_pick_already_opened(row["id"]):self.state="waiting";return
        p=row["payload_json"];evidence=(p.get("evidence") or {})
        market=evidence.get("market") or {}
        price=market.get("price_usd");liq=market.get("liquidity_usd")
        if not price or not liq:
            self.state="waiting_for_price";return
        pick=(p.get("pick") or {}).get("winner") or {}
        factor=pick.get("size_factor",1.0)
        social=evidence.get("social") or {}
        ticket=ticket_usd(self.bank_usd,liq,factor,missing_x=not bool(social.get("x_observation")))
        if ticket<=0:self.state="no_ticket";return
        fill=simulated_market_fill(ticket,price)
        pos=await open_book_position(row["token_id"],ticket,price,fill)
        if not pos:self.state="already_open";return
        await log_savip_lifecycle("SAVIP_SHADOW_ENTRY",row["token_id"],{"pick_event_id":row["id"],"position_id":pos,"price":price,"ticket_usd":ticket,"fill":fill,"real_execution":False})
        self.state="open"
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
