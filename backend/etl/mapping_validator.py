from __future__ import annotations
import re
from typing import Dict, Any, List, Tuple

REQUIRED_KEYS = {
    "jira": ["points_field", "status_map"],
    "clickup": ["points_field_name"],
    "azure": ["points_field"],
    "github": ["link_patterns"],
}

CANONICAL_STEPS = [
    "dev_started","dev_done","ready_for_qa","qa_started","qa_verified",
    "signed_off","ready_for_uat","deployed_uat","done"
]

def _compile_regex(pat: str) -> Tuple[bool, str]:
    try:
        re.compile(pat)
        return True, ""
    except re.error as e:
        return False, str(e)

def _nonempty_list(val) -> bool:
    return isinstance(val, list) and all(isinstance(x, str) and x.strip() for x in val)

def validate_mapping_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      {
        "ok": bool,
        "errors": [ { "path": "jira.points_field", "msg": "..." }, ...],
        "warnings": [ ... ],
        "normalized": <possibly normalized cfg>
      }
    """
    errors, warnings = [], []
    cfg = cfg or {}

    # ----- presence / shapes -----
    for section, keys in REQUIRED_KEYS.items():
        if section not in cfg:
            errors.append({"path": section, "msg": f"Missing '{section}' section"})
            continue
        sec = cfg.get(section) or {}
        for k in keys:
            if k not in sec:
                errors.append({"path": f"{section}.{k}", "msg": f"Missing '{k}'"})
    # jira
    jira = cfg.get("jira", {}) or {}
    if "points_field" in jira and not isinstance(jira.get("points_field"), str):
        errors.append({"path": "jira.points_field", "msg": "Must be a string (e.g., customfield_10016)"})
    status_map = jira.get("status_map", {}) or {}
    if not isinstance(status_map, dict):
        errors.append({"path": "jira.status_map", "msg": "Must be an object of arrays"})
    else:
        # every canonical step must exist and be a non-empty array of strings
        for step in CANONICAL_STEPS:
            vals = status_map.get(step)
            if vals is None:
                warnings.append({"path": f"jira.status_map.{step}", "msg": "Not mapped — timestamps for this step won't be set"})
                continue
            if not _nonempty_list(vals):
                errors.append({"path": f"jira.status_map.{step}", "msg": "Must be a non-empty list of status names"})
        # Detect duplicates across steps
        seen = {}
        for step, arr in status_map.items():
            if not isinstance(arr, list): 
                errors.append({"path": f"jira.status_map.{step}", "msg": "Must be a list"})
                continue
            for s in arr:
                key = s.lower().strip()
                if not key:
                    errors.append({"path": f"jira.status_map.{step}", "msg": "Empty status string"})
                    continue
                if key in seen and seen[key] != step:
                    warnings.append({"path": f"jira.status_map", "msg": f"Status '{s}' appears in multiple steps: {seen[key]} and {step}"})
                else:
                    seen[key] = step

    # clickup
    clickup = cfg.get("clickup", {}) or {}
    if "points_field_name" in clickup and not isinstance(clickup.get("points_field_name"), str):
        errors.append({"path": "clickup.points_field_name", "msg": "Must be a string (custom field display name)"})

    # azure
    azure = cfg.get("azure", {}) or {}
    if "points_field" in azure and not isinstance(azure.get("points_field"), str):
        errors.append({"path": "azure.points_field", "msg": "Must be a string (e.g., Microsoft.VSTS.Scheduling.StoryPoints)"})

    # github
    github = cfg.get("github", {}) or {}
    link_patterns = github.get("link_patterns", {}) or {}
    if not isinstance(link_patterns, dict):
        errors.append({"path": "github.link_patterns", "msg": "Must be an object (name -> regex string)"})
    else:
        for name, pat in link_patterns.items():
            if not isinstance(pat, str):
                errors.append({"path": f"github.link_patterns.{name}", "msg": "Must be a regex string"})
                continue
            ok, err = _compile_regex(pat)
            if not ok:
                errors.append({"path": f"github.link_patterns.{name}", "msg": f"Invalid regex: {err}"})

    # validator thresholds (optional section)
    validator = cfg.get("validator")
    if validator is not None and not isinstance(validator, dict):
        errors.append({"path": "validator", "msg": "Must be an object with numeric thresholds"})
    else:
        # soft checks
        for k in ["max_dev_days_without_progress", "max_ready_for_qa_days", "max_qa_days"]:
            if k in (validator or {}):
                v = validator.get(k)
                if not isinstance(v, (int, float)) or v < 0:
                    errors.append({"path": f"validator.{k}", "msg": "Must be a non-negative number"})

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings, "normalized": cfg}
