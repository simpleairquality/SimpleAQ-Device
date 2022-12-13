from PIL import Image, ImageFont, ImageDraw
from fonts.ttf import FredokaOne
import epaper 

# For now we have added tooling for a Waveshare display, but if desired we could
# do a refactor where we support other types of e-ink or other displays.
# Note that the differences in the Waveshare drivers between displays are different
# enough that we must treat each individually.
class Waveshare(object):
  def __init__(self, display_type, logging=None): 

    self.display = epaper.epaper(display_type).EPD()
    self.display_type = display_type

    self.logging = logging

    if display_type == "epd2in13_V3":
      self.display.init()
    else:
      self.logging.warn("Unsupported Display Type: " + display_type)

    self.current_row = 0
    self.display_width = self.display.width
    self.display_height = self.display.height
    self.row_height = 20
    self.img = None
    self.font = ImageFont.truetype(FredokaOne, 16)

  def reset(self):
    self.current_row = 0
    self.img = Image.new("1", (self.display_height, self.display_width), 255)

  def write_row(self, message):
    draw = ImageDraw.Draw(self.img)
    draw.text((1, 1 + self.row_height * self.current_row), message, fill=0, font=self.font)
    self.current_row += 1

  def update(self):
    if self.display_type == "epd2in13_V3":
      self.display.display(self.display.getbuffer(self.img))

      

