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
