"""byova_ces fixes: continued caller speech and CVP re-entry.

1. Continued speech: when the caller speaks again while a CES reply is pending,
   the gateway must really open a new CES input turn. Before the fix the
   connector's generator was created but never run, so CES never heard the
   caller and every reply was suppressed until the 30 s turn timeout.
2. Re-entry: a SESSION_START that arrives right after a session ended (CVP
   re-entering the virtual agent with the same conversation ID) must start a
   fresh session instead of being ignored, and the old stream must not clean up
   the new session when it finishes.
"""
import threading
import time
from unittest.mock import MagicMock, patch

from src.connectors.gecx_connector import GECXConnector
from src.core.virtual_agent_router import VirtualAgentRouter
from src.core.wxcc_gateway_server import ConversationProcessor, WxCCGatewayServer
from src.generated.byova_common_pb2 import EventInput
from src.generated.voicevirtualagent_pb2 import VoiceVARequest
from src.utils.silero_speech_boundary import SpeechBoundarySignal


class _FakeTimer:
    instances = []

    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self.daemon = False
        self.__class__.instances.append(self)

    def start(self):
        return None

    def cancel(self):
        return None


def _audio_input():
    audio_input = MagicMock()
    audio_input.caller_audio = b"caller-audio"
    audio_input.encoding = 2
    audio_input.sample_rate_hertz = 8000
    audio_input.language_code = "en-US"
    audio_input.is_single_utterance = False
    return audio_input


def test_continued_speech_runs_connector_speech_started_handler():
    """The sequence from the customer log: noise turn committed, then real speech."""
    router = MagicMock(spec=VirtualAgentRouter)
    processor = ConversationProcessor("cont-conv", "GECX Agent", router)
    _FakeTimer.instances = []
    signals = iter(
        [
            [SpeechBoundarySignal("speech_started", "cont-conv", 8000)],  # noise
            [SpeechBoundarySignal("speech_ended", "cont-conv", 8000)],
            [SpeechBoundarySignal("speech_started", "cont-conv", 8000)],  # real answer
            [SpeechBoundarySignal("speech_ended", "cont-conv", 8000)],
        ]
    )
    processor.speech_boundary_observer = MagicMock(end_silence_ms=1000)
    processor.speech_boundary_observer.observe.side_effect = lambda _f: next(signals)
    router.should_observe_speech_boundaries.return_value = True
    router.should_merge_speech_pauses.return_value = True
    router.should_coalesce_speech_end_with_response.return_value = True

    started_turns = []
    response_waiting = threading.Event()
    release_response = threading.Event()

    def speech_started_handler():
        # Like GECXConnector.handle_speech_boundary: a generator whose body
        # opens the CES input turn. It only runs when iterated.
        started_turns.append("begin_input_turn")
        return
        yield  # pragma: no cover

    def delayed_reply():
        response_waiting.set()
        assert release_response.wait(1.0)
        yield {
            "message_type": "audio",
            "text": "Thanks, I have that.",
            "audio_content": b"RIFFaudio",
            "output_events": [],
        }

    def route_request(_agent_id, operation, _conversation_id, *args):
        if operation in {
            "send_message",
            "pause_speech_turn",
            "resume_speech_turn",
            "commit_speech_turn",
        }:
            return None
        if operation == "handle_speech_boundary":
            kind = args[0]["speech_boundary"]["kind"]
            return speech_started_handler() if kind == "speech_started" else delayed_reply()
        raise AssertionError(f"unexpected operation: {operation}")

    router.route_request.side_effect = route_request
    async_responses = []
    processor.set_async_response_sink(lambda r: not async_responses.append(r))

    with patch("src.core.wxcc_gateway_server.threading.Timer", _FakeTimer):
        list(processor._process_audio_input(_audio_input()))  # noise starts
        list(processor._process_audio_input(_audio_input()))  # noise ends (held)
        waiter = threading.Thread(target=_FakeTimer.instances[0].callback)
        waiter.start()  # noise turn committed, CES reply pending
        assert response_waiting.wait(1.0)
        resumed = list(processor._process_audio_input(_audio_input()))  # real answer
        list(processor._process_audio_input(_audio_input()))
        _FakeTimer.instances[1].callback()
        release_response.set()
        waiter.join(timeout=1.0)

    assert resumed == []  # still no duplicate START_OF_INPUT to WxCC/CVP
    # Once for the first speech start, once for the continued speech.
    # Before the fix the second one was never run.
    assert started_turns == ["begin_input_turn", "begin_input_turn"]
    assert async_responses[-1].prompts[0].text == "Thanks, I have that."


def test_continued_speech_opens_a_new_turn_in_the_real_gecx_connector():
    """Use Cisco's real GECXConnector.handle_speech_boundary."""
    calls = []

    class FakeStreamSession:
        is_terminal = False

        def begin_input_turn(self, **kwargs):
            calls.append(kwargs)
            return True

        def drain_responses(self):
            return iter(())

    connector = GECXConnector.__new__(GECXConnector)
    connector.sessions_lock = threading.Lock()
    connector.streaming_sessions = {"real-conv": FakeStreamSession()}
    connector.logger = MagicMock()

    router = MagicMock(spec=VirtualAgentRouter)
    router.route_request.side_effect = (
        lambda _agent, operation, conversation_id, *args: getattr(connector, operation)(
            conversation_id, *args
        )
    )
    processor = ConversationProcessor("real-conv", "GECX Agent", router)
    processor._speech_response_pending = True

    assert processor._continue_pending_speech_turn() is True
    assert calls == [{"expect_recognition": True}]


def _session_start(conversation_id):
    return VoiceVARequest(
        conversation_id=conversation_id,
        virtual_agent_id="GECX Agent",
        event_input=EventInput(
            event_type=EventInput.EventType.SESSION_START, name="call_start"
        ),
    )


def test_reentry_after_session_end_starts_fresh_session():
    """CVP re-enters 0.9 s after SESSION_END: it must get a greeting, not silence."""
    router = MagicMock(spec=VirtualAgentRouter)
    started = []

    def route_request(agent_id, operation, conversation_id, message_data):
        if operation == "start_conversation":
            started.append(conversation_id)
            return {
                "message_type": "session_start",
                "text": "Welcome back",
                "audio_content": b"",
                "barge_in_enabled": False,
                "response_type": "final",
            }
        if operation == "end_conversation":
            return None
        raise AssertionError(f"unexpected operation: {operation}")

    router.route_request.side_effect = route_request
    router.should_cleanup_on_client_stream_end.return_value = True
    server = WxCCGatewayServer(router)
    old = ConversationProcessor("reentry-conv", "GECX Agent", router)
    old.session_started = True
    old.can_be_deleted = True  # the previous session already ended
    server.conversations["reentry-conv"] = old
    context = MagicMock()
    context.is_active.return_value = True

    responses = list(
        server.ProcessCallerInput(iter([_session_start("reentry-conv")]), context)
    )

    assert started == ["reentry-conv"]
    assert len(responses) == 1
    assert responses[0].prompts[0].text == "Welcome back"
    new = server.conversations["reentry-conv"]
    assert new is not old and new.session_started and not new.can_be_deleted
    operations = [call.args[1] for call in router.route_request.call_args_list]
    assert operations == ["end_conversation", "start_conversation"]


def test_old_stream_does_not_clean_up_the_session_that_replaced_it():
    router = MagicMock(spec=VirtualAgentRouter)
    start_count = []

    def route_request(agent_id, operation, conversation_id, message_data):
        if operation == "start_conversation":
            start_count.append(1)
            if len(start_count) == 1:
                return {  # first session ends at once (like the 30 s timeout)
                    "message_type": "session_end",
                    "text": "",
                    "audio_content": b"",
                    "response_type": "final",
                }
            return {
                "message_type": "session_start",
                "text": "Welcome back",
                "audio_content": b"",
                "barge_in_enabled": False,
                "response_type": "final",
            }
        if operation == "end_conversation":
            return None
        raise AssertionError(f"unexpected operation: {operation}")

    router.route_request.side_effect = route_request
    router.should_cleanup_on_client_stream_end.return_value = True
    server = WxCCGatewayServer(router)
    context = MagicMock()
    context.is_active.return_value = True
    release_old_reader = threading.Event()

    def old_requests():
        yield _session_start("guard-conv")
        release_old_reader.wait(5.0)  # VVB has not closed its side yet

    old_stream = threading.Thread(
        target=lambda: list(server.ProcessCallerInput(old_requests(), context))
    )
    old_stream.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        processor = server.conversations.get("guard-conv")
        if processor is not None and processor.can_be_deleted:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("first session never ended")

    responses = list(
        server.ProcessCallerInput(iter([_session_start("guard-conv")]), context)
    )
    new = server.conversations["guard-conv"]
    old_stream.join(timeout=6.0)  # old stream finishes after its 2 s join timeout
    release_old_reader.set()

    assert not old_stream.is_alive()
    assert responses[0].prompts[0].text == "Welcome back"
    assert server.conversations.get("guard-conv") is new
    assert new.session_started and not new.can_be_deleted
