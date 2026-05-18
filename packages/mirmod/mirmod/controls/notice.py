# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Notice:
  def __init__(self, level='info', message=''):
    self.kind = 'notice'
    self.level = level
    self.message = message

  def to_dict(self):
    return {
      'kind': self.kind,
      'level': self.level,
      'message': self.message
    }
