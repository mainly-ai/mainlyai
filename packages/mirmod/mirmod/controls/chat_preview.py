class ChatPreview:
  def __init__(self):
    self.kind = 'chat-preview'

  def to_dict(self):
    return {
      'kind': self.kind
    }