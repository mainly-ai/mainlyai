# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class File:
  def __init__(self, accept: str = None, capture: str = None):
    self.kind = 'file'
    self.accept = accept
    if capture is not None and capture not in ['camera', 'microphone']:
      raise Exception("Capture must be either 'camera' or 'microphone'")
    self.capture = capture

  def to_dict(self):
    return {
      'kind': self.kind,
      'accept': self.accept,
      'capture': self.capture
    }
