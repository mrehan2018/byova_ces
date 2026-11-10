# Update: CES stops answering for 30 seconds, CVP re-entry gets no answer, and a KeyError on hang-up

This update fixes three gateway problems that we found in your gateway logs of 6 and 10 November 2026. The first two make callers wait in silence. The third writes an error to the log when a caller hangs up. The fix changes one file, `src/core/wxcc_gateway_server.py`: it adds 66 lines and changes 5. You don't need to change `config.yaml`.

| Problem | What the caller experiences | Fixed by |
|---|---|---|
| **1. Continued speech is not sent to CES** | The caller answers, then hears **about 30 seconds of silence**, and the CES session ends with no reply | This update |
| **2. CVP re-entry right after a session ends is ignored** | CVP reopens the virtual agent for the same call, and **VVB waits about 15 seconds** (`error.noresource`) | This update |
| **3. `KeyError` when the caller hangs up** | Nothing the caller notices. The log shows `grpc._server - ERROR - Exception iterating responses` with a `KeyError` in `_cleanup_conversation` | This update |

All three problems are in Cisco's gateway code, the same as in Cisco's current release (`eb2a1e3`). Our additions didn't cause them.

## 1. Why the caller heard 30 seconds of silence

### What happened in your call

Times from your log for the call that started at 20:42:36. Every line in the right column is a real log message:

| Time | What happened | Log line |
|---|---|---|
| 20:42:39.5 | The greeting (5.3 s) goes to VVB and plays until about 20:42:45 | `[CVP] Coalesced streamed audio … (~5.3s)` |
| 20:42:42.35 | **During the greeting, the gateway hears a very short sound** (about 0.2 s: a cough, "uh" or line noise) and treats it as the caller's answer | `gateway_caller_speech_start_detected` |
| 20:42:44.4 | That sound is sent to CES as the caller's turn. CES finds no words in it, so it never sends back a transcript | `gecx_caller_endpoint_committed … caller_audio_bytes=13180` |
| 20:42:46.4 to 20:42:52.5 | **The caller gives the real answer (about 6 s).** The gateway sees that CES is still working on the noise turn and tells the CES connector to open a new turn for this speech | `Continued caller speech while the CES response was pending` |
| | **Because of the bug, the connector never opens that turn.** The caller's audio stays in a 0.5-second buffer and is never sent to CES. There is no `gecx_caller_speech_start … input_turn=2` line | (missing) |
| 20:42:55.7 and 20:43:12.0 | CES speaks twice, probably "I didn't catch that". The gateway throws both replies away, because it waits for CES to confirm a transcript of the noise turn, and that never comes | `gecx_pre_input_output_suppressed` (twice) |
| 20:43:14.4 | 30 seconds after the noise turn, the gateway gives up and ends the session with no audio | `Timed out after 30.0s waiting for turn completion` |

### The bug, in plain terms

Cisco designed this case well. If the caller speaks again before the reply is ready, the gateway opens a **new turn**, sends the new speech to CES, and waits for CES to answer that. The log line `Continued caller speech…` shows that the gateway decided to do this.

But the instruction to the connector is written so that it **never runs**. The connector's "open a new turn" code only runs when the gateway reads the connector's answer to that instruction, and in this one place the gateway never reads it. So the gateway believes a new turn is open, and the connector never opened one.

### The bug, for developers

`ConversationProcessor._continue_pending_speech_turn()` calls `router.route_request(…, "handle_speech_boundary", …)` with `speech_started`. `GECXConnector.handle_speech_boundary()` is a **generator function** (it contains `yield`). Calling a generator function only creates a generator object, and its body runs only when the generator is iterated. This call site never iterates the result, so `stream_session.begin_input_turn(expect_recognition=True)` is never called.

Cisco's own unit test for this path uses a mock router that returns `None` for `speech_started`, so the test can't detect it. Our new test uses a real generator and Cisco's real `GECXConnector`:

| | `begin_input_turn` calls |
|---|---|
| Called the way the gateway calls it (before the fix) | **0** |
| Result iterated (after the fix) | **1** |

### When it happens

Only when the caller (or a noise) starts speaking **after** a turn was sent to CES and **before** CES's reply is played. A noise or a cough during the greeting is the usual trigger, and callers who pause and then keep talking can also trigger it.

## 2. Why VVB waited 15 seconds after a session ended

In the same call, the session ended at 20:43:14.4. **0.9 seconds later** CVP opened a new virtual-agent session for the same call (same conversation ID):

```
20:43:14,385  Sent SESSION_END event to WxCC for conversation <call>
20:43:15,309  ProcessCallerInput stream started (conversation_id=<call>, ...)
20:43:15,309  SESSION_START event received but session already started for conversation <call>
```

The old session was still being cleaned up (that takes up to 2 seconds), so the gateway treated the new `SESSION_START` as a duplicate and **answered nothing**. VVB then waits about 15 seconds and reports `error.noresource`.

With the update, a `SESSION_START` that arrives after the session has ended closes the old session and **starts a fresh one**. The caller gets a greeting instead of silence.

## 3. Why the log showed a KeyError when the caller hung up

In your call of 10 November, the caller hung up during a greeting. Within 60 ms, two gateway streams for that call finished:

```
16:39:50,578  gecx_end_conversation ... reason=client_cancelled      (the stream that was playing the greeting)
16:39:50,639  Processing SESSION_END event for conversation <call>    (CVP's SESSION_END, on a new stream)
16:39:50,664  grpc._server - ERROR - Exception iterating responses: '<call>'
              ... _cleanup_conversation ... del self.conversations[conversation_id]
              KeyError: '<call>'
```

Both streams cleaned up the same call. Cisco's clean-up checks that the call is there, runs the connector's clean-up (which takes a moment), and then deletes the entry. The other stream had already deleted it, so the second delete failed. The caller had already gone and `SESSION_END` had been sent, so it only adds an error to the log.

With the update, the entry is removed only if it is still there and is still the same session, so the second clean-up does nothing. This also protects the fresh session from problem 2: a slow clean-up of the old session can't remove the new one.

## What the update changes

One file, `src/core/wxcc_gateway_server.py`, 6 small edits (66 lines added, 5 lines changed).

| # | Where | Change |
|---|---|---|
| 1 | `ConversationProcessor.__init__` | A holder for responses from the new turn (normally empty) |
| 2 | `_continue_pending_speech_turn` | **Runs** the connector's "speech started" code, so the new turn really opens |
| 3 | `_process_audio_input` | Passes on any response from step 2 (only happens if the session already ended) |
| 4 | `ProcessCallerInput`, when a stream starts | `SESSION_START` for a session that already ended: close it and start a fresh session |
| 5 | `ProcessCallerInput`, when a stream finishes | The old stream doesn't clean up the new session that replaced it |
| 6 | `_cleanup_conversation` | Two clean-ups of the same call no longer raise `KeyError`, and a clean-up never removes a session that replaced it |

**What stays the same:**
- Normal calls behave exactly as before.
- Change 2 applies only to CES. Dialogflow CX doesn't use this code path.
- Change 4 applies to any agent, but only to a `SESSION_START` after a session has ended. Before, that was ignored.
- Change 6 applies to any agent, but only when two clean-ups of the same call overlap.
- Your config, your Dialogflow CX connectors, `main.py` and the CES connector file are not changed.

## What this update does not fix

| Seen in your logs | Where to fix it |
|---|---|
| **After a transfer, CVP sends the caller back into the virtual agent.** In one call, each new session started less than a second after the transfer message finished playing, and the caller heard the greeting again (twice) | The CVP script: after VirtualAgentVoice exits with a transfer (`TRANSFER_TO_AGENT`, name `transfer_requested`), it must go to the queue. The gateway sends the same transfer event as your Dialogflow CX connector |
| Each turn takes about 3.5 to 8 seconds; long replies make it worse (a 27-second transfer message) | Mostly reply length: VVB can only play a complete prompt, so the gateway waits until CES has finished generating it. Shorter agent replies (especially the transfer message) help the most |
| A 0.2-second noise is taken as an answer | Optional setting, after testing: `voice_activity_detection.start_debounce_ms` from `96` to about `200`. It also makes very short answers like "yes" register slightly later |

## Install

```bash
# 1. get the update
cd /tmp/byova_ces && git pull            # or: cd /tmp && rm -rf byova_ces && git clone https://github.com/mrehan2018/byova_ces.git

# 2. back up
GW=/home/administrator/byova-dialogflow-agent
B=$GW/backups/pre-continued-speech-$(date +%Y%m%d-%H%M%S); mkdir -p $B
cp -p $GW/src/core/wxcc_gateway_server.py $B/
echo "backup in $B"

# 3. is your file exactly the one from the ticket_number update?
git -C /tmp/byova_ces show e7dbbc4:src/core/wxcc_gateway_server.py | cmp -s - $GW/src/core/wxcc_gateway_server.py \
  && echo "SAME: use option A" || echo "DIFFERENT: use option B or C"
```

**Option A: copy the file.** Use this only if step 3 printed `SAME`.
```bash
cp /tmp/byova_ces/src/core/wxcc_gateway_server.py $GW/src/core/
```

**Option B: apply the patch.** Use this if you have edited the file yourself.
```bash
cd $GW
patch -p1 --dry-run < /tmp/byova_ces/patches/continued-speech-reentry.patch   # check only
patch -p1          < /tmp/byova_ces/patches/continued-speech-reentry.patch   # apply
```
If the dry run reports `FAILED`, apply nothing and use option C.

**Option C: the edit script.** It finds each place by its exact text and changes nothing unless all 6 are found. Edits that are already in the file are skipped:
```bash
python3 /tmp/byova_ces/tools/apply_continued_speech_fix.py $GW/src/core/wxcc_gateway_server.py
```
It prints `applied 6 edits`, `already applied: nothing changed`, or which text it could not find.

**4. Check, then restart the gateway the way you normally do:**
```bash
python3 -m py_compile $GW/src/core/wxcc_gateway_server.py && echo "syntax OK"
grep -c "byova_ces fix" $GW/src/core/wxcc_gateway_server.py      # 5
```

## Check after test calls

**Test 1: continued speech.** Call the CES agent, cough or say "uh" **during** the greeting, then give your answer after the greeting. CES should answer within a few seconds.

```bash
grep -E "Continued caller speech|gecx_caller_speech_start|gecx_recognition_received|gecx_pre_input_output_suppressed|Timed out after" $GW/logs/gateway.log | tail -8
```

| You see | Meaning |
|---|---|
| `Continued caller speech…` followed by `gecx_caller_speech_start … input_turn=2`, then `gecx_recognition_received … input_turn=2` | Fixed: the new turn opened and CES heard the caller |
| `gecx_pre_input_output_suppressed` followed by `Timed out after 30.0s` | The fix is not active. Check step 4 and that the gateway was restarted |

**Test 2: re-entry.** After a call where the session ends and CVP reopens the virtual agent:

```bash
grep -E "Starting a fresh session|session already started|re-entry replaced" $GW/logs/gateway.log | tail -5
```

| You see | Meaning |
|---|---|
| `Starting a fresh session for <call>: SESSION_START arrived after the previous session ended (CVP re-entry)` | Fixed: the re-entry got a new session |
| `Stream for <call> ended after a re-entry replaced its session; keeping the new session` | Normal: the old stream finished and left the new session alone |
| `SESSION_START event received but session already started` | The fix is not active, or CVP sent a second `SESSION_START` while the session was still running (that case is still ignored, on purpose) |

**Test 3: hang-up.** Run this before and after a few test calls where you hang up during a CES prompt. The number should not go up:

```bash
grep -c "KeyError" $GW/logs/gateway.log
```

## Undo

```bash
cp -p $B/wxcc_gateway_server.py $GW/src/core/      # $B = the backup folder printed in step 2
```
Then restart the gateway.

## How it was tested

- **6 new tests** in `verification/tests/test_byova_continued_speech_reentry.py`. They reproduce your calls: a noise turn, then the real answer, using Cisco's real `GECXConnector`; a re-entry 0.9 s after the end; the old stream finishing after the new session started; two clean-ups of the same call (the same `KeyError`, at the same line as in your log); and a slow clean-up while a new session starts. **All 6 fail without the update and pass with it.**
- **Cisco's own tests** for the gateway server and the CES connector: 161 pass before and after. The same 2 fail before and after: a Windows-only file permission test, and a test that expects barge-in off, which your gateway forces on for CVP.
- **The rest of Cisco's test suite:** identical results before and after the update.
- **Your own gateway changes:** `verification/verify_preserved.py` still reports `all customer changes are present`.
- **Install options:** the patch (option B) and the script (option C) both produce exactly the same file as option A.

To run the new tests on a **copy** of your gateway folder (needs `pytest`; run from the folder root so `src` is found):
```bash
cp -a $GW /tmp/gw-test && cd /tmp/gw-test && mkdir -p tests \
  && cp /tmp/byova_ces/verification/tests/test_byova_continued_speech_reentry.py tests/ \
  && python3 -m pytest -q tests/test_byova_continued_speech_reentry.py      # 6 passed
```
