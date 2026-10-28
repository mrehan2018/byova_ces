# Update: pass values between CVP and the CES agent

For gateways that already run the CES adapter from this repo. This update adds one thing: **CES can send values back to CVP when the call ends normally.** Before, values could go back only on a transfer.

## What needs what

| Feature | Code update needed? | What to configure |
|---|---|---|
| CVP → CES (e.g. `Name` → CES variable `customer_name`) | **No**, already in your installed code | `session_variables` in config.yaml |
| CES → CVP on a **transfer** | **No**, already in your installed code | `forward_end_session_fields` in config.yaml |
| CES → CVP on a **normal end** | **Yes**: this update (2 files) | `forward_end_session_fields` in config.yaml |

## The code change (2 files, additions only)

- `src/connectors/gecx_connector.py` (+8 lines): on a normal end, the listed `end_session` fields are also forwarded, and one log line shows which fields were sent: `[GECX] end_session fields for CVP: [...]`.
- `src/core/wxcc_gateway_server.py` (+6 lines, 1 log line extended): those fields go into the metadata of the `SESSION_END` event (`session_ended`) that CVP receives.

All of your own server changes are still present. You can check with `python3 verification/verify_preserved.py verification/customer-server.diff src/core/wxcc_gateway_server.py`.

## Steps

> Prefer to edit the two files by hand? See **[MANUAL_UPDATE_PARAMETERS.md](MANUAL_UPDATE_PARAMETERS.md)**: three small edits, or one patch file.

```bash
# 1. get the update
cd /tmp/byova_ces && git pull            # or: cd /tmp && rm -rf byova_ces && git clone https://github.com/mrehan2018/byova_ces.git

# 2. back up the two files and copy the new ones in
GW=/home/administrator/byova-dialogflow-agent
B=$GW/backups/pre-params-$(date +%Y%m%d-%H%M%S); mkdir -p $B/src/connectors $B/src/core
cp -p $GW/src/connectors/gecx_connector.py $B/src/connectors/
cp -p $GW/src/core/wxcc_gateway_server.py $B/src/core/
cp $GW/config/config.yaml $B/
cp /tmp/byova_ces/src/connectors/gecx_connector.py $GW/src/connectors/
cp /tmp/byova_ces/src/core/wxcc_gateway_server.py  $GW/src/core/
echo "backup in $B"
```

**3. config.yaml.** In your CES connector block (e.g. `gecx_connector_tc_anurag`), add these lines under `config:`, at the same indentation as `language_code`:

```yaml
      session_variables:            # CVP value -> CES variable
        Name: customer_name
      forward_end_session_fields:   # CES end_session params -> CVP event metadata
        - account_name
        - zipcode
```

**4. Restart the gateway** the way you normally do.

## CES agent setup

- **CVP → CES:**
  - Declare the variable `customer_name` (Text) in the CES app.
  - Use it in the instructions with **single braces**: `{customer_name}`, for example: `"Hello {customer_name}, please say or enter the 3 or 4 digit CVV present on your card."`
- **CES → CVP:**
  - The agent puts the values in the `params` argument of `end_session`, for example:
    ```
    In ONE response, call {@TOOL: end_session} with reason="success" and
    params={"account_name": "{account_name}", "zipcode": "{zipcode}"},
    then say the closing sentence.
    ```
  - `{account_name}` and `{zipcode}` here are CES variables, with default values for a static test.
  - Only the fields listed in `forward_end_session_fields` are passed to CVP.

## What CVP receives

| How CES ends | CVP event | Metadata |
|---|---|---|
| `end_session(reason="success", params={...})` | `SESSION_END`, name `session_ended` | `account_name`, `zipcode` |
| `end_session(session_escalated=true, params={...})` | `TRANSFER_TO_AGENT`, name `transfer_requested` | `account_name`, `zipcode` (and `summary` if sent) |

All values arrive as text.

## Check after a test call

```bash
grep -E "Session variables|end_session fields for CVP|Sent SESSION_END" $GW/logs/gateway.log | tail -5
```
Expected:
```
[GECX] Session variables for <call>: ['customer_name']
[GECX] end_session fields for CVP: ['account_name', 'zipcode']
Sent SESSION_END event to WxCC for conversation <call> (session_end message, fields=['account_name', 'zipcode'])
```
If a field is missing, the second line says `(not sent by the agent: [...])`. In that case, check the agent's `end_session` call.

## Undo

```bash
cp -p $B/src/connectors/gecx_connector.py $GW/src/connectors/
cp -p $B/src/core/wxcc_gateway_server.py  $GW/src/core/
cp -p $B/config.yaml $GW/config/
# then restart the gateway
```

Tested: Cisco's 92 CES connector tests pass. Normal end, transfer and the default (no setting) were checked with your server file. On our own CVP gateway, the same feature was confirmed on a live call: `Name` in, `account_name` and `zipcode` back.
