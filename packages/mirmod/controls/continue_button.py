class ContinueButton:
  # This control presents a button to the user which lets
  # them re-compile the node from the current state of the
  # node's API within designer. This allows powerusers to
  # create dynamic nodes that can change attributes depending
  # on the state of other controls on the node.

  def __init__(self, label="Continue", disabled=True):
    self.kind = 'continue-execution'
    self.label = label
    self.disabled = disabled

  def to_dict(self):
    return {
      'kind': self.kind,
      'label': self.label,
      'disabled': self.disabled
    }
