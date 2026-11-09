"""Apply the continued-speech + CVP re-entry fixes to wxcc_gateway_server.py.

Usage: python apply_continued_speech_fix.py <path to wxcc_gateway_server.py>
Every edit is anchored on text that must occur exactly once; nothing else changes.
"""
import io
import sys

path = sys.argv[1]
s = io.open(path, encoding="utf-8").read()

EDITS = [
    # A. per-call holder for responses returned by the continued-turn call
    (
        "        self._speech_response_pending = False\n"
        "        self._async_task_count = 0\n",
        "        self._speech_response_pending = False\n"
        "        self._async_task_count = 0\n"
        "        # byova_ces fix: responses returned when continued caller speech\n"
        "        # opens a new CES input turn (see _continue_pending_speech_turn).\n"
        "        self._continued_turn_responses: List[Dict[str, Any]] = []\n",
    ),
    # B. actually run the connector's speech_started handler
    (
        "            self._caller_input_acknowledged = False\n"
        "        self.router.route_request(\n"
        "            self.virtual_agent_id,\n"
        "            \"handle_speech_boundary\",\n"
        "            self.conversation_id,\n"
        "            {\n"
        "                \"conversation_id\": self.conversation_id,\n"
        "                \"virtual_agent_id\": self.virtual_agent_id,\n"
        "                \"input_type\": \"speech_boundary\",\n"
        "                \"speech_boundary\": {\"kind\": \"speech_started\"},\n"
        "            },\n"
        "        )\n",
        "            self._caller_input_acknowledged = False\n"
        "        boundary_response = self.router.route_request(\n"
        "            self.virtual_agent_id,\n"
        "            \"handle_speech_boundary\",\n"
        "            self.conversation_id,\n"
        "            {\n"
        "                \"conversation_id\": self.conversation_id,\n"
        "                \"virtual_agent_id\": self.virtual_agent_id,\n"
        "                \"input_type\": \"speech_boundary\",\n"
        "                \"speech_boundary\": {\"kind\": \"speech_started\"},\n"
        "            },\n"
        "        )\n"
        "        # byova_ces fix: handle_speech_boundary is a generator, so its code runs\n"
        "        # only when the result is iterated. Without this loop the connector never\n"
        "        # opened the new input turn: the caller's speech was not sent to CES and\n"
        "        # every CES reply was suppressed until the 30 s turn timeout.\n"
        "        if (\n"
        "            boundary_response is not None\n"
        "            and hasattr(boundary_response, \"__iter__\")\n"
        "            and not isinstance(boundary_response, (dict, str, bytes))\n"
        "        ):\n"
        "            self._continued_turn_responses = [\n"
        "                response for response in boundary_response if response is not None\n"
        "            ]\n",
    ),
    # C. forward anything the connector returned (only on a failed/terminal turn)
    (
        "                    and self._continue_pending_speech_turn()\n"
        "                ):\n"
        "                    continue\n",
        "                    and self._continue_pending_speech_turn()\n"
        "                ):\n"
        "                    responses = self._continued_turn_responses\n"
        "                    self._continued_turn_responses = []\n"
        "                    yield from self._iter_grpc_connector_responses(\n"
        "                        responses, include_single_response=False\n"
        "                    )\n"
        "                    continue\n",
    ),
    # D. CVP re-entry: SESSION_START after the session ended -> fresh session
    (
        "                            return\n"
        "\n"
        "                        if conversation_id not in self.conversations:\n",
        "                            return\n"
        "\n"
        "                        # byova_ces fix: CVP re-enters the virtual agent with the\n"
        "                        # same conversation ID right after a session ended. The old\n"
        "                        # session used to answer \"session already started\" with\n"
        "                        # nothing, and VVB waited 15 s (error.noresource). Close the\n"
        "                        # ended session and start a fresh one instead.\n"
        "                        if (\n"
        "                            conversation_id in self.conversations\n"
        "                            and self.conversations[conversation_id].can_be_deleted\n"
        "                            and request.HasField(\"event_input\")\n"
        "                            and request.event_input.event_type\n"
        "                            == EventInput.EventType.SESSION_START\n"
        "                        ):\n"
        "                            self.logger.info(\n"
        "                                \"Starting a fresh session for %s: SESSION_START \"\n"
        "                                \"arrived after the previous session ended (CVP re-entry)\",\n"
        "                                conversation_id,\n"
        "                            )\n"
        "                            self._cleanup_conversation(\n"
        "                                conversation_id, termination_reason=\"completed\"\n"
        "                            )\n"
        "\n"
        "                        if conversation_id not in self.conversations:\n",
    ),
    # E. the old stream must not clean up the session that replaced it
    (
        "            if conversation_id and conversation_id in self.conversations:\n"
        "                processor = self.conversations[conversation_id]\n"
        "                agent_id = processor.virtual_agent_id\n",
        "            current_processor = (\n"
        "                self.conversations.get(conversation_id) if conversation_id else None\n"
        "            )\n"
        "            if (\n"
        "                processor is not None\n"
        "                and current_processor is not None\n"
        "                and current_processor is not processor\n"
        "            ):\n"
        "                # byova_ces fix: a CVP re-entry already replaced this stream's\n"
        "                # session. Leave the new session alone.\n"
        "                self.logger.info(\n"
        "                    \"Stream for %s ended after a re-entry replaced its session; \"\n"
        "                    \"keeping the new session\",\n"
        "                    conversation_id,\n"
        "                )\n"
        "            elif conversation_id and conversation_id in self.conversations:\n"
        "                processor = self.conversations[conversation_id]\n"
        "                agent_id = processor.virtual_agent_id\n",
    ),
]

if "byova_ces fix: handle_speech_boundary is a generator" in s:
    sys.exit("already applied: nothing changed")
for old, new in EDITS:
    n = s.count(old)
    if n != 1:
        sys.exit(f"anchor found {n} times (expected 1), nothing changed:\n{old[:120]}")
for old, new in EDITS:
    s = s.replace(old, new)
io.open(path, "w", encoding="utf-8", newline="\n").write(s)
print("applied 5 edits to", path)
