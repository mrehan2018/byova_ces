# Optional `main.py` change

**You don't need this change for CES to work.** The new gateway code runs with an
unchanged `main.py`, which usually contains:

```python
server = WxCCGatewayServer(router)
```

When `main.py` is unchanged, the gateway uses built-in defaults:
- voice activity detection uses the same values as the config snippet;
- CVP compatibility is on.

## Why you might make the change

You'd make it to get two things:

1. The `voice_activity_detection:` and `gateway:` settings in `config.yaml` take effect.
2. Caller streams get their own thread pool, as in Cisco's current release. Cisco recommends this for more than ~10 concurrent calls, because the default gRPC pool can otherwise starve health checks.

## The change

In `main.py`, find the line `server = WxCCGatewayServer(router)` and replace that one line with:

```python
        gateway_config = config.get("gateway", {})
        server = WxCCGatewayServer(
            router,
            config.get("voice_activity_detection", {}),
            max_terminal_playback_seconds=float(gateway_config.get("max_terminal_playback_seconds", 30.0)),
            request_queue_maxsize=int(gateway_config.get("request_queue_maxsize", 100)),
            response_queue_maxsize=int(gateway_config.get("response_queue_maxsize", 100)),
            cvp_compat_audio=bool(gateway_config.get("cvp_compat_audio", True)),
        )
```

Keep the indentation of the original line. The variable that holds the loaded YAML
may have a different name in your `main.py`. It's usually `config`.

Then find the statement that registers the servicer. It starts with
`add_VoiceVirtualAgentServicer_to_server(` and may continue over several lines.
Add these lines **directly above** it:

```python
        # Dedicated thread pool for long-lived caller streams (Cisco recommendation)
        _streaming_executor = futures.ThreadPoolExecutor(
            max_workers=int(gateway_config.get("streaming_max_workers", 100)),
            thread_name_prefix="byova-stream",
        )
        server.ProcessCallerInput.__func__.experimental_thread_pool = _streaming_executor
```

`futures` comes from `from concurrent import futures`. A standard BYOVA `main.py`
already imports it.
