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

> Prefer to edit the code by hand instead of copying files? Do steps 1–3 from **[Manual code update](#manual-code-update-instead-of-copying-files)** below, then continue with step 4 here.

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
grep -c "', fields='" $GW/src/core/wxcc_gateway_server.py
```

**4. config.yaml.** In your CES connector block (`gecx_connector_tc_anurag`), add these lines under `config:`, at the same indentation as `language_code`. If you already have a `forward_end_session_fields` list, add `ticket_number` to it rather than adding a second list.

```yaml
      forward_end_session_fields:   # CES end_session params -> CVP
        - ticket_number
      log_end_session_values: true  # TESTING ONLY: log the values. Remove after testing
```

**5. Restart the gateway** the way you normally do, then make a test call that reaches the point where the agent ends the session.

> **Warning:** `log_end_session_values: true` writes the values (ticket numbers and anything else you list) into `gateway.log`. That breaks Cisco's "never log values" rule and may be customer data. Remove the line (or set it to `false`) and restart once you have confirmed the value.

## Manual code update (instead of copying files)

You edit only `src/connectors/gecx_connector.py`, and every edit **adds** lines. Nothing of yours is removed. After the edits, go back to **step 4** (config.yaml) above.

### M1. Back up and check what you already have

```bash
GW=/home/administrator/byova-dialogflow-agent
B=$GW/backups/pre-ticket-$(date +%Y%m%d-%H%M%S); mkdir -p $B
cp -p $GW/src/connectors/gecx_connector.py $GW/src/core/wxcc_gateway_server.py $GW/config/config.yaml $B/
echo "backup in $B"

grep -c "end_session fields for CVP" $GW/src/connectors/gecx_connector.py   # must print 1
grep -c "', fields='"               $GW/src/core/wxcc_gateway_server.py     # must print 1
```

If either prints **0**, the parameters update is not installed. Do **[MANUAL_UPDATE_PARAMETERS.md](MANUAL_UPDATE_PARAMETERS.md)** first (its 3 edits), then come back here.

### M2. Option A: apply the patch (one command)

```bash
cd /tmp/byova_ces && git pull
cd $GW
patch -p1 --dry-run < /tmp/byova_ces/patches/ticket-number-logging.patch   # check only, changes nothing
patch -p1          < /tmp/byova_ces/patches/ticket-number-logging.patch   # apply
```

If the dry run reports `FAILED` or `Reversed (or previously applied) patch detected`, answer `n` if asked, apply nothing, and use Option B instead.

### M2. Option B: three hand edits

> **Indentation matters in Python.** Copy the added lines with their leading spaces exactly as shown, using **spaces, not tabs**.

| # | Where (search for this text) | Change |
|---|---|---|
| 1 | `self.forward_end_session_fields = [` (about line 2016) | +3 lines |
| 2 | `EndSession metadata keys` (about line 1810) | +8 lines |
| 3 | `return {"transfer_metadata": selected}` (about line 1676) | +8 lines |

Line numbers move slightly after each edit, so search for the text rather than relying on the number.

**Edit 1 of 3: the new setting.** Find:
```python
        self.forward_end_session_fields = [
            str(name) for name in (config.get("forward_end_session_fields") or [])
        ]
```
Change to (3 lines added below it):
```python
        self.forward_end_session_fields = [
            str(name) for name in (config.get("forward_end_session_fields") or [])
        ]
        # Test aid: also log the VALUES of the forwarded fields. Off by default
        # (Cisco rule: never log values); turn off again after testing.
        self.log_end_session_values = bool(config.get("log_end_session_values", False))
```

**Edit 2 of 3: log the param names from the agent.** Find:
```python
        self.logger.info(
            "[%s] [GECX] EndSession metadata keys: %s",
            conversation_id,
            sorted(metadata),
        )
```
Change to (8 lines added below it):
```python
        self.logger.info(
            "[%s] [GECX] EndSession metadata keys: %s",
            conversation_id,
            sorted(metadata),
        )
        end_params = metadata.get("params")
        if isinstance(end_params, Mapping):
            # Names only, never values (e.g. ['ticket_number']).
            self.logger.info(
                "[%s] [GECX] end_session params from agent: %s",
                conversation_id,
                sorted(str(k) for k in end_params),
            )
```
(`Mapping` is already imported at the top of the file: `from collections.abc import Mapping`.)

**Edit 3 of 3: optional value log.** Find:
```python
            f" (not sent by the agent: {missing})" if missing else "",
        )
        return {"transfer_metadata": selected} if selected else {}
```
Change to (8 lines added before the `return`):
```python
            f" (not sent by the agent: {missing})" if missing else "",
        )
        if selected and getattr(self.connector, "log_end_session_values", False):
            # Test aid only (config log_end_session_values: true). Values can hold
            # customer data, so keep this off in production.
            self.logger.warning(
                "[%s] [GECX] end_session values for CVP (log_end_session_values is on): %s",
                self.conversation_id,
                selected,
            )
        return {"transfer_metadata": selected} if selected else {}
```

### M3. Check the edits

```bash
cd $GW
python3 -m py_compile src/connectors/gecx_connector.py && echo "syntax OK"
grep -c "log_end_session_values = bool" src/connectors/gecx_connector.py      # 1
grep -c "end_session params from agent" src/connectors/gecx_connector.py      # 1
grep -c "end_session values for CVP"    src/connectors/gecx_connector.py      # 1
```

If `py_compile` shows `IndentationError` or `SyntaxError`, fix the line it names (usually tabs or wrong spaces), or restore the backup: `cp -p $B/gecx_connector.py $GW/src/connectors/`.

Now continue with **step 4** (config.yaml) and **step 5** (restart) above.

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

If you used the **manual** steps, the backup is flat: `cp -p $B/gecx_connector.py $GW/src/connectors/` (and `$B/config.yaml` back to `$GW/config/`), then restart.

Tested: Cisco's CES connector tests pass. The one test that fails on Windows (a file-permission check) fails the same way without this change. With your server file, `ticket_number` reached CVP on both a normal end (`session_ended`) and a transfer (`transfer_requested`). Values were logged only with `log_end_session_values: true`.
