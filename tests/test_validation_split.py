from app.research.validation_split import cohort_partition,split_samples

def test_partition_is_stable():
    s={"token_id":"solana:abc","baseline_at":"2026-01-01T00:00:00Z"}
    assert cohort_partition(s)==cohort_partition(dict(s))

def test_split_has_no_overlap():
    samples=[{"token_id":f"t{i}","baseline_at":"2026-01-01"} for i in range(100)]
    a,b=split_samples(samples)
    ka={x["token_id"] for x in a};kb={x["token_id"] for x in b}
    assert not ka&kb
    assert ka|kb=={x["token_id"] for x in samples}
    assert len(a)>0 and len(b)>0
