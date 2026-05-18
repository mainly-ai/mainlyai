# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Plotly:
  # TODO: add plot options here later

  def __init__(self):
    self.kind = 'plotly'

  def to_dict(self):
    return {
      'kind': self.kind
    }
