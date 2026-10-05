from codeagent.providers.ratelimit import ModelRateLimits, TokenBucket, buckets_for_model


def test_bucket_refills_with_injected_clock() -> None:
    tick = {"t": 0.0}
    bucket = TokenBucket(capacity=2.0, refill_per_second=60.0, clock=lambda: tick["t"])
    assert bucket.try_consume(1.0)
    assert bucket.try_consume(1.0)
    assert not bucket.try_consume(1.0)
    tick["t"] = 1.0
    assert bucket.try_consume(1.0)


def test_model_buckets_share_limits() -> None:
    req, tok = buckets_for_model(ModelRateLimits(rpm=60, tpm=6000), clock=lambda: 0.0)
    assert req.try_consume(1.0)
    assert tok.try_consume(100.0)
