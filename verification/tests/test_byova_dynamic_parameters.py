"""byova_ces dynamic parameters.

  session_variables: "auto"        CVP -> CES without a list of names
  forward_end_session_fields: "*"  CES -> CVP without a list of names

Lists and mappings must keep working, and the default (nothing set) must stay off.
"""
import logging
from unittest.mock import patch

import pytest

from src.connectors.gecx_connector import GECXConnector, GECXStreamingSession


@pytest.fixture
def gecx_config():
    return {
        "project_id": "test-project",
        "location": "us",
        "application_id": "test-app",
        "deployment_id": "test-deployment",
        "agents": ["Test GECX Agent"],
        "input_sample_rate_hertz": 8000,
        "output_sample_rate_hertz": 8000,
        "input_audio_encoding": "MULAW",
        "output_audio_encoding": "MULAW",
        "initial_message": "Hello",
    }


class TestDynamicParameters:
    """session_variables: "auto" and forward_end_session_fields: "*"."""

    CVP_PARAMS = {
        "sipHeader.CALL_ANI": "5551230001",
        "sipHeader.CALL_DNIS": "8005550100",
        "sipHeader.Contact": "<sip:x@10.0.0.1>",
        "sipHeader.Cisco-Guid": "1-2-3-4",
        "Name": "Alex",
        "account_id": "A42",
        "queue name": "Billing",
        "empty_one": "",
    }

    def _connector(self, gecx_config, **extra):
        with patch("src.connectors.gecx_connector.ces_v1.SessionServiceClient"):
            return GECXConnector({**gecx_config, **extra})

    def _session(self, connector):
        return GECXStreamingSession(
            connector=connector,
            conversation_id="conv-1",
            session_path="projects/p/locations/us/apps/a/sessions/s1",
            deployment_path=connector.deployment_path,
        )

    def test_auto_sends_ani_dnis_and_cvp_parameters_only(self, gecx_config):
        connector = self._connector(gecx_config, session_variables="auto")
        variables = connector._session_variables_for(
            "conv-1", {"session_params": dict(self.CVP_PARAMS)}
        )
        assert variables == {
            "caller_ani": "5551230001",
            "caller_dnis": "8005550100",
            "Name": "Alex",
            "account_id": "A42",
        }

    def test_auto_logs_names_not_values(self, gecx_config, caplog):
        connector = self._connector(gecx_config, session_variables="AUTO")
        with caplog.at_level(logging.INFO):
            connector._session_variables_for(
                "conv-1", {"session_params": dict(self.CVP_PARAMS)}
            )
        text = caplog.text
        assert "caller_ani" in text and "queue name" in text
        for value in ("5551230001", "8005550100", "Alex", "A42", "Billing"):
            assert value not in text

    def test_auto_cvp_parameter_overrides_sip_default(self, gecx_config):
        connector = self._connector(gecx_config, session_variables="auto")
        variables = connector._session_variables_for(
            "conv-1",
            {"session_params": {"sipHeader.CALL_ANI": "111", "caller_ani": "222"}},
        )
        assert variables == {"caller_ani": "222"}

    def test_auto_without_parameters_sends_nothing(self, gecx_config):
        connector = self._connector(gecx_config, session_variables="auto")
        assert connector._session_variables_for("conv-1", {}) == {}

    def test_mapping_and_list_still_work(self, gecx_config):
        mapped = self._connector(
            gecx_config, session_variables={"Name": "customer_name"}
        )
        assert mapped._session_variables_for(
            "c", {"session_params": dict(self.CVP_PARAMS)}
        ) == {"customer_name": "Alex"}
        listed = self._connector(gecx_config, session_variables=["account_id"])
        assert listed._session_variables_for(
            "c", {"session_params": dict(self.CVP_PARAMS)}
        ) == {"account_id": "A42"}

    def test_default_sends_no_variables(self, gecx_config):
        connector = self._connector(gecx_config)
        assert not connector.session_variables_auto
        assert connector._session_variables_for(
            "c", {"session_params": dict(self.CVP_PARAMS)}
        ) == {}

    END_SESSION = {
        "reason": "success",
        "session_escalated": True,
        "summary": "short summary",
        "params": {"ticket_number": "T-1", "zipcode": 75001.0, "nested": {"a": 1}},
    }

    def test_wildcard_forwards_every_param_field(self, gecx_config):
        for setting in ("*", ["*"]):
            connector = self._connector(
                gecx_config, forward_end_session_fields=setting
            )
            forwarded = self._session(connector)._forwarded_end_session_fields(
                dict(self.END_SESSION)
            )
            assert forwarded == {
                "transfer_metadata": {"ticket_number": "T-1", "zipcode": "75001"}
            }

    def test_wildcard_with_no_params_forwards_nothing(self, gecx_config):
        connector = self._connector(gecx_config, forward_end_session_fields="*")
        session = self._session(connector)
        assert session._forwarded_end_session_fields({"reason": "success"}) == {}

    def test_allowlist_still_filters(self, gecx_config):
        connector = self._connector(
            gecx_config, forward_end_session_fields=["ticket_number"]
        )
        forwarded = self._session(connector)._forwarded_end_session_fields(
            dict(self.END_SESSION)
        )
        assert forwarded == {"transfer_metadata": {"ticket_number": "T-1"}}

    def test_default_forwards_nothing(self, gecx_config):
        connector = self._connector(gecx_config)
        session = self._session(connector)
        assert session._forwarded_end_session_fields(dict(self.END_SESSION)) == {}

    def test_auto_cleans_sip_uri_and_skips_structured_values(self, gecx_config):
        connector = self._connector(gecx_config, session_variables="auto")
        variables = connector._session_variables_for(
            "conv-1",
            {
                "session_params": {
                    "sipHeader.CALL_ANI": "sip:+15551230001@10.0.0.1:5060",
                    "sipHeader.CALL_DNIS": "<sip:8005550100@host;user=phone>",
                    "user": "VVB",
                    "userData": {"timezone": "X"},
                    "Name": "Alex",
                }
            },
        )
        assert variables == {
            "caller_ani": "+15551230001",
            "caller_dnis": "8005550100",
            "user": "VVB",
            "Name": "Alex",
        }

    def test_sip_user_part_leaves_plain_numbers_alone(self):
        assert GECXConnector._sip_user_part("55500277777777771001") == "55500277777777771001"
        assert GECXConnector._sip_user_part("tel:+15551230001") == "+15551230001"
