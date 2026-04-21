class TerminalShell:
  def __init__(self, rows=1, cols=1, init_commands=""):
    self.kind = 'terminalshell'
    self.cols = cols
    self.init_commands = init_commands.split("\n")
    self.rows = rows
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'rows' : self.rows,
      'cols' : self.cols,
      'init_commands' : self.init_commands

    }
