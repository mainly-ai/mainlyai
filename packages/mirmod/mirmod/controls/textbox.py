class Textbox:
  def __init__(self, placeholder="", min_len=0, max_len=256, rows=1, regex=".*"):
    self.kind = 'textbox'
    self.placeholder = placeholder
    self.min_len = min_len
    self.max_len = max_len
    self.regex = regex
    self.rows = rows
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'placeholder': self.placeholder,
      'min_len': self.min_len,
      'max_len': self.max_len,
      'regex': self.regex,
      'rows' : self.rows
    }
