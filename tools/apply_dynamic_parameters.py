"""Add automatic parameter passing to gecx_connector.py.

  session_variables: "auto"        CVP -> CES, no list of names needed
  forward_end_session_fields: "*"  CES -> CVP, no list of names needed

Usage: python apply_dynamic_parameters.py <path to gecx_connector.py>
Every edit is anchored on text that must occur exactly once; nothing else changes.
Edits that are already in the file are skipped, so running it twice is safe.
Lists and mappings in config.yaml keep working exactly as before.

Edits A-E add the two settings. Edits F-I add the limits for them
(dynamic_parameter_max_count, dynamic_parameter_max_chars). A file that already
has A-E gets only F-I.
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
    # F. config: limits for "auto" and "*"
    (
        "        self.forward_end_session_fields = [str(name) for name in _forward_fields]\n",
        "        self.forward_end_session_fields = [str(name) for name in _forward_fields]\n"
        "        # byova_ces dynamic parameters: limits for \"auto\" and \"*\". Names in a\n"
        "        # list or mapping are chosen by you and are not limited.\n"
        "        self.dynamic_parameter_max_count = max(\n"
        "            1, int(config.get(\"dynamic_parameter_max_count\", 20))\n"
        "        )\n"
        "        self.dynamic_parameter_max_chars = max(\n"
        "            1, int(config.get(\"dynamic_parameter_max_chars\", 256))\n"
        "        )\n",
    ),
    # G. CES -> CVP: apply the limits in "*" mode
    (
        "            allowed = list(self._end_session_fields(metadata))\n",
        "            allowed, over_limit = self.connector._limit_dynamic_parameters(\n"
        "                self._end_session_fields(metadata)\n"
        "            )\n"
        "            if over_limit:\n"
        "                self.logger.warning(\n"
        "                    \"[%s] [GECX] end_session fields NOT sent to CVP, over the limit \"\n"
        "                    \"(%d fields, %d characters each): %s\",\n"
        "                    self.conversation_id,\n"
        "                    self.connector.dynamic_parameter_max_count,\n"
        "                    self.connector.dynamic_parameter_max_chars,\n"
        "                    sorted(over_limit),\n"
        "                )\n",
    ),
    # H. CVP -> CES: apply the limits in "auto" mode (caller number first)
    (
        "        # names only, never values\n"
        "        self.logger.info(\n"
        "            \"[GECX] Session variables for %s (auto): %s%s\",\n",
        "        variables, over_limit = self._limit_dynamic_parameters(\n"
        "            variables, keep_first=tuple(self._AUTO_SIP_VARIABLES.values())\n"
        "        )\n"
        "        if over_limit:\n"
        "            self.logger.warning(\n"
        "                \"[GECX] Session variables for %s NOT sent to CES, over the limit \"\n"
        "                \"(%d parameters, %d characters each): %s\",\n"
        "                conversation_id,\n"
        "                self.dynamic_parameter_max_count,\n"
        "                self.dynamic_parameter_max_chars,\n"
        "                sorted(over_limit),\n"
        "            )\n"
        "        # names only, never values\n"
        "        self.logger.info(\n"
        "            \"[GECX] Session variables for %s (auto): %s%s\",\n",
    ),
    # I. the helper that applies the limits
    (
        "    _SIP_URI = re.compile(r\"^\\s*<?\\s*(?:sips?|tel):([^@;>\\s]+)\", re.IGNORECASE)\n",
        "    def _limit_dynamic_parameters(\n"
        "        self, values: Dict[str, Any], keep_first: Tuple[str, ...] = ()\n"
        "    ) -> Tuple[Dict[str, Any], list]:\n"
        "        \"\"\"byova_ces dynamic parameters: apply the count and length limits.\n"
        "\n"
        "        Returns (kept, names not sent). A value that is too long is left out,\n"
        "        not cut: a shortened account or ticket number would be a wrong value.\n"
        "        \"\"\"\n"
        "        kept: Dict[str, Any] = {}\n"
        "        over_limit = []\n"
        "        names = [n for n in keep_first if n in values]\n"
        "        names += [n for n in values if n not in keep_first]\n"
        "        for name in names:\n"
        "            if (\n"
        "                len(str(values[name])) > self.dynamic_parameter_max_chars\n"
        "                or len(kept) >= self.dynamic_parameter_max_count\n"
        "            ):\n"
        "                over_limit.append(name)\n"
        "            else:\n"
        "                kept[name] = values[name]\n"
        "        return kept, over_limit\n"
        "\n"
        "    _SIP_URI = re.compile(r\"^\\s*<?\\s*(?:sips?|tel):([^@;>\\s]+)\", re.IGNORECASE)\n",
    ),
]

MARKERS = [
    "            metadata = {\"params\": params if isinstance(params, Mapping) else {}}\n",
    "        self.session_variables_auto = (\n",
    "        _forward_fields = config.get(\"forward_end_session_fields\") or []\n",
    "            return self._auto_session_variables(conversation_id, request_data)\n",
    "    def _auto_session_variables(\n",
    "        self.dynamic_parameter_max_count = max(\n",
    "            allowed, over_limit = self.connector._limit_dynamic_parameters(\n",
    "        variables, over_limit = self._limit_dynamic_parameters(\n",
    "    def _limit_dynamic_parameters(\n",
]

assert len(EDITS) == len(MARKERS) == 9
applied = skipped = 0
for label, (old, new), marker in zip("ABCDEFGHI", EDITS, MARKERS):
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
