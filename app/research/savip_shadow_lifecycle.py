"""PRICE -> SIZE -> FILLS -> BOOK shadow entry lifecycle. No real order transport."""
import asyncio
from app.storage.db import latest_accepted_savip_pick,savip_pick_already_opened,log_savip_lifecycle
from app.research.savip_book import open_book_position
from app.research.savip_shadow_execution import ticket_usd,simulated_market_fill

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
