# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk

from sgtk.platform.qt import QtCore, QtGui

import os
import hou
import sys
import pyseq
import subprocess
import glob
import threading

# import pyseq
sys.path.append(r'\\server01\shared\sharedPython\modules\pyseq')

class MessageBox(QtGui.QMessageBox):
    def __init__(self, parent, message):
        super(MessageBox, self).__init__(parent)

        self.setText(message)
        self.show()

class ColumnNames():
    def __init__(self):
        self.nice_names = ['Flipbook Name', 'Thumbnail', 'Range']
        self.prog_names = ['name', 'thumb', 'range']
    def index_name(self, name):
        return self.prog_names.index(name)
    def name_to_nice(self, name):
        return self.nice_names[self.prog_names.index(name)]

class AppDialog(QtGui.QWidget):
    @property
    def hide_tk_title_bar(self):
        """
        Tell the system to not show the std toolbar
        """
        return True

    def __init__(self, parent=None):
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self, parent)

        # most of the useful accessors are available through the Application class instance
        # it is often handy to keep a reference to this. You can get it via the following method:
        self._app = sgtk.platform.current_bundle()

        self._template_name = self._app.get_setting("output_flipbook_template")
        
        self.column_names = ColumnNames()
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle('Flipbook')

        #Top lout
        upper_bar = QtGui.QHBoxLayout()
        title_lab = QtGui.QLabel('Flipbook versioning system')
        refresh_but = QtGui.QPushButton()
        refresh_but.setFixedSize(25, 25)
        icon = QtGui.QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "refresh.png")))
        refresh_but.setIcon(icon)
        refresh_but.clicked.connect(self._fill_treewidget)

        upper_bar.addWidget(title_lab)
        upper_bar.addWidget(refresh_but)

        #Tree layout
        self.tree_widget = QtGui.QTreeWidget()
        self.tree_widget.itemClicked.connect(self._set_flipbook_name_sel)

        self.tree_widget.setColumnCount(len(self.column_names.nice_names))
        self.tree_widget.setHeaderLabels(self.column_names.nice_names)
        self.tree_widget.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree_widget.header().setSectionsMovable(False)
        self.tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)
        self.tree_widget.itemDoubleClicked.connect(self._load_flipbooks)

        # self._fill_treewidget()

        tree_bar = QtGui.QHBoxLayout()
        del_but = QtGui.QPushButton('Delete Flipbook(s)')
        del_but.clicked.connect(self._del_flipbooks)
        load_but = QtGui.QPushButton('Load Flipbook(s) in Mplay')
        load_but.clicked.connect(self._load_flipbooks)
        send_but = QtGui.QPushButton('Copy Flipbook(s) to Clipboard')
        send_but.clicked.connect(self._copy_flipbook_clipboard)
        pub_but = QtGui.QPushButton('Publish Flipbook')
        pub_but.clicked.connect(self._publish_flipbook)

        tree_bar.addWidget(del_but)
        tree_bar.addWidget(load_but)
        tree_bar.addWidget(send_but)
        tree_bar.addWidget(pub_but)

        #New flipbook layout
        new_flipbook_bar = QtGui.QVBoxLayout()
        title_label = QtGui.QLabel('New Flipbook Settings')

        #Range
        range_bar = QtGui.QHBoxLayout()
        self.start_line = QtGui.QLineEdit()
        self.start_line.setPlaceholderText('$FSTART')
        self.end_line = QtGui.QLineEdit()
        self.end_line.setPlaceholderText('$FEND')

        range_bar.addWidget(self.start_line)
        range_bar.addWidget(self.end_line)

        range_box = QtGui.QGroupBox('Range')
        range_box.setLayout(range_bar)

        #Res
        res_bar = QtGui.QHBoxLayout()
        self.res_auto = QtGui.QCheckBox('Auto')
        self.res_auto.setChecked(True)
        self.res_auto.stateChanged.connect(self._auto_checkbox_changed)
        self.res_w = QtGui.QLineEdit()
        self.res_w.setPlaceholderText('1280')
        self.res_w.setEnabled(False)
        self.res_h = QtGui.QLineEdit()
        self.res_h.setPlaceholderText('720')
        self.res_h.setEnabled(False)

        res_bar.addWidget(self.res_auto)
        res_bar.addWidget(self.res_w)
        res_bar.addWidget(self.res_h)

        res_box = QtGui.QGroupBox('Resolution')
        res_box.setLayout(res_bar)

        #Create Range Res Larout
        groupbox_layout = QtGui.QHBoxLayout()
        groupbox_layout.addWidget(range_box)
        groupbox_layout.addWidget(res_box)

        #Name
        name_bar = QtGui.QHBoxLayout()
        self.name_line = QtGui.QLineEdit()
        self.name_line.setPlaceholderText('flipbook')

        name_bar.addWidget(self.name_line)

        name_box = QtGui.QGroupBox('Flipbook Name')
        name_box.setLayout(name_bar)

        #Create button
        create_but = QtGui.QPushButton('Create Flipbook')
        create_but.setDefault(True)
        create_but.clicked.connect(self._create_flipbook)

        #Create Name Button Larout
        name_but_layout = QtGui.QHBoxLayout()
        name_but_layout.addWidget(name_box)
        name_but_layout.addWidget(create_but)

        new_flipbook_bar.addWidget(title_label)
        new_flipbook_bar.addLayout(groupbox_layout)
        new_flipbook_bar.addLayout(name_but_layout)

        #Create final layout
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().addLayout(upper_bar)
        self.layout().addWidget(self.tree_widget)
        self.layout().addLayout(tree_bar)
        self.layout().addLayout(new_flipbook_bar)

    ###################################################################################################
    # UI callbacks

    def _auto_checkbox_changed(self, state):
        self.res_w.setEnabled(not state)
        self.res_h.setEnabled(not state)

    def _set_flipbook_name_sel(self, item, column):
        if isinstance(item, treeItem):
            self.name_line.setText(item.get_cache_name())
        else:
            self.name_line.setText(item.text(0))

    def _del_flipbooks(self):
        for item in self._tree_find_selected():
            dir_path = item.get_dir()

            command = 'rm -rf %s' % (dir_path)
            subprocess.call(command.split(' '))

            cache_name = os.path.basename(dir_path)
            path_jpg = os.path.join(self.flip_location.get_thumbnail_path(), '%s.jpg' % cache_name)

            command = 'rm -f %s' % (path_jpg)
            subprocess.call(command.split(' '))

        self._fill_treewidget()

    def _load_flipbooks(self):
        item_paths = []
        for item in self._tree_find_selected():
            item_paths.append(item.get_mplay_path())

        item_paths = ' '.join(item_paths)

        if item_paths:
            command = '%s/bin/mplay-bin %s -g' % (hou.getenv('HFS'), item_paths)
            subprocess.call(command.split(' '))

    def _copy_flipbook_clipboard(self):
        paths = []
        for item in self._tree_find_selected():
            paths.append('%s %s' % (item.get_mplay_path().replace('$F4', '####'), item.get_range()))

        hou.ui.copyTextToClipboard('\n'.join(paths))

    def _publish_flipbook(self):
        print 'Publish Flipbook not implemented yet!'

    def _create_flipbook(self):
        #Ranges
        range_begin = self.start_line.text()
        if range_begin == '':
            range_begin = self.start_line.placeholderText()

        rangeEnd = self.end_line.text()
        if rangeEnd == '':
            rangeEnd = self.end_line.placeholderText()

        if not range_begin.isdigit():
            range_begin = hou.expandString(range_begin)
        if not rangeEnd.isdigit():
            rangeEnd = hou.expandString(rangeEnd)

        if not range_begin.isdigit() or not rangeEnd.isdigit() or int(range_begin) < 1 or int(rangeEnd) < 1 or int(range_begin) > int(rangeEnd):
            MessageBox(self, 'Incorrect flipbook ranges!')
            return

        #Resolution
        if not self.res_auto.checkState():
            res_x = self.res_w.text()
            if res_x == '':
                res_x = self.res_w.placeholderText()

            res_y = self.res_h.text()
            if res_y == '':
                res_y = self.res_h.placeholderText()

            if not res_x.isdigit() or not res_y.isdigit() or int(res_x) < 10 or int(res_y) < 10:
                MessageBox(self, 'Incorrect flipbook resolution!')
                return
        else:
            res_x = None
            res_y = None

        #Name
        flip_name = self.name_line.text()
        if flip_name == '':
            flip_name = self.name_line.placeholderText()

        if set('[~!@#$%^&*() +{}":;\']+$.').intersection(flip_name):
            MessageBox(self, 'Incorrect flipbook name!')
            return

        sceneViewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if sceneViewer:
            settings = sceneViewer.flipbookSettings().stash()
            settings.sessionLabel('beflipbook_%s' % os.getpid())
            settings.overrideGamma(True)
            settings.beautyPassOnly(True)
            settings.frameRange((int(range_begin), int(rangeEnd)))

            if res_x and res_y:
                settings.useResolution(True)
                settings.resolution((int(res_x), int(res_y)))
            else:
                settings.useResolution(False)

            #Check if there are already flipbook versions in tree
            ver = 1
            for top_level in range(self.tree_widget.topLevelItemCount()):
                topLevelWidget = self.tree_widget.topLevelItem(top_level)
                if topLevelWidget.text(0) == flip_name:
                    ver = int(topLevelWidget.child(topLevelWidget.childCount() -1).text(0)[1:]) + 1

            path_flipbook = beshared.createFullPath(self.flip_location.get_flipbook_path(), flip_name, ver, 'exr', True)
            settings.output(path_flipbook)

            #Create dir to reserve slot
            command = 'mkdir %s' % (os.path.dirname(path_flipbook))
            subprocess.call(command.split(' '))

            self._fill_treewidget()

            #Create flipbook
            sceneViewer.flipbook(sceneViewer.curViewport(), settings)

    def _fill_treewidget(self):
        self.tree_widget.invisibleRootItem().takeChildren()

        print 'Fill Treewidget, to be implemented'

    ###################################################################################################
    # Extra Functions

    def _tree_find_selected(self):
        items = []
        for top_level in range(self.tree_widget.topLevelItemCount()):
            topLevelWidget = self.tree_widget.topLevelItem(top_level)
            topLevelWidget.setSelected(False)

            for index in range(topLevelWidget.childCount()):
                if topLevelWidget.child(index).isSelected():
                    items.append(topLevelWidget.child(index))
                    topLevelWidget.child(index).setSelected(False)
        return items

    ###################################################################################################
    # navigation

    def navigate_to_context(self, context):
        """
        Navigates to the given context.

        :param context: The context to navigate to.
        """
        self._fill_treewidget()

class treeItem(QtGui.QTreeWidgetItem):
    def __init__(self, parent, column_names, parent_seq, panel):
        super(treeItem, self).__init__(parent)
        self.panel = panel
        self.column_names = column_names
        self.dir_path = parent_seq.path
        self.sequence = beshared.getSequence(self.dir_path, parent_seq.name)

        try:
            self.setText(self.column_names.index_name('name'), 'v%s' % (parent_seq[-3:]))
        except:
            print 'Could not get version from %s' % (parent_seq)

        cache_range = beshared.setRange(self.sequence)
        self.setText(self.column_names.index_name('range'), cache_range)

        self.thumbnail = QtGui.QLabel()
        self.thumbnail.setAlignment(QtCore.Qt.AlignHCenter)

        self.thread = threading.Thread(target=self._create_thumbnail, args=(False,))
        self.thread .start()
        self.treeWidget().setItemWidget(self, self.column_names.index_name('thumb'), self.thumbnail)

    ###################################################################################################
    # Private Functions

    def _create_thumbnail(self, force):
        if self.sequence:
            in_thumb_path = self.sequence[self.sequence.length() / 2].path
            filename = '%s.jpg' % os.path.basename(in_thumb_path).split('.')[0]

            thumb_dir = self.panel.flip_location.get_thumbnail_path()
            out_thumb_path = os.path.join(thumb_dir, filename)

            if not os.path.isdir(thumb_dir):
                os.mkdir(thumb_dir)
            if not os.path.isfile(out_thumb_path):
                command = 'ffmpeg -i %s -vf scale=80:-1 %s' % (in_thumb_path, out_thumb_path)
                subprocess.call(command.split(' '))

            image = QtGui.QPixmap(out_thumb_path)
            self.setSizeHint(self.column_names.index_name('thumb'), image.size())
            self.thumbnail.setPixmap(image)

            #Force refresh after all the data is added
            self.treeWidget().header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    ###################################################################################################
    # Get Attributes

    def get_cache_name(self):
        return self.parent().text(0)

    def get_range(self):
        return '%s-%s' % (self.sequence.start(), self.sequence.end())

    def get_mplay_path(self):
        try:
            if self.sequence.length() == 1:
                split_name = self.sequence.format('%h%t').split('.')
                return os.path.join(os.path.dirname(self.sequence.path()), '%s.$F4.%s' % (split_name[0], split_name[2]))
            else:
                return os.path.join(os.path.dirname(self.sequence.path()), '%s$F4%s' % (self.sequence.format('%h'), self.sequence.format('%t')))
        except:
            return ''

    def get_dir(self):
        return self.dir_path
