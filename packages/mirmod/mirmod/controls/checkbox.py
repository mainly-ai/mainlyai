class Checkbox:
  def __init__(self, checked=False):
    self.kind = 'checkbox'
    self.checked = checked
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'checked': self.checked
    }
