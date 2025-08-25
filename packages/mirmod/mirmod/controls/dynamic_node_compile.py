class DynamicNodeCompileButton:
  # This control presents a button to the user which lets
  # them re-compile the node from the current state of the
  # node's API within designer. This allows powerusers to
  # create dynamic nodes that can change attributes depending
  # on the state of other controls on the node.

  def __init__(self, label="Update Dynamic Node"):
    self.kind = 'dynamic-node-compile'
    self.label = label

  def to_dict(self):
    return {
      'kind': self.kind,
      'label': self.label
    }
