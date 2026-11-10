# What is different from Cisco's code

**In short:** this is Cisco's BYOVA gateway code (`webex/webex-byova-gateway-python`) with **additions**, plus three small fixes to bugs in Cisco's server code (listed in the table below). No other Cisco logic was removed or rewritten. Every gateway change you had made yourself is kept.

The additions:
- CVP/VVB audio compatibility;
- keyless Google sign-in (Workload Identity Federation);
- parameter passing between CVP and CES, which is **off unless you configure it**;
- a few log lines.

## Where the code comes from

| Part | Source |
|---|---|
| Gateway server, router, base connector, CES connector, audio helpers | Cisco's current release of `webex-byova-gateway-python` |
| Your own server changes (transcript, barge-in on every prompt, gRPC activity, logs, numeric agent IDs, `language_code`) | Your gateway (`wxsd-sales/byova-dialogflow-agent`). All are kept, and `verification/verify_preserved.py` checks each one |
| The additions below | This repo |

Your gateway was based on an older Cisco release. Cisco's CES connector needs Cisco's newer server, so your server file is Cisco's current server with your changes put back in. See [REPORT.md](REPORT.md) sections 4 to 6.

## What we added on top of Cisco

| Addition | File | Why | Default |
|---|---|---|---|
| **CVP compatibility:** CES audio pieces are joined into one WAV prompt, prompts are bargeable, and the gateway's START/END_OF_INPUT events are not sent | `src/core/wxcc_gateway_server.py` | Cisco's CES path streams audio in small pieces, which only Webex Contact Center accepts. VVB plays one complete prompt per turn | Always on (needed for CVP). Dialogflow CX calls are not affected |
| **Workload Identity Federation sign-in:** accepts a keyless (`external_account`) credential file in `service_account_key`. With no key set, Google default credentials (`GOOGLE_APPLICATION_CREDENTIALS`) are used, as in Cisco | `src/connectors/gecx_connector.py` | Cisco's connector expects a service-account JSON key, and you use WIF | Used only when such a file is present |
| **Base-class fixes:** voice detection off by default (only CES turns it on), and `create_session_start_response` accepts `language_code` | `src/connectors/i_vendor_connector.py` | Your Dialogflow CX connectors pass `language_code` | n/a |
| **CVP → CES values** (`session_variables`, e.g. `Name` → `customer_name`) | `gecx_connector.py`, `wxcc_gateway_server.py` | Pass caller data from CVP to the CES agent | **Off** unless set in config.yaml |
| **CES → CVP values** (`forward_end_session_fields`, e.g. `ticket_number`) on a transfer and on a normal end | `gecx_connector.py`, `wxcc_gateway_server.py` | Return agent data to CVP. Only the fields you list are passed | **Off** unless set in config.yaml |
| **Log lines:** call lifecycle, the names of the values passed, and `end_session params from agent` | both files | Troubleshooting | Names only, never values |
| **`log_end_session_values`:** logs the values of the passed fields | `gecx_connector.py` | Testing only | **Off.** Turn it on only for a test call |
| **Bug fix: continued caller speech** really opens a new CES turn ([UPDATE_CONTINUED_SPEECH.md](UPDATE_CONTINUED_SPEECH.md)) | `wxcc_gateway_server.py` | Cisco's code never ran the connector's "speech started" step here, so CES never heard the caller and replies were dropped until the 30 s timeout. Same bug in Cisco's current release | Always on (CES only) |
| **Bug fix: CVP re-entry** after a session ended starts a fresh session | `wxcc_gateway_server.py` | The re-entry was ignored and VVB waited 15 s (`error.noresource`) | Always on |
| **Bug fix: clean-up race** when the caller hangs up | `wxcc_gateway_server.py` | Two streams cleaning up the same call raised `KeyError` in the log | Always on |

## Cisco's rules that we follow

Cisco's handoff rules (in their `docs/BYOVA_HANDOFF_CONTEXT.md`) are:
- **Allowlist:** only named fields are passed. We do the same.
- **Never log values:** we log names only, unless you turn on `log_end_session_values` for testing.
- **Limit the size of passed values:** we don't add a limit. Keep the fields short (IDs, numbers, short text).

## What is not touched

`main.py`, your Dialogflow CX connectors, the other connectors, `src/generated/`, the monitoring dashboard, TLS, and your existing `config.yaml` blocks.

## More detail

- [REPORT.md](REPORT.md): the full review, the file-by-file changes (section 5), behaviour differences (section 7) and test results (section 8).
- `patches/`: diffs against Cisco's original files.
- `verification/`: your original server changes and the script that proves they are kept.

The code is under the Cisco Sample Code License (see `LICENSE`).
