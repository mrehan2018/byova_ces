# BYOVA Google CES Adapter: package for Linux gateways

> **Made for byova-dialogflow-agent.** Start with **INSTALL_FOR_YOUR_GATEWAY.md**: your server file keeps your own changes, and the install uses `--force`.

This package adds **Google CES (Gemini Enterprise for CX / CX Agent Studio)** as a new
virtual agent to an existing BYOVA gateway that already serves **Cisco CVP / VVB**, for example
with Dialogflow CX. Existing connectors keep working unchanged.

The full procedure is in **docs/CES_Adapter_Install_Guide_Linux_v2.1.docx**. This README is the short version.

## What's inside

| Path | What it is |
|---|---|
| `src/connectors/gecx_connector.py` | Cisco's Google CES connector (BidiRunSession). It opts in to gateway voice-activity detection. |
| `src/connectors/i_vendor_connector.py` | The base class with Cisco's streaming hooks. VAD is off by default, so existing connectors keep their behaviour. It also accepts `language_code` in `create_session_start_response`. |
| `src/core/wxcc_gateway_server.py` | Cisco's current gateway server plus a **CVP/VVB compatibility mode**: streamed audio becomes one WAV prompt, START/END_OF_INPUT events are suppressed, and CVP prompts stay bargeable. |
| `src/core/virtual_agent_router.py`, `src/core/health_service.py` | Cisco's current versions. They're required by the server above. |
| `src/utils/audio_normalizer.py`, `silero_speech_boundary.py`, `telephony_audio.py` | New helper modules used by the server and the CES connector. |
| `requirements-ces.txt` | The extra Python packages. Install CPU-only PyTorch first. |
| `config/gecx_connector.snippet.yaml` | The block to paste into `config/config.yaml`. |
| `config/gecx_example.cisco.yaml` | Cisco's fully commented reference for every CES option. |
| `tools/check_compat.sh` | A read-only pre-check. It reports whether your gateway files are unmodified Cisco originals. |
| `tools/install.sh` | Backs up, installs the packages, copies the code and runs the smoke test. It doesn't edit config or restart the gateway. |
| `tools/rollback.sh` | Restores the backup that `install.sh` made. |
| `tools/smoke_test.py` | An offline check of packages, imports, every configured connector and the CES config. |
| `tools/cvp_sim.py` | Simulates a CVP call over gRPC to test without a phone. |
| `docs/main_py_optional_change.md` | An optional `main.py` change: config-driven VAD settings and a dedicated stream thread pool. |
| `patches/*.patch` | Changes against Cisco release 0f63e16, for gateways with local code changes. |
| `reference/cisco-0f63e16/` | The original Cisco files that `check_compat.sh` compares against. |

## Quick install

Run these on the gateway host, as the user that owns the gateway folder:

```bash
tar -xzf ces-adapter-package.tgz && cd ces-adapter-package
./tools/check_compat.sh /opt/byova-gateway                 # 1. pre-check (read-only)
./tools/install.sh /opt/byova-gateway                      # 2. backup + packages + code + smoke test
vi /opt/byova-gateway/config/config.yaml                   # 3. paste config/gecx_connector.snippet.yaml
sudo systemctl restart byova-gateway                       # 4. restart (use your service name)
python tools/cvp_sim.py --gateway-dir /opt/byova-gateway localhost:50051 ces 8   # 5. test
```

Replace `/opt/byova-gateway` with your gateway folder, `50051` with `gateway.port` from your
config, and `byova-gateway` with your service name. If the gateway runs in a virtualenv that isn't
`<gateway>/venv` or `<gateway>/.venv`, pass its Python as the second argument to the scripts.

In CVP, set the virtual agent ID to **`ces`**, the agent name in the config snippet.

## Rollback

```bash
./tools/rollback.sh /opt/byova-gateway/backups/pre-ces-<timestamp>
sudo systemctl restart byova-gateway
```

## Tested

- Cisco gateway 0f63e16 in a Python 3.11 venv on Debian, with a Dialogflow CX connector.
- The Dialogflow CX regression passed, and the CES greeting, conversation and end_session passed through CVP 15 / VVB.
- The rollback was verified.
- Cisco's unit tests for the gateway server, router, base class, CES connector and audio helpers all pass (307 tests).
