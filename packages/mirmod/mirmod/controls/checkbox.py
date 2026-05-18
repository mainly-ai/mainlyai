# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Checkbox:
  def __init__(self, checked=False):
    self.kind = 'checkbox'
    self.checked = checked
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'checked': self.checked
    }
