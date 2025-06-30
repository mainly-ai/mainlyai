class Slider:
  def __init__(self, min=0.0, max=1.0, step=0.1):
    self.kind = 'slider'
    self.min = min
    self.max = max
    self.step = step
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'min': self.min,
      'max': self.max,
      'step': self.step
    }
