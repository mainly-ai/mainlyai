class Select:
  def __init__(self, choices=[], placeholder=""):
    self.kind = 'select'
    self.choices = list(map(lambda x: str(x), choices))
    self.placeholder = placeholder

  def to_dict(self):
    return {
      'kind': self.kind,
      'choices': self.choices,
      'placeholder': self.placeholder
    }

class KVSelect:
  def __init__(self, source, placeholder="Select a value", type="secret"):
    self.kind = 'select'
    self.source = source
    self.placeholder = placeholder
    if type not in ['secret', 'model']:
      raise Exception("KVSelect type is invalid. Must be model or secret")
    self.type = type

  def to_dict(self):
    return {
      'kind': self.kind,
      'source': self.source,
      'placeholder': self.placeholder,
      'type': self.type
    }
