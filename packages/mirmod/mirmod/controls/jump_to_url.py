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
