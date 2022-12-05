from inky import InkyPHAT
from PIL import Image, ImageFont, ImageDraw
from fonts.ttf import FredokaOne

class InkyPhat(object):
  def __init__(self, num_rows=5):
    self.inky_display = InkyPHAT("black")
    self.inky_display.set_border(inky_display.WHITE)

    self.current_row = 0
    self.max_rows = num_rows
    self.row_width = inky_display.WIDTH
    self.row_height = int(inky_display.HEIGHT / num_rows)
    self.img = None
    self.font = ImageFont.truetype(FredokaOne, self.row_height - 2)
    self.reset()

  def reset():
    self.current_row = 0
    self.img = Image.new("P", (self.inky_display.WIDTH, self.inky_display.HEIGHT))

  def write_row(self, message):
    if (self.current_row < self.max_rows):
      draw = ImageDraw.Draw(img)
      draw.text((1, 1 + self.row_height * self.current_row), message, inky_display.BLACK, self.font)
      self.current_row += 1

  def update():
    self.inky_display.set_image(self.img)
    self.inky_display.show()

