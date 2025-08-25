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
