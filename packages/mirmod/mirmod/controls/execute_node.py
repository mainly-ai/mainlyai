class ExecuteNode:
  # This control presents a button to the user which lets
  # them re-compile the node from the current state of the
  # node's API within designer. This allows powerusers to
  # create dynamic nodes that can change attributes depending
  # on the state of other controls on the node.

  def __init__(self, label="Execute", use_inbound=False, recompile=True, disabled=False):
    self.kind = 'execute-node'
    self.label = label
    self.use_inbound = use_inbound
    self.recompile = recompile
    self.disabled = disabled

  def to_dict(self):
    return {
      'kind': self.kind,
      'label': self.label,
      'use_inbound': self.use_inbound, # receive from adjacent nodes before execute
      'recompile': self.recompile, # reload node and recompile
      'disabled': self.disabled
    }
