import unittest
from unittest.mock import patch,AsyncMock
from app.storage.db import log_savip_single_eligibility,savip_single_eligibility_seen

class Cursor:
    def __init__(self,exists=False):self.exists=exists
    async def fetchone(self):return (1,) if self.exists else None
class Conn:
    def __init__(self,exists=False):self.exists=exists;self.sql=[];self.commits=0
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass
    async def execute(self,sql,params=None):
        self.sql.append((sql,params))
        return Cursor(self.exists if "SELECT 1" in sql else False)
    async def commit(self):self.commits+=1
class FakePsycopg:
    class AsyncConnection:
        connection=None
        @classmethod
        async def connect(cls,url):return cls.connection
class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_once(self):
        conn=Conn();FakePsycopg.AsyncConnection.connection=conn
        with patch("app.storage.db.settings",type("Settings",(),{"database_url":"postgres://mock"})()),patch.dict("sys.modules",{"psycopg":FakePsycopg}):
            result=await log_savip_single_eligibility({"jev_event_id":19,"token_id":"eth:a","accepted":False})
        self.assertTrue(result)
        self.assertTrue(any("INSERT INTO events" in q for q,_ in conn.sql))
        self.assertEqual(conn.commits,1)
    async def test_duplicate_no_insert(self):
        conn=Conn(exists=True);FakePsycopg.AsyncConnection.connection=conn
        with patch("app.storage.db.settings",type("Settings",(),{"database_url":"postgres://mock"})()),patch.dict("sys.modules",{"psycopg":FakePsycopg}):
            result=await log_savip_single_eligibility({"jev_event_id":19,"token_id":"eth:a"})
        self.assertFalse(result)
        self.assertFalse(any("INSERT INTO events" in q for q,_ in conn.sql))
    async def test_invalid_id(self):
        with patch("app.storage.db.settings",type("Settings",(),{"database_url":"postgres://mock"})()):
            with self.assertRaises(ValueError):await log_savip_single_eligibility({"jev_event_id":None})
    async def test_seen(self):
        conn=Conn(exists=True);FakePsycopg.AsyncConnection.connection=conn
        with patch("app.storage.db.settings",type("Settings",(),{"database_url":"postgres://mock"})()),patch.dict("sys.modules",{"psycopg":FakePsycopg}):
            self.assertTrue(await savip_single_eligibility_seen(19))
if __name__=="__main__":unittest.main()
