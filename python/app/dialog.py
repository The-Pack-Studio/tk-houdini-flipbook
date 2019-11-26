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
import shutil
import subprocess
import threading

# import pyseq
sys.path.append(r'\\server01\shared\sharedPython\modules\pyseq')
import pyseq

class MessageBox(QtGui.QMessageBox):
    def __init__(self, parent, message):
        super(MessageBox, self).__init__(parent)

        self.setText(message)
        self.show()

class ColumnNames():
    def __init__(self):
        self.nice_names = ['Flipbook Name', 'Thumbnail', 'Range', 'Comment']
        self.prog_names = ['name', 'thumb', 'range', 'comment']
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

        template_name = self._app.get_setting("output_flipbook_template")
        self._output_template = self._app.get_template_by_name(template_name)
        
        self.column_names = ColumnNames()
        self.setup_ui()
        self._fill_treewidget()

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

        #Comment
        comment_bar = QtGui.QHBoxLayout()
        self.comment_line = QtGui.QLineEdit()

        comment_bar.addWidget(self.comment_line)

        comment_box = QtGui.QGroupBox('Comment')
        comment_box.setLayout(comment_bar)

        name_comment_layout = QtGui.QHBoxLayout()
        name_comment_layout.addWidget(name_box)
        name_comment_layout.addWidget(comment_box)

        #Create button
        create_but = QtGui.QPushButton('Create Flipbook')
        create_but.setDefault(True)
        create_but.clicked.connect(self._create_flipbook)

        #Create Name Button Larout
        name_but_layout = QtGui.QHBoxLayout()
        name_but_layout.addLayout(name_comment_layout)
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
        if isinstance(item, TreeItem):
            self.name_line.setText(item.get_cache_name())
        else:
            self.name_line.setText(item.text(0))

    def _del_flipbooks(self):
        for item in self._tree_find_selected():
            dir_path = os.path.dirname(item.get_path())

            shutil.rmtree(dir_path)

        self._fill_treewidget()

    def _load_flipbooks(self):
        item_paths = []
        for item in self._tree_find_selected():
            item_paths.append(item.get_path())

        item_paths = ' '.join(item_paths)

        if item_paths:
            system = sys.platform

            # run the app
            if system == "linux2":
                command = '%s/bin/mplay-bin %s -g' % (hou.getenv('HFS'), item_paths)
                subprocess.call(command.split(' '))
            elif system == 'win32':
                command = '%s/bin/mplay.exe %s -g' % (hou.getenv('HFS'), item_paths)
                subprocess.call(command.split(' '), shell=True)
            else:
                msg = "Platform '%s' is not supported." % (system,)
                self._app.log_error(msg)
                hou.ui.displayMessage(msg)
                return

    def _copy_flipbook_clipboard(self):
        paths = []
        for item in self._tree_find_selected():
            paths.append('%s %s' % (item.get_path().replace('$F4', '####'), item.get_range()))

        hou.ui.copyTextToClipboard('\n'.join(paths))

    def _publish_flipbook(self):
        for item in self._tree_find_selected():
            file_path = item.get_path()
            name = item.get_cache_name()
            version_number = item.get_version()

            sgtk.util.register_publish(
                self._app.sgtk,
                self._app.context,
                file_path, name,
                version_number, 
                comment = 'To be Implemented!',
                published_file_type = 'Playblast')

    def _create_flipbook(self):
        # Ranges
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

        # Resolution
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

        # Name
        flip_name = self.name_line.text()
        if flip_name == '':
            flip_name = self.name_line.placeholderText()

        if set('[~!@#$%^&*() +{}":;\']+$.').intersection(flip_name):
            MessageBox(self, 'Incorrect flipbook name!')
            return

        # set settings
        sceneViewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if sceneViewer:
            settings = sceneViewer.flipbookSettings().stash()
            settings.sessionLabel('flipbook_%s' % os.getpid())
            settings.overrideGamma(True)
            settings.beautyPassOnly(True)
            settings.frameRange((int(range_begin), int(rangeEnd)))

            if res_x and res_y:
                settings.useResolution(True)
                settings.resolution((int(res_x), int(res_y)))
            else:
                settings.useResolution(False)

            # Check if there are already flipbook versions in tree
            ver = 1
            for top_level in range(self.tree_widget.topLevelItemCount()):
                top_level_widget = self.tree_widget.topLevelItem(top_level)
                if top_level_widget.text(0) == flip_name:
                    tree_item = top_level_widget.child(top_level_widget.childCount() - 1)
                    ver = tree_item.get_version() + 1

            # create path
            # get relevant fields from the current file path
            work_file_fields = self._get_hipfile_fields()

            fields = { 
                "name": work_file_fields.get("name", None),
                "node": flip_name,
                "version": ver,
                "SEQ": "FORMAT: $F"
                }

            fields.update(self._app.context.as_template_fields(self._output_template))

            path_flipbook = self._output_template.apply_fields(fields)
            path_flipbook = path_flipbook.replace(os.sep, '/')
            settings.output(path_flipbook)

            # Create dir to reserve slot
            os.makedirs(os.path.dirname(path_flipbook))

            if self.comment_line.text() != "":
                text_file = open(os.path.join(os.path.dirname(path_flipbook), "comment.txt"), "w")
                text_file.write(self.comment_line.text())
                text_file.close()

            self._fill_treewidget()

            # Create flipbook
            sceneViewer.flipbook(sceneViewer.curViewport(), settings)

    def _fill_treewidget(self):
        self.tree_widget.invisibleRootItem().takeChildren()

        # get relevant fields from the current file path
        work_file_fields = self._get_hipfile_fields()
        fields = { 
            "name": work_file_fields.get("name", None),
            "SEQ": "FORMAT: $F"
            }

        fields.update(self._app.context.as_template_fields(self._output_template))

        flipbooks = self._app.sgtk.abstract_paths_from_template(self._output_template, fields)
        flipbooks.sort()
        for flip in flipbooks:
            # get flipbook name
            flip_fields = self._output_template.get_fields(flip)

            if 'node' in flip_fields:
                name = flip_fields['node']
                flip_top_level_item = None
                
                # check if the flipbook name is already in tree
                for top_level in range(self.tree_widget.topLevelItemCount()):
                    top_level_item = self.tree_widget.topLevelItem(top_level)

                    if top_level_item.text(0) == name:
                        flip_top_level_item = top_level_item
                        break
                
                # create new top level item or add version
                if not flip_top_level_item:
                    flip_top_level_item = QtGui.QTreeWidgetItem([name, '', '', ''])
                    self.tree_widget.addTopLevelItem(flip_top_level_item)
                    flip_top_level_item.setExpanded(True)

                TreeItem(flip_top_level_item, self.column_names, flip, flip_fields)
            else:
                print 'Could not find name for %s' % flip

    ###################################################################################################
    # Extra Functions

    def _tree_find_selected(self):
        items = []
        for top_level in range(self.tree_widget.topLevelItemCount()):
            top_level_widget = self.tree_widget.topLevelItem(top_level)
            top_level_widget.setSelected(False)

            for index in range(top_level_widget.childCount()):
                if top_level_widget.child(index).isSelected():
                    items.append(top_level_widget.child(index))
                    top_level_widget.child(index).setSelected(False)
        return items

    # extract fields from current Houdini file using the workfile template
    def _get_hipfile_fields(self):
        current_file_path = hou.hipFile.path()

        work_fields = {}
        work_file_template = self._app.get_template("work_file_template")
        if (work_file_template and 
            work_file_template.validate(current_file_path)):
            work_fields = work_file_template.get_fields(current_file_path)

        return work_fields

    ###################################################################################################
    # navigation

    def navigate_to_context(self, context):
        """
        Navigates to the given context.

        :param context: The context to navigate to.
        """
        self._fill_treewidget()

class TreeItem(QtGui.QTreeWidgetItem):
    def __init__(self, parent, column_names, path, fields):
        super(TreeItem, self).__init__(parent)
        self._column_names = column_names
        self._path = path
        self._fields = fields
        self._thumb_path = os.path.join(os.path.dirname(self._path), 'thumb.jpg')

        sequences = pyseq.get_sequences(path.replace('$F4', '*'))
        self._sequence = None
        if sequences:
            self._sequence = sequences[0]

        # set version
        self.setText(self._column_names.index_name('name'), 'v%s' % (str(self._fields['version']).zfill(3)))
        
        # set range
        cache_range = 'Invalid Sequence Object!'
        if self._sequence:
            if self._sequence.missing():
                cache_range = '[%s-%s], missing %s' % (self._sequenceeq.format('%s'), self._sequence.format('%e'), self._sequence.format('%m'))
            else:
                cache_range = self._sequence.format('%R')
        self.setText(self._column_names.index_name('range'), cache_range)

        # set comment
        comment_path = os.path.join(os.path.dirname(self._path), 'comment.txt')
        if os.path.exists(comment_path):
            text_file = open(comment_path, "r")
            text = text_file.read()
            text_file.close()

            self.setText(self._column_names.index_name('comment'), text)

        # set thumbnail
        if self._sequence:
            if os.path.isfile(self._thumb_path):
                self._set_thumbnail()
            else:
                # self.thread = threading.Thread(target=self._create_thumbnail)
                # self.thread.start()

                self._create_thumbnail()
                self._set_thumbnail()

    ###################################################################################################
    # Private Functions

    def _create_thumbnail(self):
        seq_thumb_path = self._sequence[self._sequence.length() / 2].path

        system = sys.platform

        # run the app
        if system == "linux2":
            command = 'ffmpeg -i %s -vf scale=80:-1 %s' % (seq_thumb_path, self._thumb_path)
            subprocess.call(command.split(' '))
        elif system == 'win32':
            ffmpeg_exe = r'\\server01\shared\Dev\Donat\NozMovTools\ffmpeg-4.2.1-win64-static\bin\ffmpeg.exe'
            command = '%s -i %s -vf scale=80:-1 %s' % (ffmpeg_exe, seq_thumb_path, self._thumb_path)
            subprocess.call(command.split(' '), shell=True)
        else:
            msg = "Platform '%s' is not supported." % (system,)
            self._app.log_error(msg)
            hou.ui.displayMessage(msg)
            return

    def _set_thumbnail(self):
        image = QtGui.QPixmap(self._thumb_path)
        self.setSizeHint(self._column_names.index_name('thumb'), image.size())
        
        self.thumbnail = QtGui.QLabel()
        self.thumbnail.setAlignment(QtCore.Qt.AlignHCenter)
        self.thumbnail.setPixmap(image)
        self.treeWidget().setItemWidget(self, self._column_names.index_name('thumb'), self.thumbnail)

        #Force refresh after all the data is added
        self.treeWidget().header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    ###################################################################################################
    # Get Attributes

    def get_cache_name(self):
        return self._fields['node']

    def get_range(self):
        return '%s-%s' % (self._sequence.start(), self._sequence.end())

    def get_path(self):
        return self._path

    def get_version(self):
        return self._fields['version']