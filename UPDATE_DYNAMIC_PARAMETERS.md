# Update: pass parameters between CVP and CES without listing them

Today every value you pass needs its name in `config.yaml`: one line per CVP parameter in `session_variables`, one line per returned field in `forward_end_session_fields`. A new parameter means a config edit and a gateway restart.

This update adds two settings that remove the lists:

| Setting | Direction | What it does |
|---|---|---|
| `session_variables: "auto"` | CVP → CES | Sends the caller number, the dialed number, and every parameter set in the CVP Virtual Agent Voice element |
| `forward_end_session_fields: "*"` | CES → CVP | Sends every field the agent puts in the `end_session` `params` back to CVP |

After this, adding a parameter needs a change only in the CVP application and in the CES agent. The gateway is not touched.

## What changes

Only **`src/connectors/gecx_connector.py`** changes: 131 lines added, 3 replaced, in 9 places. No other file, no new package, no change to audio, speech detection, timing or call handling.

Both settings are **off until you set them**. The lists and mappings you have today keep working exactly as before, so you can install the code first and switch the config later.

## How "auto" names the CES variables

| CVP sends | CES variable | Notes |
|---|---|---|
| `sipHeader.CALL_ANI` | `caller_ani` | Only the number is sent: `sip:+15551230001@10.0.0.1:5060` becomes `+15551230001` |
| `sipHeader.CALL_DNIS` | `caller_dnis` | Same clean-up |
| Any other `sipHeader.*` | not sent | |
| A parameter you set in the element, for example `Name` | Same name: `Name` | The name must use letters, digits and `_` only, and not start with a digit |
| A parameter with a space or other character in its name | not sent | The name is written to the log as skipped |
| A structured value such as `userData` | not sent | The name is written to the log as skipped |

Declare each variable you want to use in the CES app (type Text) under the same name, and use it in instructions as `{Name}`. In our test, CES ignored variables that were sent but not declared, and the call continued normally.

**If you use a mapping today that renames a parameter** (for example `Name: customer_name`), "auto" sends it as `Name`. Either rename the parameter in CVP to `customer_name`, or declare `Name` in CES. Or keep your mapping: it still works.

## How "*" chooses the returned fields

It sends every text, number or true/false value inside `params` of the agent's `end_session` call:

```
end_session(reason="...", params={"ticket_number": "INC0012345", "zipcode": "75063"})
```

Top-level fields such as `reason` are not sent in this mode, and nested values are skipped. `summary` on a transfer is sent as before. In CVP the values arrive in the same place as today: the `end_session` element data on a normal end, and the transfer metadata on a transfer.

If the agent ends the session without `params`, nothing is returned. That is decided by the agent's instructions, not by the gateway.

## Limits

The two automatic settings have limits, so that an unexpected parameter cannot send a large amount of data to CES or to CVP.

| Limit | Default | Config key (optional) |
|---|---|---|
| Number of parameters per call, in each direction | 20 | `dynamic_parameter_max_count` |
| Length of one value | 256 characters | `dynamic_parameter_max_chars` |

- A value that is too long is **left out, not cut**. A shortened account or ticket number would be a wrong value, and a missing one is easier to notice.
- When there are too many parameters, the first ones are kept in the order they arrive. `caller_ani` and `caller_dnis` are always counted first.
- Every name that was left out is written to the log as a warning (names only).
- The limits apply only to `"auto"` and `"*"`. Names you list yourself in `config.yaml` are not limited, so your current setup behaves as before.

To change a limit, add the key under the same `config:` block, for example:

```yaml
      dynamic_parameter_max_count: 10
      dynamic_parameter_max_chars: 100
```

## Steps

Pick **one** of the three ways in step 2. All three give the same file.

```bash
# 1. get the update and back up
cd /tmp/byova_ces && git pull            # or: cd /tmp && rm -rf byova_ces && git clone https://github.com/mrehan2018/byova_ces.git
GW=/home/administrator/byova-dialogflow-agent
B=$GW/backups/pre-dynamic-params-$(date +%Y%m%d-%H%M%S); mkdir -p $B
cp -p $GW/src/connectors/gecx_connector.py $GW/config/config.yaml $B/
echo "backup in $B"

# 2a. script (recommended): 9 anchored edits, changes nothing else, safe to run twice.
#     If you installed the first version of this update (19 Nov), it adds only the 4 limit edits.
python3 /tmp/byova_ces/tools/apply_dynamic_parameters.py $GW/src/connectors/gecx_connector.py

# 2b. or the patch (only for a file that has no part of this update yet; the dry run stops otherwise)
cd $GW && patch -p1 --dry-run < /tmp/byova_ces/patches/dynamic-parameters.patch && patch -p1 < /tmp/byova_ces/patches/dynamic-parameters.patch

# 2c. or copy the whole file (only if your gecx_connector.py is the one from this repo, unchanged)
cp /tmp/byova_ces/src/connectors/gecx_connector.py $GW/src/connectors/

# 3. check (must print 6, then nothing)
grep -c "byova_ces dynamic parameters" $GW/src/connectors/gecx_connector.py
python3 -m py_compile $GW/src/connectors/gecx_connector.py
```

If the script prints `anchor found 0 times`, it wrote nothing. Send us that line.

**4. Config.** In `config.yaml`, in your CES connector block under `config:` (same level as `language_code`), replace the two lists with:

```yaml
      session_variables: "auto"
      forward_end_session_fields: "*"
```

Keep the quotes. You can change one direction and leave the other as a list.

**5. Restart the gateway**, then place one test call.

## What to look for in the log

```bash
grep -E "Session variables for|end_session fields for CVP" $GW/logs/gateway.log | tail -5
```

| Line | Meaning |
|---|---|
| `[GECX] Session variables for <id> (auto): ['Name', 'caller_ani', 'caller_dnis']` | These names were sent to CES |
| `... (skipped, name or value not usable: ['userData'])` | These were not sent |
| `[GECX] end_session fields for CVP: ['ticket_number', 'zipcode']` | These names were returned to CVP |

| `[GECX] Session variables for <id> NOT sent to CES, over the limit (20 parameters, 256 characters each): ['notes']` | These were left out by a limit |
| `[GECX] end_session fields NOT sent to CVP, over the limit (20 fields, 256 characters each): ['notes']` | Same, for the return direction |

Only names are logged, never values (unless you turned on `log_end_session_values` for a test).

No `end_session fields for CVP` line on a call means the agent sent no `params`. Check the line `EndSession metadata keys` for that call: it must include `params`.

## Undo

```bash
cp -p $B/gecx_connector.py $GW/src/connectors/ && cp -p $B/config.yaml $GW/config/
```

Then restart the gateway. To turn the feature off without removing the code, put your lists back in `config.yaml` and restart.

## How it was tested

- 18 new tests in `verification/tests/test_byova_dynamic_parameters.py`: both new settings, the name and value rules, the two limits, names-only logging, and that lists, mappings and the default behave as before.
- The connector's existing 92 tests give the same result before and after.
- Live calls on our lab gateway behind CVP/VVB: the caller's name reached the CES agent in "auto" mode, and `account_name` and `zipcode` came back to CVP in `end_session`.
