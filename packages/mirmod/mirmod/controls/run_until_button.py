# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class RunUntilButton:
  # This control presents a button to the user which lets
  # them run the graph until the node is reached. This allows
  # for the creation of nodes that update their attributes
  # based on their inputs.

  def __init__(self, label="Run Until this Node"):
    self.kind = 'run-until'
    self.label = label

  def to_dict(self):
    return {
      'kind': self.kind,
      'label': self.label
    }
