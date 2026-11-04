# Update: get `ticket_number` from the CES agent into CVP (and see it in the log)

Use this when the CES agent returns a value such as `ticket_number` in `end_session` and you want it in CVP.

**Why you don't see it today.** Your log shows `EndSession metadata keys: ['params', 'reason', 'session_escalated']`. That means the agent did send `params`, but the gateway logs only the top-level key names, and it passes only the fields you list in `forward_end_session_fields` on to CVP. With no list, nothing is passed and no `end_session fields for CVP` line is written.

## What this update adds

Only `src/connectors/gecx_connector.py` changes (+19 lines, additions only):

| Log line | When | Shows |
|---|---|---|
| `[GECX] end_session params from agent: ['ticket_number']` | Every call where CES ends the session with `params` | Names only, so you can see what the agent sent |
| `[GECX] end_session fields for CVP: ['ticket_number']` | When `forward_end_session_fields` is set | Names of the fields passed to CVP (was already there) |
| `[GECX] end_session values for CVP (log_end_session_values is on): {'ticket_number': 'INC0012345'}` | Only if you set `log_end_session_values: true` | The **values**. Use this for testing only (see the warning below) |

`wxcc_gateway_server.py` is the same file as in [UPDATE_PARAMETERS.md](UPDATE_PARAMETERS.md). It puts the fields into the `SESSION_END` event when the call ends normally. If you already installed that update, copying it again does no harm.

## Steps

```bash
# 1. get the update
cd /tmp/byova_ces && git pull            # or: cd /tmp && rm -rf byova_ces && git clone https://github.com/mrehan2018/byova_ces.git

# 2. back up and copy the two files
GW=/home/administrator/byova-dialogflow-agent
B=$GW/backups/pre-ticket-$(date +%Y%m%d-%H%M%S); mkdir -p $B/src/connectors $B/src/core
cp -p $GW/src/connectors/gecx_connector.py $B/src/connectors/
cp -p $GW/src/core/wxcc_gateway_server.py  $B/src/core/
cp $GW/config/config.yaml $B/
cp /tmp/byova_ces/src/connectors/gecx_connector.py $GW/src/connectors/
cp /tmp/byova_ces/src/core/wxcc_gateway_server.py  $GW/src/core/
echo "backup in $B"

# 3. check that the new code is in place (each should print 1)
grep -c "end_session params from agent" $GW/src/connectors/gecx_connector.py
grep -c "fields=%s" $GW/src/core/wxcc_gateway_server.py
```

**4. config.yaml.** In your CES connector block (`gecx_connector_tc_anurag`), add these lines under `config:`, at the same indentation as `language_code`. If you already have a `forward_end_session_fields` list, add `ticket_number` to it rather than adding a second list.

```yaml
      forward_end_session_fields:   # CES end_session params -> CVP
        - ticket_number
      log_end_session_values: true  # TESTING ONLY: log the values. Remove after testing
```

**5. Restart the gateway** the way you normally do, then make a test call that reaches the point where the agent ends the session.

> **Warning:** `log_end_session_values: true` writes the values (ticket numbers and anything else you list) into `gateway.log`. That breaks Cisco's "never log values" rule and may be customer data. Remove the line (or set it to `false`) and restart once you have confirmed the value.

## CES agent setup

The agent must put the value in the `params` argument of `end_session`. For example, in the agent instructions:

```
After the ticket is created, call {@TOOL: end_session} with reason="success" and
params={"ticket_number": "{ticket_number}"}, then say the closing sentence.
```

- `{ticket_number}` is a CES variable that your tool sets (or put the value from the tool response directly into params).
- For a transfer, use `session_escalated=true` with the same `params`. CVP then receives the field on the transfer event.

## Check after a test call

```bash
grep -E "EndSession metadata keys|end_session params from agent|end_session fields for CVP|end_session values for CVP|Sent SESSION_END|Sent TRANSFER_TO_AGENT" $GW/logs/gateway.log | tail -8
```

Expected (normal end):
```
[GECX] EndSession metadata keys: ['params', 'reason']
[GECX] end_session params from agent: ['ticket_number']
[GECX] end_session fields for CVP: ['ticket_number']
[GECX] end_session values for CVP (log_end_session_values is on): {'ticket_number': 'INC0012345'}
Sent SESSION_END event to WxCC for conversation <call> (session_end message, fields=['ticket_number'])
```

| What you see | Meaning | Fix |
|---|---|---|
| `end_session params from agent: [...]` without `ticket_number` | The agent did not put it in `params` (maybe it used another name) | Fix the agent instruction, or list the name the agent actually uses |
| No `end_session params from agent` line | The agent ended without `params` | Fix the agent's `end_session` call |
| `end_session fields for CVP: [] (not sent by the agent: ['ticket_number'])` | Listed in config, but the agent didn't send it | Same as the first row |
| No `end_session fields for CVP` line | `forward_end_session_fields` is not set, or the gateway was not restarted | Step 4, then restart |
| Line present, but CVP doesn't get the value | The gateway side is OK | Check the CVP app (below) |

## What CVP receives

| How CES ends | CVP event | Metadata |
|---|---|---|
| `end_session(reason="success", params={"ticket_number": ...})` | `SESSION_END`, name `session_ended` | `ticket_number` |
| `end_session(session_escalated=true, params={"ticket_number": ...})` | `TRANSFER_TO_AGENT`, name `transfer_requested` | `ticket_number` (and `summary` if sent) |

The value always arrives as text. In the CVP application, read `ticket_number` from the virtual agent element's returned event data, the same way as any other field returned on `session_ended` / `transfer_requested`.

## Undo

```bash
cp -p $B/src/connectors/gecx_connector.py $GW/src/connectors/
cp -p $B/src/core/wxcc_gateway_server.py  $GW/src/core/
cp -p $B/config.yaml $GW/config/
# then restart the gateway
```

Tested: Cisco's CES connector tests pass. The one test that fails on Windows (a file-permission check) fails the same way without this change. With your server file, `ticket_number` reached CVP on both a normal end (`session_ended`) and a transfer (`transfer_requested`). Values were logged only with `log_end_session_values: true`.
