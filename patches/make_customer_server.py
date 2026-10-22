"""Customer gateway server = CES package server (Cisco HEAD + CVP compat + params)
plus the customer's own customizations from wxsd-sales/byova-dialogflow-agent:
session transcript, barge-in forced on every prompt, gRPC activity tracking for their
dashboard, ListVirtualAgents/ProcessCallerInput logging and numeric agent IDs.

The added code is copied from the customer's wxcc_gateway_server.py (server.diff).
Usage: python make_customer_server.py <package server.py> <output.py>
"""
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def sub(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        sys.exit(f"ANCHOR FAILED ({n} matches): {label}")
    s = s.replace(old, new)
    print("ok  ", label)


sub("from typing import Any, Callable, Dict, Iterator, Optional",
    "from typing import Any, Callable, Dict, Iterator, List, Optional", "typing List")

# --- session transcript --------------------------------------------------------------
sub("""        self.start_time = time.time()
        self.session_started = False
        self.can_be_deleted = False
""", """        self.start_time = time.time()
        self.session_started = False
        self.can_be_deleted = False
        # Cumulative session transcript (User:/Agent: lines) for session_transcript field
        self._session_transcript_lines: List[str] = []
        self._session_transcript_language: str = "en-US"
""", "transcript state")

TRANSCRIPT_METHODS = '''    def _update_session_transcript_from_connector(
        self, connector_response: Dict[str, Any]
    ) -> None:
        """Append User:/Agent: lines from connector dict (Dialogflow STT + agent text)."""
        ut = connector_response.get("user_transcript")
        if ut is not None and str(ut).strip():
            self._session_transcript_lines.append(f"User: {str(ut).strip()}")
        lang = connector_response.get("language_code")
        if lang:
            self._session_transcript_language = str(lang)

        text = (connector_response.get("text") or "").strip()
        if not text:
            return
        mt = connector_response.get("message_type", "")
        if mt == "silence":
            return
        # Skip audio-only chunks with no spoken text (second yield from Dialogflow)
        if mt == "audio":
            return
        self._session_transcript_lines.append(f"Agent: {text}")

    def _apply_session_transcript_to_response(
        self,
        va_response: VoiceVAResponse,
        connector_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set VoiceVAResponse.session_transcript from accumulated lines."""
        if not self._session_transcript_lines:
            return
        full = "\\n".join(self._session_transcript_lines)
        va_response.session_transcript.text = full
        lang = "en-US"
        if connector_response and connector_response.get("language_code"):
            lang = str(connector_response["language_code"])
        else:
            lang = self._session_transcript_language
        va_response.session_transcript.language_code = lang

'''
sub("""    def _convert_connector_response_to_grpc(
        self,""", TRANSCRIPT_METHODS + """    def _convert_connector_response_to_grpc(
        self,""", "transcript methods")
sub("""            va_response = VoiceVAResponse()

            # Handle empty or silence responses""", """            if isinstance(connector_response, dict):
                self._update_session_transcript_from_connector(connector_response)

            va_response = VoiceVAResponse()

            # Handle empty or silence responses""", "transcript update hook")
sub("""                            self.logger.debug(
                                f"Added {event_type} event to silence response"
                            )

                return va_response""", """                            self.logger.debug(
                                f"Added {event_type} event to silence response"
                            )

                self._apply_session_transcript_to_response(
                    va_response, connector_response if isinstance(connector_response, dict) else None
                )
                return va_response""", "transcript on silence responses")
sub("""            self.logger.debug(
                f"Final gRPC response created with {len(va_response.prompts)} prompts"
            )
            return va_response""", """            self._apply_session_transcript_to_response(va_response, connector_response)

            self.logger.debug(
                f"Final gRPC response created with {len(va_response.prompts)} prompts"
            )
            return va_response""", "transcript on prompt responses")

# --- barge-in forced on every prompt (customer behaviour) ----------------------------
sub("""                barge_in_enabled=False,  # Enable barge-in for conversation start (until server bug is resolved)""",
    """                barge_in_enabled=True,  # Enable barge-in for conversation start (until server bug is resolved)""",
    "welcome barge-in")
sub("""                # Use specified barge-in setting, or fall back to connector response setting
                if barge_in_enabled is not None:
                    # Use the explicitly specified barge-in setting
                    final_barge_in_enabled = barge_in_enabled
                else:
                    # Use the barge-in setting from the connector response
                    final_barge_in_enabled = connector_response.get(
                        "barge_in_enabled", True
                    )
""", """                # Force barge-in to be enabled for every prompt, regardless of connector/config.
                final_barge_in_enabled = True
""", "audio prompt barge-in")
sub("""                    prompt.is_barge_in_enabled = connector_response.get(
                        "barge_in_enabled", False
                    )""", """                    prompt.is_barge_in_enabled = True""", "text prompt barge-in")
sub("""        prompt.text = f"I'm sorry, I encountered an error: {error_message}"
        prompt.is_barge_in_enabled = False
        va_response.prompts.append(prompt)
""", """        prompt.text = f"I'm sorry, I encountered an error: {error_message}"
        prompt.is_barge_in_enabled = True
        va_response.prompts.append(prompt)
        self._update_session_transcript_from_connector(
            {
                "text": prompt.text,
                "message_type": "error",
                "language_code": self._session_transcript_language,
            }
        )
        self._apply_session_transcript_to_response(
            va_response, {"language_code": self._session_transcript_language}
        )
""", "error prompt barge-in + transcript")

# --- gRPC activity for the customer's dashboard --------------------------------------
sub("""        self.health_service = HealthCheckService(self.router)

        self.logger.info("WxCCGatewayServer initialized")""",
    """        self.health_service = HealthCheckService(self.router)

        # gRPC activity (port 50051) - for logging and dashboard
        self._grpc_activity: List[Dict[str, Any]] = []
        self._grpc_activity_lock = threading.Lock()
        self._grpc_request_counts: Dict[str, int] = {
            "ListVirtualAgents": 0,
            "ProcessCallerInput": 0,
        }

        self.logger.info("WxCCGatewayServer initialized")""", "gRPC activity state")
sub("""    def get_active_conversations(self) -> Dict[str, Dict[str, Any]]:""", '''    def _record_grpc_activity(self, method: str, **kwargs: Any) -> None:
        """Record gRPC request for logging and dashboard (port 50051)."""
        with self._grpc_activity_lock:
            self._grpc_request_counts[method] = self._grpc_request_counts.get(
                method, 0
            ) + 1
            entry = {
                "ts": time.time(),
                "method": method,
                **kwargs,
            }
            self._grpc_activity.append(entry)
            if len(self._grpc_activity) > 50:
                self._grpc_activity.pop(0)

    def get_grpc_activity(self) -> Dict[str, Any]:
        """
        Get recent gRPC activity on port 50051 for monitoring/test page.

        Returns:
            Dict with recent (list of {ts, method, ...}), counts (method -> count)
        """
        with self._grpc_activity_lock:
            recent = list(self._grpc_activity)
            counts = dict(self._grpc_request_counts)
        return {"recent": recent, "counts": counts}

    def get_active_conversations(self) -> Dict[str, Dict[str, Any]]:''', "gRPC activity methods")
sub("""            self.logger.debug("ListVirtualAgents called")""", """            self._record_grpc_activity(
                "ListVirtualAgents",
                customer_org_id=getattr(request, "customer_org_id", "") or "",
            )
            self.logger.info(
                "[gRPC:50051] ListVirtualAgents received (customer_org_id=%s)",
                getattr(request, "customer_org_id", "") or "(none)",
            )""", "ListVirtualAgents received log")
sub("""            self.logger.debug(
                f"ListVirtualAgents: Returning {len(virtual_agents)} agents"
            )""", """            self.logger.info(
                "[gRPC:50051] ListVirtualAgents returning %d agents",
                len(virtual_agents),
            )""", "ListVirtualAgents returning log")

# --- ProcessCallerInput: activity, log, numeric agent index --------------------------
sub("""                    if conversation_id is None:
                        conversation_id = request.conversation_id
                        agent_id = request.virtual_agent_id

                        # Use default agent if none specified
                        if not agent_id:
                            available_agents = self.router.get_all_available_agents()
                            if available_agents:""",
    """                    if conversation_id is None:
                        conversation_id = request.conversation_id
                        agent_id = request.virtual_agent_id

                        self._record_grpc_activity(
                            "ProcessCallerInput",
                            conversation_id=conversation_id or "",
                            agent_id=agent_id or "",
                            customer_org_id=getattr(
                                request, "customer_org_id", ""
                            ) or "",
                        )
                        self.logger.info(
                            "[gRPC:50051] ProcessCallerInput stream started "
                            "(conversation_id=%s, agent_id=%s)",
                            conversation_id or "(none)",
                            agent_id or "(none)",
                        )

                        available_agents = self.router.get_all_available_agents()
                        # Webex may send a 1-based index (e.g. "1", "2") instead of full agent ID
                        if (
                            isinstance(agent_id, str)
                            and agent_id.strip().isdigit()
                            and available_agents
                        ):
                            idx = int(agent_id.strip()) - 1  # 1-based -> 0-based
                            if 0 <= idx < len(available_agents):
                                resolved = available_agents[idx]
                                self.logger.debug(
                                    "Resolved agent_id index %s to %s",
                                    agent_id,
                                    resolved,
                                )
                                agent_id = resolved

                        # Use default agent if none specified
                        if not agent_id:
                            if available_agents:""", "stream start log + numeric agent index")

open(out, "w", encoding="utf-8", newline="\n").write(s)
print("written", out, len(s.splitlines()), "lines")
