# CES for your gateway (byova-dialogflow-agent)

This package was made for **your** gateway, `/home/administrator/byova-dialogflow-agent` (repo `wxsd-sales/byova-dialogflow-agent`). We reviewed the files you sent.

## What's different from the general package

`src/core/wxcc_gateway_server.py` keeps **all of your own changes**:
- the session transcript;
- barge-in forced on for every prompt, including the greeting;
- gRPC activity tracking for your dashboard (`get_grpc_activity`);
- ListVirtualAgents / ProcessCallerInput logging;
- numeric agent IDs ("1", "2").

It adds the CES support on top: Cisco's streaming server, the CVP/VVB compatibility mode, and passing session parameters such as `Name`. `patches/make_customer_server.py` shows exactly what was added.

`src/connectors/i_vendor_connector.py` keeps your `language_code` change. Your Dialogflow CX connectors are not touched.

We tested it with your setup:
- **Dialogflow CX:** the greeting played, barge-in was on, the transcript was filled, and agent number "1" worked.
- **CES:** the greeting played with `Name` passed.

## Steps

0. **Get the code** onto the gateway server:
   ```bash
   cd /tmp && git clone https://github.com/mrehan2018/byova_ces.git
   ```
   No git on the server? Download the ZIP from the GitHub page (Code → Download ZIP), copy it to `/tmp`, and unzip it to `/tmp/byova_ces`.
1. **Pre-check.** It reports `CUSTOMIZED` for `wxcc_gateway_server.py` and `i_vendor_connector.py`, and that is expected: those are the two files we reviewed and merged.
   ```bash
   cd /tmp/byova_ces && chmod +x tools/*.sh
   ./tools/check_compat.sh /home/administrator/byova-dialogflow-agent python3
   ```
2. **Install with `--force`.** This is safe here, for three reasons: the new files already contain your changes, every replaced file is backed up first, and `rollback.sh` restores them.
   ```bash
   ./tools/install.sh /home/administrator/byova-dialogflow-agent python3 --force
   ```
3. **Config.** In `config/config.yaml`, add the block from `config/gecx_connector.snippet.yaml` as the **last** connector:
   - **Agent name:** use `gecx`, not `ces`. Your `dialogflow_cx_ces` connector already uses `ces`. Use the same name as the CVP Agent ID.
   - **Google sign-in (workload identity federation):** set `service_account_key` to the **same path** as `wif_config_path` in your Dialogflow CX blocks. Or delete the line if your gateway uses `GOOGLE_APPLICATION_CREDENTIALS`. The identity needs the role **CES Client** (`roles/ces.client`).
   - **Optional:** `session_variables: ["Name"]` to send `Name` from CVP to CES. The CES app must declare a `Name` variable (Text).
4. **Smoke test, then restart the gateway the way you normally do.**
   ```bash
   cd /home/administrator/byova-dialogflow-agent
   python3 /tmp/byova_ces/tools/smoke_test.py --gateway-dir . --check-credentials
   ```
5. **Simulated call** (your gRPC port is 50052 unless `gateway.port` says otherwise):
   ```bash
   python3 /tmp/byova_ces/tools/cvp_sim.py --gateway-dir . localhost:50052 gecx 3 --param Name=Muhammad
   ```

**Undo:** `/tmp/byova_ces/tools/rollback.sh /home/administrator/byova-dialogflow-agent/backups/pre-ces-<date> --restore-packages python3`, then restart the gateway. `--restore-packages` also puts back the exact Python package versions from before the install.

The full guide is `docs/CES_Adapter_Install_Guide_Linux_v2.1.docx`.
