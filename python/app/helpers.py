from sgtk.platform.qt import QtCore, QtGui

class MessageBox(QtGui.QMessageBox):
    def __init__(self, parent, message):
        super(MessageBox, self).__init__(parent)

        self.setText(message)
        self.show()

class ColumnNames():
    def __init__(self):
        self._nice_names = ['Flipbook Name', 'Thumbnail', 'Range', 'Comment']
        self._prog_names = ['name', 'thumb', 'range', 'comment']
    def index_name(self, name):
        return self._prog_names.index(name)
    def name_to_nice(self, name):
        return self._nice_names[self._prog_names.index(name)]
    def get_nice_names(self):
        return self._nice_names