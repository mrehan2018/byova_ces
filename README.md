# BYOVA CES adapter for byova-dialogflow-agent

This repo adds a **Google CES (CX Agent Studio) voice agent** to a BYOVA gateway based on `wxsd-sales/byova-dialogflow-agent`, for **Cisco CVP / VVB** callers. Your Dialogflow CX agents keep working, and your own gateway changes are kept.

| Start here | |
|---|---|
| **[REPORT.md](REPORT.md)** | What we reviewed, what changes, proof that your changes are kept, test results, risks |
| **[INSTALL_FOR_YOUR_GATEWAY.md](INSTALL_FOR_YOUR_GATEWAY.md)** | Step-by-step install for your gateway |
| [docs/CES_Adapter_Install_Guide_Linux_v2.1.docx](docs/CES_Adapter_Install_Guide_Linux_v2.1.docx) | Full guide: CES agent rules, settings, troubleshooting |

## Quick install

```bash
cd /tmp && git clone https://github.com/mrehan2018/byova_ces.git && cd byova_ces
chmod +x tools/*.sh
./tools/check_compat.sh /home/administrator/byova-dialogflow-agent python3          # read-only pre-check
./tools/install.sh /home/administrator/byova-dialogflow-agent python3 --force       # backup + packages + code + smoke test
# add the gecx_connector block (config/gecx_connector.snippet.yaml) to config.yaml, then restart the gateway
```

**Undo:** `./tools/rollback.sh /home/administrator/byova-dialogflow-agent/backups/pre-ces-<date> --restore-packages python3`, then restart the gateway.

## Contents

| Path | |
|---|---|
| `src/` | The 8 gateway files (4 replace existing files, 4 are new). See REPORT.md section 5 |
| `tools/` | `check_compat.sh`, `install.sh`, `rollback.sh`, `smoke_test.py`, `cvp_sim.py` |
| `config/` | `gecx_connector.snippet.yaml` (the block for your `config.yaml`) and Cisco's full CES example |
| `verification/` | Your `server.diff` and the script that proves every change in it is kept |
| `patches/` | `make_customer_server.py` (how your server file was built) and diffs against Cisco 0f63e16 |
| `reference/` | Original Cisco files used by the pre-check |
| `requirements-ces.txt` | Extra Python packages (install CPU-only PyTorch first; `install.sh` does this) |

The code is based on Cisco's `webex-byova-gateway-python`, under the Cisco Sample Code License (see `LICENSE`).
