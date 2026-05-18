# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Image:
  # Hmm, can't think of any options are needed for images
  # but they can just be added here later if needed
  def __init__(self,width=-1,height=-1):
    self.kind = 'image'
    self.width = width
    self.height = height

  def to_dict(self):
    return {
      'kind': self.kind,
      'width': self.width,
      'height': self.height
    }
