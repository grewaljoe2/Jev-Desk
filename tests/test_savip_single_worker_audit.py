import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock,patch
from app.research import savip_pick_worker as m
E={"market":{"liquidity_usd":50000,"proposed_ticket_usd":36},"chain":{"chain":"eth"}}
J={"market":{}}
S={"worth_trading_at_all":0.8,"confidence":0.7,"size_factor":0.5}
def row(age=0):
    return {"id":42,"token_id":"eth:a","created_at":datetime.now(timezone.utc)-timedelta(seconds=age),"payload_json":{"result":{"ok":True,"soft_pass":True,"judgment":J},"evidence":E}}
class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_single_audited_without_pick_or_entry(self):
        p=type("Provider",(),{"configured":True,"pick":AsyncMock(),"judge_single_eligibility":AsyncMock(return_value={"eligibility":S,"model":"mock"})})()
        entry=AsyncMock()
        w=m.SavipPickWorker(p,on_accept=entry)
        with patch.dict("os.environ",{"SAVIP_SINGLE_ELIGIBILITY_ENABLED":"true"}),patch.object(m,"open_savip_positions",AsyncMock(return_value=[])),patch.object(m,"recent_savip_soft_survivors",AsyncMock(return_value=[row()])),patch.object(m,"savip_pick_fingerprint_seen",AsyncMock(return_value=False)),patch.object(m,"savip_single_eligibility_seen",AsyncMock(return_value=False)),patch.object(m,"claim_savip_single_eligibility",AsyncMock(return_value=True)),patch.object(m,"complete_savip_single_eligibility_claim",AsyncMock()),patch.object(m,"claim_savip_single_eligibility",AsyncMock(return_value=True)),patch.object(m,"complete_savip_single_eligibility_claim",AsyncMock()),patch.object(m,"log_savip_single_eligibility",AsyncMock(return_value=True)) as log:
            await w.run_cycle()
            self.assertEqual(w.state,"single_eligible_audited")
            self.assertTrue(log.await_args.args[0]["accepted"])
        p.pick.assert_not_awaited()
        entry.assert_not_awaited()
    async def test_duplicate_skips_provider(self):
        p=type("Provider",(),{"configured":True,"judge_single_eligibility":AsyncMock()})()
        w=m.SavipPickWorker(p)
        with patch.object(m,"savip_single_eligibility_seen",AsyncMock(return_value=True)):
            await w.run_single(row())
        self.assertEqual(w.state,"single_already_judged")
        p.judge_single_eligibility.assert_not_awaited()
    async def test_stale_skips_provider(self):
        p=type("Provider",(),{"configured":True,"judge_single_eligibility":AsyncMock()})()
        w=m.SavipPickWorker(p)
        await w.run_single(row(1000))
        self.assertEqual(w.state,"single_stale_source")
        p.judge_single_eligibility.assert_not_awaited()
    async def test_low_confidence_logged_rejected(self):
        p=type("Provider",(),{"configured":True,"judge_single_eligibility":AsyncMock(return_value={"eligibility":{**S,"confidence":0.2}})})()
        w=m.SavipPickWorker(p)
        with patch.dict("os.environ",{"SAVIP_SINGLE_ELIGIBILITY_ENABLED":"true"}),patch.object(m,"savip_single_eligibility_seen",AsyncMock(return_value=False)),patch.object(m,"log_savip_single_eligibility",AsyncMock(return_value=True)) as log:
            await w.run_single(row())
            self.assertEqual(w.state,"single_rejected_audited")
            self.assertEqual(log.await_args.args[0]["reason"],"confidence")
    async def test_existing_claim_prevents_duplicate_model_spend(self):
        p=type("Provider",(),{"configured":True,"judge_single_eligibility":AsyncMock()})()
        w=m.SavipPickWorker(p)
        with patch.dict("os.environ",{"SAVIP_SINGLE_ELIGIBILITY_ENABLED":"true"}),patch.object(m,"savip_single_eligibility_seen",AsyncMock(return_value=False)),patch.object(m,"claim_savip_single_eligibility",AsyncMock(return_value=False)):
            await w.run_single(row())
        self.assertEqual(w.state,"single_already_claimed")
        p.judge_single_eligibility.assert_not_awaited()
    async def test_default_off_never_calls_provider(self):
        p=type("Provider",(),{"configured":True,"judge_single_eligibility":AsyncMock()})()
        w=m.SavipPickWorker(p)
        with patch.dict("os.environ",{"SAVIP_SINGLE_ELIGIBILITY_ENABLED":"false"}),patch.object(m,"savip_single_eligibility_seen",AsyncMock(return_value=False)):
            await w.run_single(row())
        self.assertEqual(w.state,"single_eligibility_disabled")
        p.judge_single_eligibility.assert_not_awaited()
if __name__=="__main__":unittest.main()
