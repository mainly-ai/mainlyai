# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class ChatPreview:
  def __init__(self):
    self.kind = 'chat-preview'

  def to_dict(self):
    return {
      'kind': self.kind
    }