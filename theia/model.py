from time import time
from collections import namedtuple
from io import StringIO, SEEK_CUR
import re



EventPreamble = namedtuple('EventPreamble', ['total','header','content'])

class Header:

  def __init__(self, id=None, timestamp=None, source=None, tags=None):
    self.id = id
    self.timestamp = timestamp
    self.source = source
    self.tags = tags


class Event:
  def __init__(self, id, source, timestamp=None, tags=None, content=None):
    self.id = id
    self.source = source
    self.timestamp = timestamp or time() # time in nanoseconds UTC
    self.tags = tags or []
    self.content = content or ''
  
  def match(self, id=None, source=None, start=None, end=None, content=None, tags=None):
    matches = True
    
    if id is not None:
      matches = _match(id, self.id)
    if matches and source is not None:
      matches = _match(source, self.source)
    if matches and self.timestamp:
      if start is not None:
        matches = self.timestamp >= start
      if matches and end is not None:
        matches = self.timestamp <= end
    if matches and content is not None:
      matches = _match(content, self.content)
    if matches and len(self.tags) and tags:
      has_tag = False
      for t in tags:
        if t in self.tags:
          has_tag = True
      if not has_tag:
        matches = False
      
    
    return matches

def _match(pattern, value):
  if value is None:
    return False
  return re.match(pattern, value) is not None


class EventSerializer:

  def __init__(self, encoding='utf-8'):
    self.encoding = encoding

  def serialize(self, event):
    event_str = ''
    hdr = self._serialize_header(event)
    hdr_size = len(hdr.encode(self.encoding))
    cnt_size = len(event.content.encode(self.encoding))
    total_size = hdr_size + cnt_size
    event_str += 'event: %d %d %d\n' %(total_size, hdr_size, cnt_size)
    event_str += hdr
    event_str += event.content
    event_str += '\n'
    return event_str.encode(self.encoding)

  def _serialize_header(self, event):
    hdr = ''
    hdr += 'id:' + str(event.id) + '\n'
    hdr += 'timestamp: %.7f' % event.timestamp + '\n'
    hdr += 'source:' + str(event.source) + '\n'
    hdr += 'tags:' + ','.join(event.tags) + '\n'
    return hdr


class EventParser:

  def __init__(self, encoding='utf-8'):
    self.encoding = encoding

  def parse_header(self, hdr_size, stream):
    bytes = stream.read(hdr_size)
    if len(bytes) != hdr_size:
      raise Exception('Invalid read size from buffer. The stream is either unreadable or corrupted. %d read, expected %d' %(len(bytes), hdr_size))
    hdr_str = bytes.decode(self.encoding)
    header = Header()
    sio = StringIO(hdr_str)

    ln = sio.readline()
    while ln:
      ln = ln.strip()
      if not ln:
        raise Exception('Invalid header')
      idx = ln.index(':')
      prop = ln[0:idx]
      value = ln[idx+1:]
      if prop == 'id':
        header.id = value
      elif prop == 'timestamp':
        header.timestamp = float(value)
      elif prop == 'source':
        header.source = value
      elif prop == 'tags':
        header.tags = value.split(',')
      else:
        raise Exception('Unknown property in header %s' % prop)
      ln = sio.readline()
    sio.close()
    return header

  def parse_preamble(self, stream):
    pstr = stream.readline()
    if pstr is None:
      raise EOFException()
    if pstr:
      pstr = pstr.decode(self.encoding).strip()
    if not pstr or not pstr.startswith('event:'):
      raise Exception('Invalid preamble line')

    values = pstr[len('event:') + 1:].split(' ')
    if len(values) != 3:
      raise Exception('Invalid preamble values')

    return EventPreamble(total=int(values[0]), header=int(values[1]), content=int(values[2]))

  def parse_event(self, stream, skip_content=False):
    preamble = self.parse_preamble(stream)
    header = self.parse_header(preamble.header, stream)
    content = None
    if skip_content:
      stream.seek(preamble.content, SEEK_CUR)
    else:
      content = stream.read(preamble.content)
      content=content.decode(self.encoding)
    print(stream, stream.seekable())
    stream.seek(1, SEEK_CUR) # new line after each event
    
    if len(content) != preamble.content:
      raise Exception('Invalid content size. The stream is either unreadable or corrupted.')

    return Event(id=header.id, source=header.source, timestamp=header.timestamp, tags=header.tags, content=content)



def EOFException(Exception):
  pass
