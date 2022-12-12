from includes.epd import Epd
from PIL import Image, ImageFont, ImageDraw
from fonts.ttf import FredokaOne
import epaper

# For now we have added tooling for a Waveshare display, but if desired we could
# do a refactor where we support other types of e-ink or other displays.
class Waveshare(object):
  def __init__(self, display_type, num_rows=5): 
    self.display = epaper.epaper(display_type).EPD()
    self.display.init()
    self.display.Clear()

    self.current_row = 0
    self.max_rows = num_rows
    self.display_width = self.display.width
    self.display_height = self.display.height
    self.row_height = int(display_height / num_rows)
    self.img = None
    self.font = ImageFont.truetype(FredokaOne, self.row_height - 2)

  def reset():
    self.current_row = 0
    self.img = Image.new("1", (self.display_width, self.display_height), 255)

  def write_row(self, message):
    if (self.current_row < self.max_rows):
      draw = ImageDraw.Draw(self.img)
      draw.text((1, 1 + self.row_height * self.current_row), message, fill=0, self.font)
      self.current_row += 1

  def update():
    self.display.showImageFull(self.display.getbuffer(self.img))

