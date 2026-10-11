from PySide6.QtWidgets import QSpinBox

class BoundedSpinBox(QSpinBox):
    def __init__(self, minv: int, maxv: int, value: int):
        super().__init__()
        self.setRange(minv, maxv)
        self.setValue(value)