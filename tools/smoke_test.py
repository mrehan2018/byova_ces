"""Offline smoke test for the BYOVA Google CES (GECX) adapter.

Run it with the same Python interpreter the gateway uses, from the gateway directory:
    python /path/to/ces-adapter-package/tools/smoke_test.py --gateway-dir /opt/byova-gateway
Add --check-credentials to also obtain a Google access token with the CES service-account key.

It checks the packages, imports the new and the existing connectors, and validates the
gecx_connector section of config/config.yaml. It doesn't touch the running gateway.
"""
import argparse
import importlib
import inspect
import json
import os
import sys

results = {"PASS": 0, "WARN": 0, "FAIL": 0}


def report(level, msg):
    results[level] += 1
    print(f"  [{level}] {msg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway-dir", default=os.getcwd())
    ap.add_argument("--config", default=None, help="default: <gateway-dir>/config/config.yaml")
    ap.add_argument("--check-credentials", action="store_true")
    args = ap.parse_args()
    gw = os.path.abspath(args.gateway_dir)
    os.chdir(gw)
    sys.path[:0] = [gw, os.path.join(gw, "src")]   # main.py imports both "src.x" and "core.x"

    print(f"== 1. Python {sys.version.split()[0]} ({sys.executable})")
    if sys.version_info < (3, 9):
        report("FAIL", "Python 3.9 or newer is required")
    elif sys.version_info >= (3, 13):
        report("WARN", "Python 3.13+: make sure audioop-lts is installed (requirements-ces.txt does this)")
    else:
        report("PASS", "Python version supported")

    print("== 2. Python packages")
    for mod, hint in [("torch", "CPU torch: see requirements-ces.txt step 1"),
                      ("torchaudio", "CPU torchaudio: see requirements-ces.txt step 1"),
                      ("silero_vad", "pip install silero-vad==6.2.1"),
                      ("google.cloud.ces_v1", "pip install google-cloud-ces"),
                      ("google_auth_oauthlib", "pip install google-auth-oauthlib"),
                      ("grpc_health.v1.health_pb2", "pip install grpcio-health-checking"),
                      ("numpy", "pip install numpy"),
                      ("audioop", "Python 3.13+: pip install audioop-lts")]:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            report("PASS", f"{mod} {ver}".strip())
        except Exception as e:  # noqa: BLE001
            report("FAIL", f"{mod} not importable ({e.__class__.__name__}: {e}) -> {hint}")
    try:
        import torch
        if getattr(torch.version, "cuda", None):
            report("WARN", f"torch is a CUDA build ({torch.__version__}); CPU build is smaller and sufficient")
        from silero_vad import load_silero_vad
        load_silero_vad()
        report("PASS", "Silero VAD model loads (bundled, no download needed)")
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"Silero VAD model failed to load: {e}")

    print("== 3. Gateway code")
    try:
        gws = importlib.import_module("src.core.wxcc_gateway_server")
        sig = inspect.signature(gws.WxCCGatewayServer.__init__)
        if "cvp_compat_audio" in sig.parameters and hasattr(gws.ConversationProcessor, "_cvp_coalesce"):
            report("PASS", "wxcc_gateway_server.py is the CES adapter version (CVP compatibility present)")
        else:
            report("FAIL", "wxcc_gateway_server.py is NOT the CES adapter version - copy src/core/wxcc_gateway_server.py")
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"src.core.wxcc_gateway_server failed to import: {e.__class__.__name__}: {e}")
    try:
        ivc = importlib.import_module("src.connectors.i_vendor_connector")
        base = ivc.IVendorConnector
        if not hasattr(base, "get_audio_delivery_mode"):
            report("FAIL", "i_vendor_connector.py lacks the streaming hooks - copy src/connectors/i_vendor_connector.py")
        else:
            report("PASS", "i_vendor_connector.py has the streaming hooks")
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"src.connectors.i_vendor_connector failed to import: {e}")
    try:
        gecx = importlib.import_module("src.connectors.gecx_connector")
        if getattr(gecx, "ces_v1", None) is None:
            report("FAIL", "gecx_connector imported but the Google CES client did not (check section 2)")
        else:
            report("PASS", "gecx_connector imports with the Google CES client")
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"src.connectors.gecx_connector failed to import: {e.__class__.__name__}: {e}")
    try:
        importlib.import_module("src.core.virtual_agent_router")
        importlib.import_module("src.core.health_service")
        report("PASS", "virtual_agent_router / health_service import")
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"router/health service failed to import: {e}")

    print("== 4. config/config.yaml")
    cfg_path = args.config or os.path.join(gw, "config", "config.yaml")
    try:
        import yaml
        cfg = yaml.safe_load(open(cfg_path, encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"cannot read {cfg_path}: {e}")
        return finish()
    connectors = cfg.get("connectors") or {}
    for name, c in connectors.items():
        c = c or {}
        module, cls_name = c.get("module"), c.get("class")
        if not module or not cls_name:
            continue
        try:
            cls = getattr(importlib.import_module(f"src.{module}"), cls_name)
            missing = sorted(getattr(cls, "__abstractmethods__", set()))
            if missing:
                report("FAIL", f"connector {name}: {cls_name} is missing methods {missing}")
            else:
                report("PASS", f"connector {name}: {cls_name} imports with the new base class")
        except Exception as e:  # noqa: BLE001
            report("FAIL", f"connector {name}: cannot import src.{module}.{cls_name} ({e.__class__.__name__}: {e})")

    g = connectors.get("gecx_connector")
    if not g:
        report("WARN", "no gecx_connector section yet - add config/gecx_connector.snippet.yaml (guide step 6)")
        return finish()
    gc = g.get("config") or {}
    for key in ("project_id", "location", "application_id"):
        val = str(gc.get(key, ""))
        if not val or val.startswith("YOUR_"):
            report("FAIL", f"gecx_connector.config.{key} is not set")
        else:
            report("PASS", f"gecx_connector.config.{key} = {val}")
    agents = gc.get("agents") or []
    report("PASS" if agents else "FAIL", f"gecx agents offered to CVP: {agents}")
    all_agents = [a for c in connectors.values() for a in ((c or {}).get("config") or {}).get("agents") or []]
    dupes = sorted({a for a in all_agents if all_agents.count(a) > 1})
    if dupes:
        report("FAIL", f"agent names used by more than one connector: {dupes}")
    for key, want in (("output_sample_rate_hertz", 8000), ("output_audio_encoding", "MULAW")):
        if gc.get(key) != want:
            report("WARN", f"gecx_connector.config.{key} = {gc.get(key)!r}; tested CVP value is {want!r}")
    if (cfg.get("gateway") or {}).get("cvp_compat_audio") is False:
        report("WARN", "gateway.cvp_compat_audio is false - CVP/VVB callers will hear only the first prompt")
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    key_path = gc.get("service_account_key")
    try:
        import google.auth
        from google.auth.transport.requests import Request
        if key_path:
            if not os.path.isfile(key_path):
                report("FAIL", f"service_account_key not found: {key_path} (relative paths are from {gw})")
                return finish()
            info = json.load(open(key_path, encoding="utf-8"))
            if info.get("type") == "service_account":
                report("PASS", f"service account key: {info.get('client_email')} (project {info.get('project_id')})")
            else:
                report("PASS", f"credential file type '{info.get('type')}' (Workload Identity Federation): {key_path}")
            creds, _ = google.auth.load_credentials_from_file(key_path, scopes=scopes)
        else:
            adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if adc:
                kind = json.load(open(adc, encoding="utf-8")).get("type") if os.path.isfile(adc) else "missing file"
                report("PASS" if os.path.isfile(adc) else "FAIL",
                       f"Application Default Credentials: GOOGLE_APPLICATION_CREDENTIALS={adc} (type {kind})")
            else:
                report("WARN", "no service_account_key and GOOGLE_APPLICATION_CREDENTIALS is not set in THIS shell; "
                               "make sure the gateway service has it (Workload Identity Federation)")
            creds, _ = google.auth.default(scopes=scopes)
        if args.check_credentials:
            creds.refresh(Request())
            who = getattr(creds, "service_account_email", None) or getattr(creds, "_service_account_impersonation_url", "") or ""
            report("PASS", f"Google access token obtained {('(' + who + ')') if who else ''}".strip())
    except Exception as e:  # noqa: BLE001
        report("FAIL", f"Google credentials problem: {e.__class__.__name__}: {e}")
    return finish()


def finish():
    print(f"\nRESULT: {results['PASS']} passed, {results['WARN']} warnings, {results['FAIL']} failed")
    sys.exit(1 if results["FAIL"] else 0)


if __name__ == "__main__":
    main()
