# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class Video:
  # Hmm, can't think of any options are needed for images
  # but they can just be added here later if needed
  def __init__(self,width=-1,height=-1,type="video/mp4",src=None):
    self.kind = 'video'
    self.width = width
    self.height = height
    self.type= type
    self.src= src

  def to_dict(self):
    return {
      'kind': self.kind,
      'width': self.width,
      'height': self.height,
      'type': self.type,
      'src': self.src
    }
