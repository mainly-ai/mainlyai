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
