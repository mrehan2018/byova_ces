# Adding Google CES to your BYOVA gateway: review and change report

**Gateway reviewed:** `byova-dialogflow-agent` (fork of Cisco `webex-byova-gateway-python`), Linux, Python 3.12.3
**Date:** 22 October 2026
**Purpose:** add a Google CES (CX Agent Studio) voice agent for Cisco CVP / VVB callers, next to your existing Dialogflow CX agents, without losing any of your own changes.

---

## 1. Summary

- **All of your gateway customizations are kept.** We merged them into the new code and checked each one with a script (section 6). All 17 changed blocks in your server file are present.
- **Most of your gateway is not touched.** Your Dialogflow CX connectors, `main.py`, the monitoring dashboard, the TLS setup and your other files stay as they are. Of the eight code files in the package, four replace existing files and four are new (section 5).
- **Your Dialogflow CX agents behave as they do today.** In our test with your setup, the greeting played with barge-in on, the session transcript was filled in, and calling an agent by number ("1") still worked.
- **CES works through CVP:** greeting, conversation, end of call and transfer to an agent. We tested this end to end on CVP 15 / VVB in our lab.
- **Everything can be undone.** The installer backs up every file it replaces, and `tools/rollback.sh` restores them, along with the previous Python package versions if you ask it to.

One decision is needed from you:

> **Pick the name for the new CES agent.** `ces` is already used by your `dialogflow_cx_ces` connector. We suggest **`gecx`**. The CVP VirtualAgentVoice element uses this name as its Agent ID.

---

## 2. What we reviewed

| File you sent | What it showed |
|---|---|
| `check_compat.sh` output | Your gateway is not a stock Cisco install. Two core files have local changes |
| `server.diff` (your `wxcc_gateway_server.py` compared with Cisco 0f63e16) | About 180 lines of your own changes (section 3) |
| `base.diff` (your `i_vendor_connector.py` compared with Cisco 0f63e16) | One real change, `language_code`. The rest of the diff is line endings |
| `main.py`, `requirements.txt`, file listing, git log | Base release Cisco 0f63e16; repo `wxsd-sales/byova-dialogflow-agent`; no `health_service.py` |
| `dialogflow_cx_connector.py` | Workload identity federation is built in (`wif_config_path` / `GOOGLE_APPLICATION_CREDENTIALS`) |

---

## 3. Findings about your gateway

**Your own changes in `wxcc_gateway_server.py`, all kept:**

| # | Change | Why it matters |
|---|---|---|
| 1 | Session transcript (`User:` / `Agent:` lines in `session_transcript`) | Gives the agent desktop or reporting the conversation text |
| 2 | Barge-in forced on for every prompt, including the greeting and error prompts | CVP/VVB stops listening after a prompt that can't be interrupted. We found the same thing in our lab |
| 3 | gRPC activity tracking (`get_grpc_activity`) | Used by your monitoring dashboard |
| 4 | ListVirtualAgents and ProcessCallerInput INFO logging | Operations visibility |
| 5 | Agent selection by number ("1", "2") | CVP can select an agent by position |

**Other findings:**

- **Base class:** Cisco 0f63e16 plus `language_code` in `create_session_start_response`. Our package already includes that exact change.
- **Agent name conflict:** `ces` is taken (see section 1).
- **Concurrency:** `main.py` uses a gRPC pool of 10 threads, which allows about 10 simultaneous calls. That's unchanged from today. If you need more simultaneous CES calls, see `docs/main_py_optional_change.md`.
- **Google sign-in:** your Dialogflow CX connector uses workload identity federation. CES can use the same identity and credential file. No JSON key is needed.
- **Python 3.12.3** is supported.

---

## 4. Why the gateway code has to change for CES

| | Dialogflow CX (today) | Google CES |
|---|---|---|
| How the agent works | Turn by turn: the gateway collects audio, sends it, and gets one reply | Real-time streaming: caller audio flows continuously and the reply streams back |
| Who decides the caller has finished speaking | Dialogflow CX | **The gateway**, using voice-activity detection (Silero VAD) |
| Gateway support needed | What you have today | Cisco's newer streaming gateway server and the Cisco CES connector |

Cisco's CES connector (`gecx_connector.py`) only works with Cisco's newer gateway server, which has streaming audio, voice-activity detection and asynchronous replies. Your server is based on the older release, so CES can't simply be added beside it. We took Cisco's current server and put your changes back into it.

On top of that, CVP/VVB has two limits that Cisco's code doesn't handle, since it was written for Webex Contact Center:
1. **VVB plays one complete prompt per agent turn.** It can't play audio that arrives in small streamed pieces. The gateway now joins each CES reply into one WAV prompt.
2. **VVB needs prompts to be interruptible (barge-in)** to keep listening. This matches change #2 in your own code.

---

## 5. What changes on your gateway

| File | Action | What it means for you |
|---|---|---|
| `src/core/wxcc_gateway_server.py` | Replaced | Cisco's current server + **all your changes** + the CVP compatibility mode + passing CVP values such as `Name` to CES |
| `src/connectors/i_vendor_connector.py` | Replaced | All 23 of your existing methods are kept, including your `language_code` change. Cisco's version adds 13 new optional methods, which only CES uses |
| `src/core/virtual_agent_router.py` | Replaced | You had Cisco's unchanged original. The new Cisco version adds routing hooks for CES. Connectors with an empty agent list are skipped, and all of yours have agents |
| `src/core/health_service.py` | Added | Required by Cisco's current server. Your `main.py` doesn't need to change |
| `src/connectors/gecx_connector.py` | Added | Cisco's CES connector, plus: workload identity federation file support, `session_variables` (CVP → CES) and `forward_end_session_fields` (CES → CVP) |
| `src/utils/audio_normalizer.py`, `silero_speech_boundary.py`, `telephony_audio.py` | Added | Cisco helper modules for audio and voice-activity detection |
| `config/config.yaml` | You add one block | The `gecx_connector` block, placed last, so your existing agent numbers stay the same |
| Python packages | Added | CPU-only PyTorch, `silero-vad`, `google-cloud-ces`. About 1.5 GB disk and about 300 MB more memory |

### What is not touched

`main.py`, every Dialogflow CX connector (`dialogflow_cx_connector.py`, `was-dialogflow_cx_connector.py`, …), `google_ces_connector.py`, `local_audio_connector.py`, `my_connector.py`, `src/generated/`, the monitoring dashboard, the TLS configuration, logs, and the other files in `src/utils/`. The existing blocks in `config.yaml` also stay as they are.

---

## 6. Proof that your changes are kept

`verification/verify_preserved.py` reads **your own** `server.diff` (included as `verification/customer-server.diff`). It checks that every line you added is in the new server, and that the Cisco lines you removed are gone.

```
KEPT     @@ -6,8 +6,9 @@      (+2 lines)    threading / typing imports
KEPT     @@ -63,6 +64,9 @@    (+3 lines)   session transcript state
KEPT     @@ -137,7 +141,7 @@   (+1 lines)   greeting barge-in on
KEPT     @@ -391,6 +395,45 @@ (+36 lines)   transcript methods
KEPT     @@ -409,6 +452,9 @@  (+2 lines)    transcript update hook
KEPT     @@ -497,6 +543,9 @@  (+3 lines)    transcript on silence responses
KEPT     @@ -506,15 +555,8 @@ (+2 lines)   barge-in forced on audio prompts
KEPT     @@ -531,7 +573,7 @@  (+1 lines)    barge-in on text prompts
KEPT     @@ -642,6 +684,8 @@  (+1 lines)    transcript on prompt responses
KEPT     @@ -661,8 +705,18 @@ (+11 lines)   error prompt barge-in + transcript
KEPT     @@ -747,6 +801,14 @@ (+7 lines)    gRPC activity state
KEPT     @@ -809,6 +871,33 @@ (+24 lines)   get_grpc_activity / _record_grpc_activity
KEPT     @@ -844,7 +933,14 @@ (+8 lines)    ListVirtualAgents logging
KEPT     @@ -869,8 +965,9 @@  (+3 lines)    ListVirtualAgents logging
KEPT     @@ -909,13 +1006,26 @@ (+16 lines) ProcessCallerInput logging
KEPT     @@ -923,6 +1033,22 @@ (+16 lines)  agent selection by number

RESULT: all customer changes are present
```

Your `typing` import counts as kept because the new file imports the same names plus `Callable`, which Cisco's newer code needs. Cisco's original barge-in lines, which you removed, are also gone from the new file. As a control, running the same check against Cisco's unmodified server correctly reports your changes as missing.

You can re-run the check yourself on any copy:

```bash
python3 verification/verify_preserved.py verification/customer-server.diff src/core/wxcc_gateway_server.py
```

`patches/make_customer_server.py` is the script that built your server file. Each of its 15 edits names the exact change it applies.

---

## 7. Behaviour differences to be aware of

These are all deliberate, and none of them changes how your Dialogflow CX calls work today.

| Area | Difference | Impact on your Dialogflow CX calls |
|---|---|---|
| Server engine | Cisco's current design: separate threads read requests, process them and send responses | None seen in testing. Same responses, same events |
| Voice-activity detection | Only for CES | None: off for every other connector |
| CVP compatibility mode | Joins streamed audio into one prompt; drops gateway START/END_OF_INPUT events | None: Dialogflow CX sends complete prompts and none of those events |
| End/transfer events | Same names as your server (`session_ended`, `transfer_requested`). A transfer can now also carry `summary` | None |
| Wait after a final prompt | Cisco's server can wait for a spoken prompt to finish before sending a separate end/transfer message | None: your Dialogflow CX connector never sends a separate end/transfer message |
| Python packages | New packages are installed. Shared libraries (for example `protobuf`, `google-api-core`) may be upgraded | Low risk. `rollback.sh ... --restore-packages` restores the exact previous versions |

---

## 8. Test results

| Test | Where | Result |
|---|---|---|
| Your server customizations present | Script check against your `server.diff` | 17 of 17 blocks kept |
| Base class methods | Script check | 23 of 23 of your methods kept |
| Dialogflow CX call: greeting, barge-in, transcript | Container with the merged code and an old-style `main.py` like yours | Greeting played, `barge=True`, transcript filled |
| Agent selected by number ("1") | Same | Resolved to the first agent |
| CES call with `Name=Muhammad` from CVP | Same | `Name` reached CES as a session variable; greeting played as one WAV prompt |
| CES full call through CVP 15 / VVB | Our lab, real phone calls | Greeting, caller answer, confirmation, end of call, all working |
| Cisco unit tests for the CES connector | Container | 92 of 92 passed |
| Install and rollback on a plain Linux box | Container (Debian, Python 3.11, venv) | Install, calls and rollback all worked |
| Rollback restores package versions | Container | Previous version restored |

**Limits of our testing:**
- We haven't run this on your server.
- We tested workload identity federation up to the Google token exchange, using a test identity pool. Your own federation setup isn't available to us. The connector uses the same Google library calls as your Dialogflow CX connector.
- Your monitoring dashboard code wasn't part of the review. We kept every server method it could call.

---

## 9. How to install

Follow `INSTALL_FOR_YOUR_GATEWAY.md`. In short:
1. `git clone` this repo on the gateway server.
2. Run `tools/check_compat.sh`. It reports your two reviewed files as `CUSTOMIZED`, which is expected.
3. Run `tools/install.sh <gateway> python3 --force`. It backs up, installs the packages, copies the code and runs a smoke test. `--force` is safe here because the new files already contain your changes.
4. Add the `gecx_connector` block to `config.yaml`, using agent name `gecx` and your federation credential file.
5. Run the smoke test, restart the gateway, then make a simulated call with `tools/cvp_sim.py`.
6. Make a test call through CVP with Agent ID `gecx`.

**CES agent setup (in ces.cloud.google.com):** the agent must call `end_session` in the same response as its closing sentence, and escalate with `end_session(session_escalated=true, summary=...)` to hand the caller to an agent. Without this, CVP waits about 30 seconds after the last sentence. The full guide (`docs/CES_Adapter_Install_Guide_Linux_v2.1.docx`, section 3) explains it.

## 10. How to undo

```bash
/tmp/byova_ces/tools/rollback.sh /home/administrator/byova-dialogflow-agent/backups/pre-ces-<date> --restore-packages python3
# then restart the gateway the way you normally do
```

This restores the four replaced files, `config.yaml` and `main.py`, removes the four added files, and reinstalls the previous Python package versions.

## 11. Risks and recommendations

| Item | Recommendation |
|---|---|
| Install timing | Install in a maintenance window. The restart takes about 20 seconds without service |
| Test first | If you have a lab or non-production gateway, install there first |
| CES session quota | Google limits how quickly CES sessions can start. Ask Google for a higher quota before production traffic |
| Keypad (DTMF) input | Cisco's CES connector doesn't support keypad input yet. Callers must speak |
| Concurrency | About 10 simultaneous calls with the current `main.py`. Apply the optional change for more |
| Future Cisco updates | This code is Cisco's 20 Sep 2026 release (`dedf1c1`) plus your changes. Re-run `verify_preserved.py` after any future merge |

---

## Appendix: file checksums (SHA-256)

Compare these on the server with `sha256sum src/*/*.py` after installing.

```
a7f5781dee560714b93d3ede92edf79e1d2c7a634dcd53bcd0d602de27883c84  src/connectors/gecx_connector.py
57aed8b03f64d21a4577b7c83f1d3088c84bb487a888841ed5c091022e5c1942  src/connectors/i_vendor_connector.py
76c30770ac51d42d226c9659829f71f08d970118593f584de51c6c2b1a3a9577  src/core/health_service.py
d6094626f9fa295b27fd040c38db4a81ea1ca9092d980c23701debd53bf7e31b  src/core/virtual_agent_router.py
3eaafd785f2b444b8a82bfca6e2d11676812248766e8b4e72669dabe07cca69a  src/core/wxcc_gateway_server.py
41a82de8cdb80815bfc7acb0115fa84168b69a9eb2267dd4765a6713856b7ebf  src/utils/audio_normalizer.py
e6da483f962a1706b1f5f4f3f1de829673cb54edbb187a6f29d6302d47468cdb  src/utils/silero_speech_boundary.py
59d83965b2e96c5d90c025cb115f5f0ed312db0d3ba625474ad93dcdc6a36e29  src/utils/telephony_audio.py
```

The code is based on Cisco's `webex-byova-gateway-python` and is provided under the Cisco Sample Code License (`LICENSE`).
