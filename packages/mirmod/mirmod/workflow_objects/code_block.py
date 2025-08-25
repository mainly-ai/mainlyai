from datetime import datetime
from mirmod.utils import logger
from ..security.security_context import Security_context
from ..orm.base_orm import Base_object_ORM
import json
import pandas as pd
from PIL import Image
import numpy as np
import difflib
from collections import deque
import re


def value2json(value: any):
    sval: str = ""
    if isinstance(value, dict):
        sval = json.dumps(value)
    elif isinstance(value, pd.DataFrame):
        sval = json.dumps(value.to_json())
    elif isinstance(value, pd.Series):
        sval = value.to_json()
    elif isinstance(value, list):
        sval = json.dumps(value)
    elif isinstance(value, Image.Image):
        sval = json.dumps(
            np.array(value.getdata()).reshape(value.size[0], value.size[1], 3).tolist()
        )
    elif isinstance(value, np.ndarray):
        sval = value.tolist()
    else:
        sval = value
    return sval


_hdr_pat = re.compile(r"^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@$")


def patch(source_string, patch, reversed=False):
    """
    Apply unified diff patch to string s to recover newer string.
    If revert is True, treat s as the newer string, recover older string.
    """
    source_lines = source_string.splitlines(True)
    patch_lines = patch.splitlines(True)
    result_string = ""
    patch_index = source_line_index = 0
    (match_index, target_sign) = (1, "+") if not reversed else (3, "-")
    while patch_index < len(patch_lines) and patch_lines[patch_index].startswith(
        ("---", "+++")
    ):
        patch_index += 1  # skip header lines
    while patch_index < len(patch_lines):
        header_match = _hdr_pat.match(patch_lines[patch_index])
        if not header_match:
            raise Exception("Cannot process diff")
        patch_index += 1
        target_line = (
            int(header_match.group(match_index))
            - 1
            + (header_match.group(match_index + 1) == "0")
        )
        result_string += "".join(source_lines[source_line_index:target_line])
        source_line_index = target_line
        while patch_index < len(patch_lines) and patch_lines[patch_index][0] != "@":
            if (
                patch_index + 1 < len(patch_lines)
                and patch_lines[patch_index + 1][0] == "\\"
            ):
                current_line = patch_lines[patch_index][:-1]
                patch_index += 2
            else:
                current_line = patch_lines[patch_index]
                patch_index += 1
            if len(current_line) > 0:
                if current_line[0] == target_sign or current_line[0] == " ":
                    result_string += current_line[1:]
                source_line_index += current_line[0] != target_sign
    result_string += "".join(source_lines[source_line_index:])
    return result_string


class Code_block(Base_object_ORM):
    """The code block creator is the entity which links a code segment with a model or etl process"""

    sql_code_block_ORM = {
        "id": "t.id as id",
        "api": "t.api as api",
        "order": "t.`order` as `order`",
        "body": "t.body as body",
        "code_type": "t.code_type as code_type",
        "platform_dependency_type": "t.platform_dependency_type as platform_dependency_type",
        "platform_dependency_version": "t.platform_dependency_version as platform_dependency_version",
        "git": "t.git as git",
        "git_branch": "t.git_branch as git_branch",
        "update_policy": "t.update_policy as update_policy",
        "diffs": "t.diffs as diffs",
    }
    sql_code_block_ORM.update(Base_object_ORM.metadata)

    def __init__(
        self, sc: Security_context, id: int = -1, metadata_id: int = None, user_id=-1
    ):
        self.default_value = {
            "id": -1,
            "metadata_id": -1,
            "order": 0,
            "code_type": "python",
            "platform_dependency_type": "REQUIREMENTS",
            "platform_dependency_version": 0,
            "git": "",
            "git_branch": "main",
            "api": "{}",
            "body": "",
            "update_policy": "NEVER",
            "diffs": "[]",
            "status": "{}",
        }
        self.id = id
        self.sctx: Security_context = sc
        self.create_mapping(self.sql_code_block_ORM, "code")
        if metadata_id is not None:
            self._load_from_metadata_id(sc, metadata_id, user_id=user_id)
            # logger.info("Created code block object with metadata id: " + str(metadata_id))
        elif id != -1:
            self._load_from_id(sc, self.id)
            # logger.info("Created code block object with id: " + str(self.id))
        self.japi = None
        self.jdiffs = []

    def get_attribute(self, attribute_name: str) -> dict:
        """Given a code block, and an attribute name, return the correspodning value and kind fields.
        Returns:
            dict: {"value" : value, "kind" : kind} where the value is a str which might contain a json list or object.
            Returns None if the attribute isn't found."""

        if self.api is None:
            return None
        if self.japi is None:
            try:
                self.japi = json.loads(self.api)
            except Exception as e:
                logger.error(f"Error loading api: {e}")
                return None
        attributes = self.japi.get("attributes", [])
        for a in attributes:
            if a.get("name", None) == attribute_name:
                return {
                    "name": a.get("name"),
                    "value": a.get("value", None),
                    "kind": a.get("kind", "Unknown"),
                    "direction": a.get("direction", 0),
                }
        return None

    def set_attribute(self, attribute_name: str, value, kind: str = None):
        """Given a code block, and an attribute name, set the correspodning value and kind fields.
        IMPORTANT: Setting an attribute in the code block is equivalent to setting the default value
        for the attribute. It shouldn't be used for passing values between code blocks in a workflow.
        Attributes of type np.array, PIL.Image, pd.DataFrame, pd.Series, dict, and list are automatically
        converted to json strings (not json objects!)"""

        if kind is not None:
            kind = kind.lower()
        if self.api is None:
            self.japi = {
                "attributes": [{"name": attribute_name, "value": value, "kind": kind}]
            }
            self.api = json.dumps(self.japi)
        elif self.japi is None:
            try:
                self.japi = json.loads(self.api)
            except Exception as e:
                logger.error(f"Error loading api: {e}")
                return False  # failure
        attributes = self.japi.get("attributes", [])
        found = False
        for a in attributes:
            if a["name"] == attribute_name:
                a["value"] = value2json(value)
                if kind is not None:
                    a["kind"] = kind
                found = True
        if not found:
            attributes.append(
                {"name": attribute_name, "value": value2json(value), "kind": kind}
            )
        self.japi["attributes"] = attributes
        self.api = json.dumps(self.japi)
        self.update(self.sctx)
        return True

    def get_attributes(self):
        if self.japi is None:
            try:
                self.japi = json.loads(self.api)
            except Exception as e:
                logger.error(f"Error loading api: {e}")
                return None
        return self.japi.get("attributes", [])

    def write_diff(self, new_code):
        """Write a diff between the old and new code and store it in the code block. This method doesn't call update()!"""
        if self.body is None:
            self.diffs = "[]"
            return
        if self.diffs is None or self.diffs == "":
            self.diffs = "[]"
        old_code = self.body
        diff = difflib.unified_diff(
            old_code.splitlines(), new_code.splitlines(), lineterm=""
        )
        self.jdiffs = json.loads(self.diffs)
        self.jdiffs = deque(self.jdiffs, maxlen=5)
        self.jdiffs.appendleft(
            {
                "diff": "\n".join(diff),
                "ts": datetime.now().isoformat(),
                "user_id": self.sctx.user_id(),
            }
        )
        self.jdiffs = list(self.jdiffs)
        self.diffs = json.dumps(self.jdiffs)

    def diff_from_clone(self, last_in_chain: bool = False, reverse: bool = False):
        # Use python difflib to diff body with the body of the code block it was cloned from
        if self.cloned_from_id is None or self.cloned_from_id == -1:
            return ""
        clone = Code_block(self.sctx, metadata_id=self.cloned_from_id)
        if clone.id == -1:
            return ""
        ct = 0
        if last_in_chain:
            # search all Code_blocks in the chain of cloned_from_id until the last one
            while clone.cloned_from_id is not None and clone.cloned_from_id != -1:
                new_clone = Code_block(self.sctx, metadata_id=clone.cloned_from_id)
                if new_clone.id == -1:
                    break
                clone = new_clone
                if ct > 10:
                    break  # prevent infinite loops

        old_code = clone.body
        new_code = self.body
        if reverse:
            diff = difflib.unified_diff(
                new_code.splitlines(), old_code.splitlines(), lineterm=""
            )
        else:
            diff = difflib.unified_diff(
                old_code.splitlines(), new_code.splitlines(), lineterm=""
            )
        return "\n".join(diff)

    def update_from_clone(self, last_in_chain=False):
        """Update the body of the code block with the body of the code block it was cloned from or, if there's a git repo,
        pull the latest version of the code from the git repo. This method calls update().
        Returns:
            >0 if the update was successful. The return is the clone metadata_id which was used.
            -1 if the code block was not cloned from another code block."""
        if self.cloned_from_id is None or self.cloned_from_id == -1:
            if self.git is not None and self.git != "":
                try:
                    # Use globals().get() to safely access git_pull if it's been injected at runtime
                    git_pull_func = globals().get("git_pull")
                    if git_pull_func is None:
                        logger.error(
                            "=> Error: git_pull function not available in runtime"
                        )
                        return -1
                    clone = git_pull_func(self.git)
                except Exception as e:
                    print("=> Error pulling git repo: " + str(e))
                    return -1
        else:
            clone_id = self.get_clone_metadata_id(last_in_chain)
            clone = Code_block(self.sctx, metadata_id=clone_id)
            if clone.id == -1:
                return -1
        self.body = clone.body
        self.update(self.sctx)
        return clone.metadata_id

    def get_clone_metadata_id(self, last_in_chain=False):
        """Get the id of the code block this code block was cloned from.
        Returns:
            int: The id of the code block this code block was cloned from, or -1 if the code block was not cloned from another code block."""
        if self.cloned_from_id is None or self.cloned_from_id == -1:
            return -1
        if last_in_chain:
            # search all Code_blocks in the chain of cloned_from_id until the last one
            ct = 0
            clone = Code_block(self.sctx, metadata_id=self.cloned_from_id)
            if clone.id == -1:
                return -1
            while clone.cloned_from_id is not None and clone.cloned_from_id != -1:
                new_clone = Code_block(self.sctx, metadata_id=clone.cloned_from_id)
                if new_clone.id == -1:
                    break
                clone = new_clone
                if ct > 10:
                    break  # prevent infinite loops
            return clone.metadata_id
        else:
            return self.cloned_from_id

    def revert(self, steps=1, preview=False):
        """Revert the code block to a previous version. This method calls update()"""
        if self.diffs is None or self.diffs == "":
            return
        self.jdiffs = json.loads(self.diffs)
        if len(self.jdiffs) < steps:
            return
        # for every diff remaining, apply it using difftools and finally replace the old code with the new code.
        new_code = self.body
        for i in range(1, steps + 1):
            diff = self.jdiffs.pop(0)
            new_code = patch(new_code, diff["diff"], reversed=True)

        if preview:
            return new_code

        self.body = new_code
        self.diffs = json.dumps(self.jdiffs)
        self.update(self.sctx)

    def update_api(self, new_api: dict):
        """Updates the api, carrying over the values of the old api. This method does not call update()"""
        if self.api is None or self.api == "":
            self.api = "{}"
        oapi = json.loads(self.api)
        for attr in oapi["attributes"]:
            for new_attr in new_api["attributes"]:
                if new_attr["name"] == attr["name"]:
                    new_attr["value"] = attr["value"]

        self.api = json.dumps(new_api)
