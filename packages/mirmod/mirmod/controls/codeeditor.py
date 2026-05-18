# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class CodeEditor:
    def __init__(self, placeholder="", max_len=16000, rows=4, language="python"):
        self.kind = "code-editor"
        self.placeholder = placeholder
        self.max_len = max_len
        self.rows = rows
        self.language = "python"

    def to_dict(self):
        return {
            "kind": self.kind,
            "placeholder": self.placeholder,
            "max_len": self.max_len,
            "rows": self.rows,
            "language": self.language,
        }
