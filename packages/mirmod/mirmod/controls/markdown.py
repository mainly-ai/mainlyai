# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

import json


class Markdown:
    def __init__(self, text="", options={}, blocktag=None):
        self.kind = "markdown"
        self.text = text
        self.options = json.dumps(options)
        self.blocktag = blocktag

    def to_dict(self):
        return {
            "kind": self.kind,
            "text": self.text,
            "options": self.options,
            "blocktag": self.blocktag,
        }
