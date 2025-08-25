class ImageMask:
  def __init__(self,width=-1,height=-1, polygons=[], url=None, style=None):
    self.kind = 'image-mask'
    self.width = width
    self.height = height,
    self.polygons = polygons,
    self.url = url
    self.style = style

  def to_dict(self):
    return {
      'kind': self.kind,
      'width': self.width,
      'height': self.height,
      'polygons': self.polygons,
      'url': self.url,
      'style': self.style # a JSON string containing line_color, point_color and surface_color.
    }
