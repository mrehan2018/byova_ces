"""Add automatic parameter passing to gecx_connector.py.

  session_variables: "auto"        CVP -> CES, no list of names needed
  forward_end_session_fields: "*"  CES -> CVP, no list of names needed

Usage: python apply_dynamic_parameters.py <path to gecx_connector.py>
Every edit is anchored on text that must occur exactly once; nothing else changes.
Edits that are already in the file are skipped, so running it twice is safe.
Lists and mappings in config.yaml keep working exactly as before.
"""
import io
import sys

path = sys.argv[1]
s = io.open(path, encoding="utf-8").read()

EDITS = [
    # A. CES -> CVP: "*" forwards every field in the end_session params
    (
        "        fields = self._end_session_fields(metadata)\n"
        "        selected = {k: v for k, v in fields.items() if k in allowed}\n",
        "        if \"*\" in allowed:\n"
        "            # byova_ces dynamic parameters: \"*\" forwards every field the agent\n"
        "            # put in the end_session params, no list of names needed.\n"
        "            params = metadata.get(\"params\")\n"
        "            metadata = {\"params\": params if isinstance(params, Mapping) else {}}\n"
        "            allowed = list(self._end_session_fields(metadata))\n"
        "        fields = self._end_session_fields(metadata)\n"
        "        selected = {k: v for k, v in fields.items() if k in allowed}\n",
    ),
    # B. config: accept session_variables: "auto"
    (
        "        self.session_variables = config.get(\"session_variables\") or {}\n",
        "        self.session_variables = config.get(\"session_variables\") or {}\n"
        "        # byova_ces dynamic parameters: \"auto\" sends caller_ani/caller_dnis plus\n"
        "        # every non-SIP CVP parameter, no list of names needed.\n"
        "        self.session_variables_auto = (\n"
        "            isinstance(self.session_variables, str)\n"
        "            and self.session_variables.strip().lower() in (\"auto\", \"*\")\n"
        "        )\n"
        "        if isinstance(self.session_variables, str) and not self.session_variables_auto:\n"
        "            self.session_variables = [self.session_variables]\n",
    ),
    # C. config: accept forward_end_session_fields: "*" (a plain string)
    (
        "        self.forward_end_session_fields = [\n"
        "            str(name) for name in (config.get(\"forward_end_session_fields\") or [])\n"
        "        ]\n",
        "        # byova_ces dynamic parameters: \"*\" = every field in the end_session params.\n"
        "        _forward_fields = config.get(\"forward_end_session_fields\") or []\n"
        "        if isinstance(_forward_fields, str):\n"
        "            _forward_fields = [_forward_fields]\n"
        "        self.forward_end_session_fields = [str(name) for name in _forward_fields]\n",
    ),
    # D. CVP -> CES: use the automatic mapping when session_variables is "auto"
    (
        "        if not self.session_variables:\n"
        "            return {}\n"
        "        if isinstance(self.session_variables, Mapping):\n",
        "        if not self.session_variables:\n"
        "            return {}\n"
        "        if self.session_variables_auto:\n"
        "            return self._auto_session_variables(conversation_id, request_data)\n"
        "        if isinstance(self.session_variables, Mapping):\n",
    ),
    # E. the automatic mapping itself
    (
        "            f\" (not sent by CVP: {missing})\" if missing else \"\",\n"
        "        )\n"
        "        return variables\n",
        "            f\" (not sent by CVP: {missing})\" if missing else \"\",\n"
        "        )\n"
        "        return variables\n"
        "\n"
        "    # byova_ces dynamic parameters -- session_variables: \"auto\"\n"
        "    #   sipHeader.CALL_ANI / sipHeader.CALL_DNIS -> caller_ani / caller_dnis\n"
        "    #   every other non-SIP parameter set in the CVP element -> same name in CES\n"
        "    #   other sipHeader.* parameters are not sent\n"
        "    _AUTO_SIP_VARIABLES = {\n"
        "        \"sipHeader.CALL_ANI\": \"caller_ani\",\n"
        "        \"sipHeader.CALL_DNIS\": \"caller_dnis\",\n"
        "    }\n"
        "    _AUTO_VARIABLE_NAME = re.compile(r\"^[A-Za-z_][A-Za-z0-9_]*$\")\n"
        "\n"
        "    def _auto_session_variables(\n"
        "        self, conversation_id: str, request_data: Dict[str, Any]\n"
        "    ) -> Dict[str, Any]:\n"
        "        params = (request_data or {}).get(\"session_params\") or {}\n"
        "        variables: Dict[str, Any] = {}\n"
        "        skipped = []\n"
        "        for raw_name, value in params.items():\n"
        "            name = str(raw_name)\n"
        "            if value in (None, \"\"):\n"
        "                continue\n"
        "            if not isinstance(value, (str, int, float, bool)):\n"
        "                # structured values (e.g. CVP userData) are not usable as text\n"
        "                skipped.append(name)\n"
        "                continue\n"
        "            if name in self._AUTO_SIP_VARIABLES:\n"
        "                variables[self._AUTO_SIP_VARIABLES[name]] = self._sip_user_part(\n"
        "                    str(value)\n"
        "                )\n"
        "            elif name.startswith(\"sipHeader.\"):\n"
        "                continue\n"
        "            elif self._AUTO_VARIABLE_NAME.match(name):\n"
        "                variables[name] = str(value)\n"
        "            else:\n"
        "                skipped.append(name)\n"
        "        # a CVP parameter named caller_ani / caller_dnis wins over the SIP header\n"
        "        for ces_name in self._AUTO_SIP_VARIABLES.values():\n"
        "            if ces_name in params and params[ces_name] not in (None, \"\"):\n"
        "                variables[ces_name] = str(params[ces_name])\n"
        "        # names only, never values\n"
        "        self.logger.info(\n"
        "            \"[GECX] Session variables for %s (auto): %s%s\",\n"
        "            conversation_id,\n"
        "            sorted(variables),\n"
        "            f\" (skipped, name or value not usable: {sorted(skipped)})\"\n"
        "            if skipped\n"
        "            else \"\",\n"
        "        )\n"
        "        return variables\n"
        "\n"
        "    _SIP_URI = re.compile(r\"^\\s*<?\\s*(?:sips?|tel):([^@;>\\s]+)\", re.IGNORECASE)\n"
        "\n"
        "    @classmethod\n"
        "    def _sip_user_part(cls, value: str) -> str:\n"
        "        \"\"\"'sip:+15551230001@10.0.0.1:5060' -> '+15551230001'; plain values unchanged.\"\"\"\n"
        "        match = cls._SIP_URI.match(value)\n"
        "        return match.group(1) if match else value.strip()\n",
    ),
]

MARKERS = [
    "            allowed = list(self._end_session_fields(metadata))\n",
    "        self.session_variables_auto = (\n",
    "        _forward_fields = config.get(\"forward_end_session_fields\") or []\n",
    "            return self._auto_session_variables(conversation_id, request_data)\n",
    "    def _auto_session_variables(\n",
]

applied = skipped = 0
for label, (old, new), marker in zip("ABCDE", EDITS, MARKERS):
    if marker in s:
        print(f"edit {label}: already applied, skipped")
        skipped += 1
        continue
    count = s.count(old)
    if count != 1:
        sys.exit(
            f"edit {label}: anchor found {count} times (expected 1). "
            "Nothing was written. Send us this message."
        )
    s = s.replace(old, new)
    applied += 1
    print(f"edit {label}: applied")

if applied:
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
print(f"done: {applied} applied, {skipped} already there")
