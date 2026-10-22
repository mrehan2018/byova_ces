"""Simulate a CVP/VVB call against the BYOVA gateway (no phone call needed).

Run on the gateway host with the gateway's Python, while the gateway is running:
    python tools/cvp_sim.py --gateway-dir /opt/byova-gateway localhost:50051 ces 8

Stream 1: SESSION_START (expect the greeting: one FINAL with RIFF audio and barge=True)
Stream 2: <seconds> of 8 kHz mu-law line noise, as VVB sends while it listens
Stream 3: SESSION_END
Use the port from config.yaml gateway.port and an agent name from your config
(e.g. ces, or your Dialogflow CX agent name for a regression check).
"""
import argparse
import os
import random
import struct
import sys
import time

import audioop  # Python 3.13+: provided by the audioop-lts package
import grpc

ap = argparse.ArgumentParser()
ap.add_argument("--gateway-dir", default=os.getcwd(), help="folder containing src/generated")
ap.add_argument("target", help="host:port of the gateway gRPC listener")
ap.add_argument("agent", help="virtual agent name, e.g. ces")
ap.add_argument("seconds", nargs="?", type=float, default=8.0)
ap.add_argument("--param", action="append", default=[], metavar="NAME=VALUE",
                help="CVP session parameter sent with SESSION_START, e.g. --param Name=John")
args = ap.parse_args()
start_params = dict(p.split("=", 1) for p in args.param if "=" in p)
sys.path.insert(0, os.path.abspath(args.gateway_dir))
from src.generated import byova_common_pb2 as common  # noqa: E402
from src.generated import voicevirtualagent_pb2 as vva  # noqa: E402
from src.generated import voicevirtualagent_pb2_grpc as vva_grpc  # noqa: E402

cid = "SIMCVP%d" % int(time.time())
stub = vva_grpc.VoiceVirtualAgentStub(grpc.insecure_channel(args.target))
t0 = time.time()


def show(stream, r):
    prompts = [("text=%r" % p.text[:60]) + (" audio=%d hdr=%r barge=%s" % (len(p.audio_content), p.audio_content[:4], p.is_barge_in_enabled) if p.audio_content else "") for p in r.prompts]
    events = ["%s:%s" % (common.OutputEvent.EventType.Name(e.event_type), e.name) for e in r.output_events]
    print("  %5.1fs [%s] %-7s prompts=%s events=%s" % (time.time() - t0, stream, vva.VoiceVAResponse.ResponseType.Name(r.response_type), prompts, events), flush=True)


def base():
    return dict(conversation_id=cid, customer_org_id="sim-org", virtual_agent_id=args.agent)


def start_stream():
    event = common.EventInput(event_type=common.EventInput.EventType.SESSION_START, name="session_start")
    if start_params:
        event.parameters.update(start_params)
    yield vva.VoiceVARequest(event_input=event, **base())


def audio_stream():
    end = time.time() + args.seconds
    while time.time() < end:
        pcm = struct.pack("<320h", *[random.randint(-60, 60) for _ in range(320)])
        yield vva.VoiceVARequest(audio_input=vva.VoiceInput(caller_audio=audioop.lin2ulaw(pcm, 2), encoding=vva.VoiceInput.VoiceEncoding.MULAW_FORMAT, sample_rate_hertz=8000, language_code="en-US"), **base())
        time.sleep(0.08)


def end_stream():
    yield vva.VoiceVARequest(event_input=common.EventInput(event_type=common.EventInput.EventType.SESSION_END, name="session_end"), **base())


print("== stream 1: SESSION_START (%s, agent=%s)" % (cid, args.agent), flush=True)
for r in stub.ProcessCallerInput(start_stream(), timeout=30):
    show("start", r)
print("== stream 2: %ss of caller line noise" % args.seconds, flush=True)
try:
    for r in stub.ProcessCallerInput(audio_stream(), timeout=args.seconds + 30):
        show("audio", r)
except grpc.RpcError as e:
    print("  stream 2 ended:", e.code(), flush=True)
print("== stream 3: SESSION_END", flush=True)
for r in stub.ProcessCallerInput(end_stream(), timeout=15):
    show("end", r)
print("done %.1fs" % (time.time() - t0))
