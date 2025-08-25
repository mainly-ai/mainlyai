class Table:
  def __init__(self, columns=[], format='csv'):
    self.kind = 'table'
    if format not in ['csv', 'json']:
      raise ValueError('format must be csv or json')
    self.format = format
    self.columns = columns

  def to_dict(self):
    return {
      'kind': self.kind,
      'format': self.format,
      'columns': self.columns
    }
