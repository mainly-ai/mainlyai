# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Audio:
  # Hmm, can't think of any options are needed for images
  # but they can just be added here later if needed
  def __init__(self,src=None):
    self.kind = 'audio'
    self.src= src

  def to_dict(self):
    return {
      'kind': self.kind,
      'src': self.src
    }
