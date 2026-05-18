# SPDX-FileCopyrightText: 2026 Kristofer Älvring <kristofer@mainly.ai>
# SPDX-FileCopyrightText: 2026 Leah Lundqvist <leah@mainly.ai>
#
# SPDX-License-Identifier: GPL-2.0-only

class JumpToURL:
  # Hmm, can't think of any options are needed for images
  # but they can just be added here later if needed
  def __init__(self,url="https://platform.mainly.ai/docs",label="Goto URL",disabled=False):
    self.kind = 'jump-to-url'
    self.url= url
    self.label = label
    self.disabled = disabled

  def to_dict(self):
    return {
      'kind': self.kind,
      'label': self.label,
      'url': self.url,
      'disabled': self.disabled
    }
