class Chatbot:
  def __init__(self, url, width=-1, height=-1,user="Anonymous",conversation_id="",secret="",avatar=""):
    self.kind = 'chatbot'
    self.url = url
    self.width = width
    self.height = height
    self.conversation_id = conversation_id
    self.user = user
    self.avatar = avatar
    self.secret = secret
  
  def to_dict(self):
    return {
      'kind': self.kind,
      'url': self.url,
      'width': self.width,
      'height': self.height,
      'user' : self.user,
      'conversation_id' : self.conversation_id,
      'secret' : self.secret
    }
