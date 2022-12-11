from includes.epd import Epd 
from PIL import Image, ImageFont, ImageDraw
from fonts.ttf import FredokaOne
import spidev as SPI

# For now we have added tooling for a Waveshare display, but if desired we could
# do a refactor where we support other types of e-ink or other displays.
# Admittedly, what you see here isn't exactly beautiful or elegant, but the idea
# is clear:  we produce a generic visualization and outsource it to some specified
# display driver.
class Waveshare(object):
  def __init__(self, display_type=None, display_height=0, display_width=0, num_rows=5):
    self.display = None

    if (display_type):
      self.spi = SPI.SpiDev(0, 0)  # TODO:  Will this ever need to be configurable?
      self.display = Epd(self.spi, self.display_type)

    self.current_row = 0
    self.max_rows = num_rows
    self.display_width = display_width
    self.display_height = display_height

    self.row_width = display_width
    if (display_height):
      self.row_height = int(display_height / num_rows)

    self.img = None
    self.font = ImageFont.truetype(FredokaOne, self.row_height - 2)

    if (self.display)
      self.display.clearDisplayPart()

  def reset():
    self.current_row = 0
    self.img = Image.new("P", (self.display_width, self.display_height))

  def write_row(self, message):
    if (self.current_row < self.max_rows):
      draw = ImageDraw.Draw(img)
      draw.text((1, 1 + self.row_height * self.current_row), message, inky_display.BLACK, self.font)
      self.current_row += 1

  def update():
    if (self.display)
      self.display.showImageFull(self.display.imageToPixelArray(self.img))

