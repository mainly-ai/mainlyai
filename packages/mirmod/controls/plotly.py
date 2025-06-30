class Plotly:
  # TODO: add plot options here later

  def __init__(self):
    self.kind = 'plotly'

  def to_dict(self):
    return {
      'kind': self.kind
    }
