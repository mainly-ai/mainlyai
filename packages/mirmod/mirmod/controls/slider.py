# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Slider:
  def __init__(self, min=0.0, max=1.0, step=0.1):
    self.kind = 'slider'
    self.min = min
    self.max = max
    self.step = step
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'min': self.min,
      'max': self.max,
      'step': self.step
    }
