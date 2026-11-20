# BYOVA CES adapter for byova-dialogflow-agent

This repo adds a **Google CES (CX Agent Studio) voice agent** to a BYOVA gateway based on `wxsd-sales/byova-dialogflow-agent`, for **Cisco CVP / VVB** callers. Your Dialogflow CX agents keep working, and your own gateway changes are kept.

| Start here | |
|---|---|
| **[REPORT.md](REPORT.md)** | What we reviewed, what changes, proof that your changes are kept, test results, risks |
| **[WHATS_DIFFERENT_FROM_CISCO.md](WHATS_DIFFERENT_FROM_CISCO.md)** | One page: Cisco's code with additions only (CVP compatibility, WIF sign-in, parameter passing off by default) |
| **[INSTALL_FOR_YOUR_GATEWAY.md](INSTALL_FOR_YOUR_GATEWAY.md)** | Step-by-step install for your gateway |
| **[UPDATE_PARAMETERS.md](UPDATE_PARAMETERS.md)** | Update: pass values CVP ↔ CES (Name in; account_name / zipcode back to CVP) |
| **[UPDATE_DYNAMIC_PARAMETERS.md](UPDATE_DYNAMIC_PARAMETERS.md)** | Update: pass parameters CVP ↔ CES without listing each name in `config.yaml` (`session_variables: "auto"`, `forward_end_session_fields: "*"`). One file changes; script, patch or copy |
| **[UPDATE_TICKET_NUMBER.md](UPDATE_TICKET_NUMBER.md)** | Update: get `ticket_number` (or any agent value) back to CVP and see it in the gateway log (copy files, one patch, or 3 hand edits) |
| **[UPDATE_CONTINUED_SPEECH.md](UPDATE_CONTINUED_SPEECH.md)** | **Fix (Nov 2026):** caller hears 30 s of silence after speaking again while CES is replying, VVB waits 15 s when CVP re-enters right after a session ends, and a `KeyError` is logged when the caller hangs up. Why it happened, install (copy, patch or script), checks, undo |
| [MANUAL_UPDATE_PARAMETERS.md](MANUAL_UPDATE_PARAMETERS.md) | The same update as 3 small hand edits (or one patch), instead of copying files |
| [docs/CES_Adapter_Install_Guide_Linux_v2.1.docx](docs/CES_Adapter_Install_Guide_Linux_v2.1.docx) | Full guide: CES agent rules, settings, troubleshooting |

## Latest update: automatic parameter passing (19 November 2026)

Parameters now pass between CVP and CES without listing each name in `config.yaml`. Full steps, checks and undo are in **[UPDATE_DYNAMIC_PARAMETERS.md](UPDATE_DYNAMIC_PARAMETERS.md)**.

| New setting | Direction | Effect |
|---|---|---|
| `session_variables: "auto"` | CVP → CES | Sends `caller_ani`, `caller_dnis` and every parameter set in the CVP Virtual Agent Voice element |
| `forward_end_session_fields: "*"` | CES → CVP | Sends every field in the agent's `end_session` `params` back to CVP |

Both are off until you set them. The lists and mappings you use today behave as before.

### Code changed

One code file: **`src/connectors/gecx_connector.py`**, 78 lines added and 3 replaced, in 5 places. Each place carries the comment `byova_ces dynamic parameters` (edit D is a two-line branch without its own comment).

| Edit | Where in the file | What it does |
|---|---|---|
| A | `GECXStreamingSession._forwarded_end_session_fields` | When the setting is `"*"`, takes every field from the `end_session` `params` instead of filtering by a list |
| B | `GECXConnector.__init__` | Reads `session_variables: "auto"` and sets `session_variables_auto` |
| C | `GECXConnector.__init__` | Accepts `forward_end_session_fields` written as a plain string (`"*"`) as well as a list |
| D | `GECXConnector._session_variables_for` | Uses the automatic mapping when `session_variables_auto` is on |
| E | New: `_auto_session_variables`, `_sip_user_part` | Builds the variable list from the CVP parameters and reduces a SIP address to the number |

Not changed: `wxcc_gateway_server.py`, the router, the base connector class, the audio and speech-detection code, `requirements-ces.txt`.

### Files added or updated in this repo

| File | |
|---|---|
| `src/connectors/gecx_connector.py` | The connector with the 5 edits |
| `tools/apply_dynamic_parameters.py` | Applies the 5 edits to your installed file; stops without writing if your file differs; safe to run twice |
| `patches/dynamic-parameters.patch` | The same change as a patch |
| `verification/tests/test_byova_dynamic_parameters.py` | 12 tests for the new settings and for unchanged behaviour of lists, mappings and the default |
| `UPDATE_DYNAMIC_PARAMETERS.md` | Install steps, naming rules, log lines to check, undo |
| `config/gecx_connector.snippet.yaml` | Two commented example lines for the new settings |

### Update history

| Date | Update | Code files changed | Guide |
|---|---|---|---|
| 19 Nov 2026 | Automatic parameter passing (`"auto"`, `"*"`) | `gecx_connector.py` | [UPDATE_DYNAMIC_PARAMETERS.md](UPDATE_DYNAMIC_PARAMETERS.md) |
| 9–10 Nov 2026 | Fix: continued caller speech, CVP re-entry, `KeyError` on hang-up | `wxcc_gateway_server.py` | [UPDATE_CONTINUED_SPEECH.md](UPDATE_CONTINUED_SPEECH.md) |
| 4 Nov 2026 | Log the names of `end_session` params; optional value log for testing | `gecx_connector.py` | [UPDATE_TICKET_NUMBER.md](UPDATE_TICKET_NUMBER.md) |
| 28 Oct 2026 | Return `end_session` fields to CVP on a normal end | `gecx_connector.py`, `wxcc_gateway_server.py` | [UPDATE_PARAMETERS.md](UPDATE_PARAMETERS.md) |
| 22 Oct 2026 | First release: CES agent on a CVP / VVB gateway | The 8 files in `src/` | [INSTALL_FOR_YOUR_GATEWAY.md](INSTALL_FOR_YOUR_GATEWAY.md) |

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
