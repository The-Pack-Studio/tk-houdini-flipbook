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

import pyseq
import json

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
        
        self._ffmpeg_exec = self._app.get_setting("ffmpeg_executable")
        if self._ffmpeg_exec == '' or not os.path.exists(self._ffmpeg_exec):
            self._app.log_error('FFmpeg path not set correctly in config!')

        # retrieve root path
        work_file_fields = self._get_hipfile_fields()
        fields = { 
            "name": work_file_fields.get("name", None),
            "SEQ": "FORMAT: $F"
            }

        fields.update(self._app.context.as_template_fields(self._output_template))
        root_path = self._output_template.parent.parent.apply_fields(fields)

        self._json_manager = JsonManager(root_path, fields['name'])
        self._column_names = ColumnNames()
        self._setup_ui()
        self._fill_treewidget()

    ###################################################################################################
    # UI callbacks

    def _auto_checkbox_changed(self, state):
        self._res_w.setEnabled(not state)
        self._res_h.setEnabled(not state)

    def _set_flipbook_name_sel(self, item, column):
        if isinstance(item, TreeItem):
            self._name_line.setText(item.get_fields()['node'])
        else:
            self._name_line.setText(item.text(0))

    def _del_flipbooks(self):
        for item in self._tree_find_selected():
            item.remove_cache()

        self._json_manager.remove_item(item.get_fields()['json_name'])
        self._refresh_treewidget()

    def _item_double_clicked(self, item, column):
        if isinstance(item, TreeItem):
            comment_index = self._column_names.index_name('comment')
            if column != comment_index:
                self._load_flipbooks()
            else:
                current_comment = item.text(comment_index)

                text, ok = QtGui.QInputDialog().getText(self, 'Set new comment', 'Comment:', text=current_comment)
                
                if text and ok:
                    item.set_comment(text)
                    fields = item.get_fields()
                    self._json_manager.write_item_data(fields['json_name'], fields['data'])

    def _item_expanded(self, item):
        for index in range(item.childCount()):
            item.child(index).load_thumbnail()

        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)

    def _load_flipbooks(self):
        item_paths = []
        for item in self._tree_find_selected():
            item_paths.append(item.get_path())

        item_paths = ' '.join(item_paths)

        if item_paths:
            process = QtCore.QProcess(self)

            # run the app
            arguments = '%s -g' % (item_paths)

            system = sys.platform
            if system == "linux2":
                program = '%s/bin/mplay-bin' % hou.getenv('HFS')
            elif system == 'win32':
                program = '%s/bin/mplay.exe' % hou.getenv('HFS')
            else:
                msg = "Platform '%s' is not supported." % (system,)
                self._app.log_error(msg)
                hou.ui.displayMessage(msg)
                return

            process.startDetached(program, arguments.split(' '))
            process.close()

    def _copy_flipbook_clipboard(self):
        paths = []
        for item in self._tree_find_selected():
            paths.append(item.get_path().replace('$F4', '####'))

        hou.ui.copyTextToClipboard('\n'.join(paths))

    def _publish_flipbook(self):
        for item in self._tree_find_selected():
            file_path = item.get_path()
            name = item.get_fields()['node']
            version_number = item.get_fields()['version']
            comment = item.text(self._column_names.index_name('comment'))

            sgtk.util.register_publish(
                self._app.sgtk,
                self._app.context,
                file_path, name,
                version_number, 
                comment = comment,
                published_file_type = 'Playblast')

    def _create_flipbook(self):
        # Ranges
        range_begin = self._start_line.text()
        if range_begin == '':
            range_begin = self._start_line.placeholderText()

        range_end = self._end_line.text()
        if range_end == '':
            range_end = self._end_line.placeholderText()

        if not range_begin.isdigit():
            range_begin = hou.text.expandString(range_begin)
        if not range_end.isdigit():
            range_end = hou.text.expandString(range_end)

        if not range_begin.isdigit() or not range_end.isdigit() or int(range_begin) < 1 or int(range_end) < 1 or int(range_begin) > int(range_end):
            MessageBox(self, 'Incorrect flipbook ranges!')
            return

        # Resolution
        if not self._res_auto.checkState():
            res_x = self._res_w.text()
            if res_x == '':
                res_x = self._res_w.placeholderText()

            res_y = self._res_h.text()
            if res_y == '':
                res_y = self._res_h.placeholderText()

            if not res_x.isdigit() or not res_y.isdigit() or int(res_x) < 10 or int(res_y) < 10:
                MessageBox(self, 'Incorrect flipbook resolution!')
                return
        else:
            res_x = None
            res_y = None

        # Name
        flip_name = self._name_line.text()
        if flip_name == '':
            flip_name = self._name_line.placeholderText()

        if set('[~!@#$%^&*() +{}":;\']+$.').intersection(flip_name):
            MessageBox(self, 'Incorrect flipbook name!')
            return

        # set settings
        sceneViewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if sceneViewer:
            settings = sceneViewer.flipbookSettings().stash()
            settings.sessionLabel('flipbook_%s' % os.getpid())
            settings.beautyPassOnly(not self._beauty_toggle.checkState())
            settings.frameRange((int(range_begin), int(range_end)))

            if res_x and res_y:
                settings.useResolution(True)
                settings.resolution((int(res_x), int(res_y)))
            else:
                settings.useResolution(False)

            # Check if there are already flipbook versions in tree
            ver = 1
            for top_level in range(self._tree_widget.topLevelItemCount()):
                top_level_widget = self._tree_widget.topLevelItem(top_level)
                if top_level_widget.text(0) == flip_name:
                    tree_item = top_level_widget.child(top_level_widget.childCount() - 1)
                    ver = tree_item.get_fields()['version'] + 1

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

            # create comment
            if self._comment_line.text() != "":
                self._json_manager.write_item_data(os.path.basename(path_flipbook).split('.')[0], {'comment': self._comment_line.text()})
                self._comment_line.setText("")
            
            self._refresh_treewidget()

            # Create flipbook
            sceneViewer.flipbook(sceneViewer.curViewport(), settings)

    def _refresh_treewidget(self):
        # Get all items in tree
        items = {}
        for top_level in range(self._tree_widget.topLevelItemCount()):
            top_level_widget = self._tree_widget.topLevelItem(top_level)

            for index in range(top_level_widget.childCount()):
                child = top_level_widget.child(index)
                items[child.get_path()] = {'item': child, 'checked': False}

        # get relevant fields from the current file path
        work_file_fields = self._get_hipfile_fields()
        fields = { 
            "name": work_file_fields.get("name", None),
            "SEQ": "FORMAT: $F"
            }

        fields.update(self._app.context.as_template_fields(self._output_template))

        flipbooks = self._app.sgtk.abstract_paths_from_template(self._output_template, fields)
        flipbooks.sort()

        # Add new flipbooks
        for flip in flipbooks:
            if flip not in items.keys():
                self._add_path_to_tree(flip)
            else:
                items[flip]['checked'] = True
        
        # Check for any missing flipbooks
        for key, value in items.iteritems():
            if not value['checked']:
                parent = value['item'].parent()
                parent.removeChild(value['item'])

                if not parent.childCount():
                    index = self._tree_widget.indexOfTopLevelItem(parent)
                    self._tree_widget.takeTopLevelItem(index)

        # Refresh items that are visible
        for top_level in range(self._tree_widget.topLevelItemCount()):
            top_level_item = self._tree_widget.topLevelItem(top_level)
            if top_level_item.isExpanded():
                for index in range(top_level_item.childCount()):
                    top_level_item.child(index).refresh()

    def _fill_treewidget(self):
        self._tree_widget.invisibleRootItem().takeChildren()

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
            self._add_path_to_tree(flip)

        for index in range(self._tree_widget.topLevelItemCount()):
            self._tree_widget.topLevelItem(index).setExpanded(False)

    ###################################################################################################
    # Private Functions

    def get_ffmpeg_exec(self):
        return self._ffmpeg_exec

    def _add_path_to_tree(self, path):
        fields = self._output_template.get_fields(path)

        if 'node' in fields:
            name = fields['node']

            flip_top_level_item = None
            
            # check if the flipbook name is already in tree
            for top_level in range(self._tree_widget.topLevelItemCount()):
                top_level_item = self._tree_widget.topLevelItem(top_level)

                if top_level_item.text(0) == name:
                    flip_top_level_item = top_level_item
                    break
            
            # create new top level item or add version
            if not flip_top_level_item:
                flip_top_level_item = QtGui.QTreeWidgetItem([name, '', '', ''])
                self._tree_widget.addTopLevelItem(flip_top_level_item)
                flip_top_level_item.setExpanded(True)

            # get json data
            name_version = os.path.basename(path).split('.')[0]
            fields['data'] = self._json_manager.get_item_data(name_version)
            fields['json_name'] = name_version

            flip_top_level_item.addChild(TreeItem(self._column_names, path, fields, self))
        else:
            self._app.log_error('Could not find name for %s' % path)

    def _setup_ui(self):
        self.setWindowTitle('Flipbook')

        #Top lout
        upper_bar = QtGui.QHBoxLayout()
        title_lab = QtGui.QLabel('Flipbook versioning system')
        refresh_but = QtGui.QPushButton()
        refresh_but.setFixedSize(25, 25)
        icon = QtGui.QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "refresh.png")))
        refresh_but.setIcon(icon)
        refresh_but.clicked.connect(self._refresh_treewidget)

        upper_bar.addWidget(title_lab)
        upper_bar.addWidget(refresh_but)

        #Tree layout
        self._tree_widget = QtGui.QTreeWidget()
        self._tree_widget.itemClicked.connect(self._set_flipbook_name_sel)

        self._tree_widget.setColumnCount(len(self._column_names.get_nice_names()))
        self._tree_widget.setHeaderLabels(self._column_names.get_nice_names())
        self._tree_widget.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree_widget.header().setSectionsMovable(False)
        self._tree_widget.header().resizeSections(QtGui.QHeaderView.ResizeToContents)
        self._tree_widget.itemDoubleClicked.connect(self._item_double_clicked)
        self._tree_widget.itemExpanded.connect(self._item_expanded)

        tree_bar = QtGui.QHBoxLayout()
        del_but = QtGui.QPushButton('Delete')
        del_but.clicked.connect(self._del_flipbooks)
        load_but = QtGui.QPushButton('Load in Mplay')
        load_but.clicked.connect(self._load_flipbooks)
        send_but = QtGui.QPushButton('Copy Path')
        send_but.clicked.connect(self._copy_flipbook_clipboard)
        pub_but = QtGui.QPushButton('Publish')
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
        self._start_line = QtGui.QLineEdit()
        self._start_line.setPlaceholderText('$FSTART')
        self._end_line = QtGui.QLineEdit()
        self._end_line.setPlaceholderText('$FEND')

        range_bar.addWidget(self._start_line)
        range_bar.addWidget(self._end_line)

        range_box = QtGui.QGroupBox('Range')
        range_box.setLayout(range_bar)

        #Res
        res_bar = QtGui.QHBoxLayout()
        self._res_auto = QtGui.QCheckBox('Auto')
        self._res_auto.setChecked(True)
        self._res_auto.stateChanged.connect(self._auto_checkbox_changed)
        self._res_w = QtGui.QLineEdit()
        self._res_w.setPlaceholderText('1280')
        self._res_w.setEnabled(False)
        self._res_h = QtGui.QLineEdit()
        self._res_h.setPlaceholderText('720')
        self._res_h.setEnabled(False)

        res_bar.addWidget(self._res_auto)
        res_bar.addWidget(self._res_w)
        res_bar.addWidget(self._res_h)

        res_box = QtGui.QGroupBox('Resolution')
        res_box.setLayout(res_bar)

        #Create Range Res Larout
        groupbox_layout = QtGui.QHBoxLayout()
        groupbox_layout.addWidget(range_box)
        groupbox_layout.addWidget(res_box)

        #Name
        name_bar = QtGui.QHBoxLayout()
        self._name_line = QtGui.QLineEdit()
        self._name_line.setPlaceholderText('flipbook')

        name_bar.addWidget(self._name_line)

        name_box = QtGui.QGroupBox('Flipbook Name')
        name_box.setLayout(name_bar)

        #Comment
        comment_bar = QtGui.QHBoxLayout()
        self._comment_line = QtGui.QLineEdit()
        self._comment_line.returnPressed.connect(self._create_flipbook)

        comment_bar.addWidget(self._comment_line)

        comment_box = QtGui.QGroupBox('Comment')
        comment_box.setLayout(comment_bar)

        name_comment_layout = QtGui.QHBoxLayout()
        name_comment_layout.addWidget(name_box)
        name_comment_layout.addWidget(comment_box)

        #Create button
        create_bar = QtGui.QVBoxLayout()
        self._beauty_toggle = QtGui.QCheckBox('Render Bg')
        self._beauty_toggle.setCheckState(QtCore.Qt.CheckState.Unchecked)

        create_but = QtGui.QPushButton('Create')
        create_but.setDefault(True)
        create_but.clicked.connect(self._create_flipbook)

        create_bar.addWidget(self._beauty_toggle)
        create_bar.addWidget(create_but)

        #Create Name Button Larout
        name_but_layout = QtGui.QHBoxLayout()
        name_but_layout.addLayout(name_comment_layout)
        name_but_layout.addLayout(create_bar)

        new_flipbook_bar.addWidget(title_label)
        new_flipbook_bar.addLayout(groupbox_layout)
        new_flipbook_bar.addLayout(name_but_layout)

        #Create final layout
        self.setLayout(QtGui.QVBoxLayout())
        self.layout().addLayout(upper_bar)
        self.layout().addWidget(self._tree_widget)
        self.layout().addLayout(tree_bar)
        self.layout().addLayout(new_flipbook_bar)

    def _tree_find_selected(self):
        items = []
        for top_level in range(self._tree_widget.topLevelItemCount()):
            top_level_widget = self._tree_widget.topLevelItem(top_level)
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
    def __init__(self, column_names, path, fields, panel):
        super(TreeItem, self).__init__()
        self._column_names = column_names
        self._path = path
        self._fields = fields
        self._sequence = None

        dir_path = os.path.dirname(os.path.dirname(self._path))
        thumb_name = '%s.jpg' % os.path.basename(self._path).split('.')[0]
        self._thumb_path = os.path.join(dir_path, 'flipbook_panel', thumb_name)
        self._panel = panel

        # set version
        self.setText(self._column_names.index_name('name'), 'v%s' % (str(self._fields['version']).zfill(3)))

        # set comment
        if 'comment' in self._fields['data'].keys():
            self.setText(self._column_names.index_name('comment'), self._fields['data']['comment'])
        
        # set range
        self._set_range()

    ###################################################################################################
    # Private methods

    def _create_thumbnail(self):
        if self._sequence:
            seq_thumb_path = self._sequence[self._sequence.length() / 2].path

            thumb_dir = os.path.dirname(self._thumb_path)
            if not os.path.exists(thumb_dir):
                os.makedirs(thumb_dir)

            process = QtCore.QProcess(self._panel)
            process.finished.connect(self._set_thumbnail)
            arguments = '-i %s -y -vf scale=80:-1 %s' % (seq_thumb_path, self._thumb_path)

            process.start(self._panel.get_ffmpeg_exec(), arguments.split(' '))

    def _set_thumbnail(self):
        if os.path.exists(self._thumb_path):
            self.treeWidget().itemWidget(self, self._column_names.index_name('thumb'))
            if not self.treeWidget().itemWidget(self, self._column_names.index_name('thumb')):
                image = QtGui.QPixmap(self._thumb_path)
                self.setSizeHint(self._column_names.index_name('thumb'), image.size())
                
                self._thumbnail = QtGui.QLabel("", self.treeWidget())
                self._thumbnail.setAlignment(QtCore.Qt.AlignHCenter)
                self._thumbnail.setPixmap(image)
                self.treeWidget().setItemWidget(self, self._column_names.index_name('thumb'), self._thumbnail)
        else:
            msg = "Could not find thumnail at '%s'. Failed to generate it!" % (self._thumb_path)
            self._app.log_error(msg)

    def _set_range(self):
        sequences = pyseq.get_sequences(self._path.replace('$F4', '*'))
        cache_range = 'Invalid Sequence Object!'
        
        if sequences:
            self._sequence = sequences[0]

            if self._sequence.missing():
                cache_range = '[%s-%s], missing %s' % (self._sequence.format('%s'), self._sequence.format('%e'), self._sequence.format('%m'))
            else:
                cache_range = self._sequence.format('%R')
        self.setText(self._column_names.index_name('range'), cache_range)

    ###################################################################################################
    # Public methods

    def refresh(self):
        self._set_range()
        self.load_thumbnail()

    def load_thumbnail(self):
        if os.path.exists(self._thumb_path):
            self._set_thumbnail()
        else:
            self._create_thumbnail()

    def remove_cache(self):
        shutil.rmtree(os.path.dirname(self._path))
        if os.path.exists(self._thumb_path):
            os.remove(self._thumb_path)

    def set_comment(self, comment):
        self._fields['data']['comment'] = comment
        self.setText(self._column_names.index_name('comment'), comment)

    def get_fields(self):
        return self._fields

    def get_path(self):
        return self._path

class JsonManager():
    def __init__(self, root_path, name):
        self._json_path = os.path.join(root_path, 'flipbook_panel', '{}_data.json'.format(name))
        self._data = {}
        
        self._convert_existing_data(os.path.join(root_path, 'flipbook_panel'))
        
        if os.path.exists(self._json_path):
            with open(self._json_path, 'r') as json_data:
                self._data = json.load(json_data)

    def _convert_existing_data(self, flipbook_root):
        if not os.path.exists(self._json_path) and os.path.exists(flipbook_root):
            files = os.listdir(flipbook_root)
            comments = []

            for name in files:
                if name.split('.')[-1] == 'txt':
                    comments.append(name)

            for comment in comments:
                text_file = open(os.path.join(flipbook_root, comment), "r")
                text = text_file.read()
                self._data[comment.split('.')[0]] = {'comment': text}

                text_file.close()

            with open(self._json_path, 'w') as json_data:
                json.dump(self._data, json_data, indent=4)

    def get_item_data(self, item_name):
        if item_name in self._data.keys():
            return self._data[item_name]
        return {}

    def remove_item(self, item_name):
        if item_name in self._data.keys():
            self._data.pop(item_name)

            with open(self._json_path, 'w') as json_data:
                json.dump(self._data, json_data, indent=4)

    def write_item_data(self, item_name, item_data):
        self._data[item_name] = item_data

        with open(self._json_path, 'w') as json_data:
            json.dump(self._data, json_data, indent=4)

