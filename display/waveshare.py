from PIL import Image, ImageFont, ImageDraw
from fonts.ttf import FredokaOne
import waveshare_epd  # Installed in stage2/03-run, not requirements. 
import importlib

# For now we have added tooling for a Waveshare display, but if desired we could
# do a refactor where we support other types of e-ink or other displays.
class Waveshare(object):
  def __init__(self, display_type, num_rows=5): 

    epaper = importlib.import_module("." + display_type, "waveshare_epd")
    self.display = epaper.EPD()
    self.display.init()

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
      draw.text((1, 1 + self.row_height * self.current_row), message, fill=0, font=self.font)
      self.current_row += 1

  def update():
    self.display.showImageFull(self.display.getbuffer(self.img))

