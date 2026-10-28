# Manual update: CES values back to CVP on a normal end

This page shows how to make the parameter update **by hand**, editing your two installed files instead of copying in new ones. The result is the same as `UPDATE_PARAMETERS.md`. That page also covers the config lines, the CES agent setup and what CVP receives.

There are three edits in two files, and every edit **adds** lines. Nothing of yours is removed.

| # | File | Where | Change |
|---|---|---|---|
| 1 | `src/connectors/gecx_connector.py` | about line **1073** | +1 line |
| 2 | `src/connectors/gecx_connector.py` | about line **1668** | +7 lines |
| 3 | `src/core/wxcc_gateway_server.py` | about line **1333** | +4 lines, 1 log line extended |

Line numbers are for the version installed from this repo. They move down slightly after each edit in the same file, so search for the text rather than relying on the number.

> **Indentation matters in Python.** Copy the added lines with their leading spaces exactly as shown, using **spaces, not tabs**. The indentation of every added line must match the line above it.

---

## 0. Back up first

```bash
GW=/home/administrator/byova-dialogflow-agent
B=$GW/backups/pre-params-$(date +%Y%m%d-%H%M%S); mkdir -p $B
cp -p $GW/src/connectors/gecx_connector.py $GW/src/core/wxcc_gateway_server.py $GW/config/config.yaml $B/
echo "backup in $B"
```

---

## Edit 1 of 3: `src/connectors/gecx_connector.py`, normal end

**Find** (search for `message_type="session_end",`; there is only one):
```python
        return self.connector.create_response(
            conversation_id=self.conversation_id,
            message_type="session_end",
            text=response_text or "",
            barge_in_enabled=False,
            response_type="final",
        )
```

**Change to** (one line added before the closing parenthesis):
```python
        return self.connector.create_response(
            conversation_id=self.conversation_id,
            message_type="session_end",
            text=response_text or "",
            barge_in_enabled=False,
            response_type="final",
            **self._forwarded_end_session_fields(decision.metadata.get("end_session", {})),
        )
```

---

## Edit 2 of 3: `src/connectors/gecx_connector.py`, log line

**Find** (search for `return {"transfer_metadata": selected}`; there is only one):
```python
        fields = self._end_session_fields(metadata)
        selected = {k: v for k, v in fields.items() if k in allowed}
        return {"transfer_metadata": selected} if selected else {}
```

**Change to** (seven lines added between `selected = ...` and `return ...`):
```python
        fields = self._end_session_fields(metadata)
        selected = {k: v for k, v in fields.items() if k in allowed}
        missing = sorted(name for name in allowed if name not in selected)
        self.logger.info(
            "[%s] [GECX] end_session fields for CVP: %s%s",
            self.conversation_id,
            sorted(selected),
            f" (not sent by the agent: {missing})" if missing else "",
        )
        return {"transfer_metadata": selected} if selected else {}
```

---

## Edit 3 of 3: `src/core/wxcc_gateway_server.py`, `SESSION_END` metadata

> **Careful:** this file has **two** lines with `output_event.name = "session_ended"`. Edit **only the second one**, under `elif message_type == "session_end":` (around line 1333). **Don't** edit the first one, under `if message_type == "goodbye":` (around line 1301).

**Find** (the block under `elif message_type == "session_end":`):
```python
            elif message_type == "session_end":
                output_event = OutputEvent()
                output_event.event_type = OutputEvent.EventType.SESSION_END
                output_event.name = "session_ended"
                va_response.output_events.append(output_event)
                self.logger.info(
                    f"Sent SESSION_END event to WxCC for conversation {self.conversation_id} (session_end message)"
                )
                self.can_be_deleted = True
```

**Change to** (four lines added after `output_event.name`, and the log message extended to show the fields):
```python
            elif message_type == "session_end":
                output_event = OutputEvent()
                output_event.event_type = OutputEvent.EventType.SESSION_END
                output_event.name = "session_ended"
                # CES end_session fields (forward_end_session_fields) for the CVP application
                end_metadata = connector_response.get("transfer_metadata") or {}
                if isinstance(end_metadata, dict) and end_metadata:
                    output_event.metadata.update(end_metadata)
                va_response.output_events.append(output_event)
                self.logger.info(
                    f"Sent SESSION_END event to WxCC for conversation {self.conversation_id} (session_end message"
                    f"{', fields=' + str(sorted(end_metadata)) if isinstance(end_metadata, dict) and end_metadata else ''})"
                )
                self.can_be_deleted = True
```

The log change is optional. If you'd rather leave the `self.logger.info(...)` line as it was, only the four added lines are required.

---

## Check your edits before restarting

```bash
cd $GW
# 1. Python can still read both files (no output = OK)
python3 -m py_compile src/connectors/gecx_connector.py src/core/wxcc_gateway_server.py && echo "compile OK"

# 2. each edit is present exactly once
grep -c '_forwarded_end_session_fields(decision.metadata' src/connectors/gecx_connector.py   # expect 1
grep -c 'end_session fields for CVP'                       src/connectors/gecx_connector.py   # expect 1
grep -c 'end_metadata = connector_response.get'            src/core/wxcc_gateway_server.py    # expect 1
```

An `IndentationError` or `SyntaxError` from step 1 means one of the added lines has the wrong number of leading spaces. Fix it, or restore the backup from step 0.

**Optional:** compare with the reference files in this repo. No output means your edits match exactly:
```bash
diff $GW/src/connectors/gecx_connector.py /tmp/byova_ces/src/connectors/gecx_connector.py
diff $GW/src/core/wxcc_gateway_server.py  /tmp/byova_ces/src/core/wxcc_gateway_server.py
```

---

## Then

1. **Add the config lines** to your CES connector block. The block is in `UPDATE_PARAMETERS.md`, step 3: `session_variables` and `forward_end_session_fields`.
2. **Restart the gateway.**
3. **Make a test call**, then check:
   ```bash
   grep -E "Session variables|end_session fields for CVP|Sent SESSION_END" $GW/logs/gateway.log | tail -5
   ```

## Alternative: apply the same change as a patch

Instead of editing by hand, the same three edits are in `patches/params-normal-end.patch`. Apply it to the installed version:
```bash
cd /home/administrator/byova-dialogflow-agent
patch -p1 --dry-run < /tmp/byova_ces/patches/params-normal-end.patch   # check first: should print two "checking file" lines
patch -p1           < /tmp/byova_ces/patches/params-normal-end.patch
```
We tested that this patch applies cleanly to the version installed from this repo, and gives files identical to the updated ones.

## Undo

```bash
cp -p $B/gecx_connector.py $GW/src/connectors/
cp -p $B/wxcc_gateway_server.py $GW/src/core/
cp -p $B/config.yaml $GW/config/
# then restart the gateway
```
