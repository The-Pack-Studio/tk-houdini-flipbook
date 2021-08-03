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
import subprocess
import shutil
import time

import jsonmanager
import treeitem
import helpers

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

        template_name = self._app.get_setting("output_flipbook_mp4_template")
        self._output_mp4_template = self._app.get_template_by_name(template_name)

        template_name = self._app.get_setting("output_flipbook_backup_template")
        self._output_backup_template = self._app.get_template_by_name(template_name)

        # set environment variables for mp4 creation
        os.environ["SHOTGUN_SITE"] = "https://nozon.shotgunstudio.com"
        os.environ["SHOTGUN_FARM_SCRIPT_USER"] = "deadline"
        os.environ["SHOTGUN_FARM_SCRIPT_KEY"] = self._app.get_setting("shotgun_farm_script_key")
        os.environ["NOZ_TK_CONFIG_PATH"] = self._app.tank.pipeline_configuration.get_path()

        self._json_manager = jsonmanager.JsonManager(self._app, self._output_template, self._get_hipfile_name())
        self._column_names = helpers.ColumnNames()
        self._setup_ui()
        self._refresh_treewidget()

    ###################################################################################################
    # UI callbacks

    def _set_flipbook_name_sel(self, item, column):
        if isinstance(item, treeitem.TreeItem):
            self._name_line.setText(item.get_fields()['node'])
        else:
            self._name_line.setText(item.text(0))

    def _del_flipbooks(self):
        for item in self._tree_find_selected():
            # Only delete if not published
            if item.get_fields()['data']['publish'] == False:
                item.remove_cache()

        self._json_manager.remove_item(item.get_fields()['json_name'])
        self._refresh_treewidget()

    def _item_double_clicked(self, item, column):
        if isinstance(item, treeitem.TreeItem):
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

            # order of arguments important!
            arguments = '-r {} {} -g -C'.format(hou.fps(), item_paths)

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
        # Get item selection before refreshing the data
        items = self._tree_find_selected()

        # Make sure everything is up to date and saved
        self._refresh_treewidget()

        # Loop over selected items
        for item in items:
            item_fields = item.get_fields()
            
            # Check if it is already published
            if item_fields['data']['publish'] == True:
                break

            # get caches in scene, including sgtk_file's in out mode
            refs = []

            for n in hou.node("/obj").allSubChildren(recurse_in_locked_nodes=False):
                hou_path = None
                node_type = n.type().name()
                if node_type == "alembicarchive":
                    hou_path = n.parm("fileName").eval().replace("/", os.path.sep)
                elif node_type == "abc_cam":
                    hou_path = n.parm("abcFile").eval().replace("/", os.path.sep)
                elif node_type == "sgtk_file":
                    hou_path = n.parm("filepath").eval().replace("/", os.path.sep)
                elif node_type == 'arnold_procedural':
                    hou_path = n.parm("ar_filename").eval().replace("/", os.path.sep)

                if hou_path:
                    refs.append(hou_path.replace('$F4', '%04d'))
            
            # remove duplicate caches
            refs = list(set(refs))

            # publish backup hip and sequence
            backup_hip_path = self._output_backup_template.apply_fields(item_fields)
            sgtk.util.register_publish(self._app.sgtk, self._app.context, backup_hip_path, item_fields['node'], published_file_type="Backup File", version_number=item_fields['version'], dependency_paths=refs)

            publish_data_frames = sgtk.util.register_publish(self._app.sgtk, self._app.context, item.get_path().replace('$F4', '####'), item_fields['node'], published_file_type="Playblast", version_number=item_fields['version'], dependency_paths=[backup_hip_path])
            
            self._app.log_debug("Published backup file and flipbook for %s" % item_fields['node'])

            # Create mov
            path_mp4 = self._output_mp4_template.apply_fields(item_fields)
            
            # Make sure dir exists
            dirdir = os.path.dirname(path_mp4)
            if not os.path.exists(dirdir):
                os.makedirs(dirdir)

            # Arguments
            script_path = os.path.join(self._app.tank.pipeline_configuration.get_path(), "config", "hooks", "tk-multi-publish2", "nozonpub", "NozCreatePreviewMovie.py")
            version_info = "{} {} {} - v{:03d}".format(self._app.context.entity['name'], item_fields['node'], self._app.context.step['name'], item_fields['version'])

            arguments = '"{python_exec}" "{script}" script="{script}" inFile="{inFile}" framerate={framerate} startFrame={startFrame} endFrame={endFrame} outFile="{outFile}" userName="{userName}" project="{project}" versionInfo="{versionInfo}" NozMovSettingsPreset=houdini'.format(
            python_exec = self._get_python_exec(),
            script = script_path,
            inFile = item.get_path().replace('$F4', '####'),
            framerate = int(hou.fps()),
            startFrame = item_fields['data']['first_frame'],
            endFrame = item_fields['data']['last_frame'],
            outFile = path_mp4,
            userName = self._app.context.user['name'],
            project = self._app.context.project['name'],
            versionInfo = version_info)

            app = subprocess.Popen(arguments)
            app.wait()

            # Create the version in Shotgun
            data = {
                "code": version_info,
                "sg_status_list": "rev",
                "entity": self._app.context.entity,
                "sg_task": self._app.context.task,
                "sg_first_frame": item_fields['data']['first_frame'],
                "sg_last_frame": item_fields['data']['last_frame'],
                "frame_count": (item_fields['data']['last_frame'] - item_fields['data']['first_frame'] + 1),
                "frame_range": "%s-%s" % (item_fields['data']['first_frame'], item_fields['data']['last_frame']),
                "sg_frames_have_slate": True,
                "created_by": self._app.context.user,
                "updated_by": self._app.context.user,
                "user": self._app.context.user,
                "description": item_fields['data'].get('comment'),
                "sg_path_to_frames": item.get_path().replace('$F4', '####'),
                "sg_movie_has_slate": True,
                "project": self._app.context.project,
                "sg_path_to_movie": path_mp4,
                "published_files": [publish_data_frames]
            }

            version = self._app.shotgun.create("Version", data)
            
            time.sleep(1)
            
            self._app.shotgun.upload("Version", version["id"], path_mp4, "sg_uploaded_movie")

            # set published
            item.published()

        # Make sure everything is up to date and saved
        self._refresh_treewidget()

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
            helpers.MessageBox(self, 'Incorrect flipbook ranges!')
            return

        # Name
        flip_name = self._name_line.text()
        if flip_name == '':
            flip_name = self._name_line.placeholderText()

        if set('[~!@#$%^&*() +{}":;\']+$.').intersection(flip_name):
            helpers.MessageBox(self, 'Incorrect flipbook name!')
            return

        # set settings
        sceneViewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if sceneViewer:
            settings = sceneViewer.flipbookSettings().stash()
            settings.sessionLabel('flipbook_%s' % os.getpid())
            settings.beautyPassOnly(not self._beauty_toggle.checkState())
            settings.frameRange((int(range_begin), int(range_end)))
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
            fields = { 
                "name": self._get_hipfile_name(),
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
            comment = self._comment_line.text()
            self._add_path_to_tree(path_flipbook, comment)

            hou.hipFile.save()
            backup_path = self._output_backup_template.apply_fields(fields)

            # Create dir if it doesn't exist
            backup_dir_path = os.path.dirname(backup_path)
            if not os.path.exists(backup_dir_path):
                os.makedirs(backup_dir_path)

            # write backup hip
            hou.hipFile.save(file_name=None, save_to_recent_files=True)

            shutil.copy2(hou.hipFile.path(), backup_path)
            self._app.log_debug("Created backup file for %s" % fields['node'])

            # Create flipbook
            sceneViewer.flipbook(sceneViewer.curViewport(), settings)

        # Make sure everything is up to date and saved
        self._refresh_treewidget()

    def _refresh_treewidget(self):
        # Get all items in tree
        items = {}
        for top_level in range(self._tree_widget.topLevelItemCount()):
            top_level_widget = self._tree_widget.topLevelItem(top_level)

            for index in range(top_level_widget.childCount()):
                child = top_level_widget.child(index)
                items[child.get_path()] = {'item': child, 'checked': False}

        # get relevant fields from the current file path
        fields = { 
            "name": self._get_hipfile_name(),
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
        
        # Check for any missing flipbooks on disk
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
                    fields = top_level_item.child(index).get_fields()
                    self._json_manager.write_item_data(fields['json_name'], fields['data'])

    ###################################################################################################
    # Private Functions

    def _fill_treewidget(self):
        self._tree_widget.invisibleRootItem().takeChildren()

        # get relevant fields from the current file path
        fields = { 
            "name": self._get_hipfile_name(),
            "SEQ": "FORMAT: $F"
            }

        fields.update(self._app.context.as_template_fields(self._output_template))

        flipbooks = self._app.sgtk.abstract_paths_from_template(self._output_template, fields)
        flipbooks.sort()

        for flip in flipbooks:
            self._add_path_to_tree(flip)

        for index in range(self._tree_widget.topLevelItemCount()):
            self._tree_widget.topLevelItem(index).setExpanded(False)

    def _get_python_exec(self):
        if not hasattr(self, '_python_exec'):
            self._python_exec = self._app.get_setting("python_executable")
            
            if self._python_exec == '' or not os.path.exists(self._python_exec):
                self._app.log_error('Python path not set correctly in config!')
       
        return self._python_exec

    def _add_path_to_tree(self, path, comment=None):
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

            if comment:
                fields['data']['comment'] = comment
                
            fields['json_name'] = name_version
            
            # create new item and add to widget
            new_item = treeitem.TreeItem(self._column_names, path, fields, self)
            flip_top_level_item.addChild(new_item)
            
            # update json
            fields = new_item.get_fields()
            self._json_manager.write_item_data(fields['json_name'], fields['data'])
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
        publish_but = QtGui.QPushButton('Publish')
        publish_but.clicked.connect(self._publish_flipbook)

        tree_bar.addWidget(del_but)
        tree_bar.addWidget(load_but)
        tree_bar.addWidget(send_but)
        tree_bar.addWidget(publish_but)

        #New flipbook layout
        new_flipbook_bar = QtGui.QVBoxLayout()
        title_label = QtGui.QLabel('New Flipbook Settings')

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

        #Create Name Button Larout
        name_but_layout = QtGui.QHBoxLayout()
        name_but_layout.addLayout(name_comment_layout)

        #Range
        range_bar = QtGui.QHBoxLayout()
        self._start_line = QtGui.QLineEdit()
        self._start_line.setPlaceholderText('$RFSTART')
        self._end_line = QtGui.QLineEdit()
        self._end_line.setPlaceholderText('$RFEND')

        range_bar.addWidget(self._start_line)
        range_bar.addWidget(self._end_line)

        range_box = QtGui.QGroupBox('Range')
        range_box.setLayout(range_bar)

        #Create button
        create_bar = QtGui.QVBoxLayout()
        self._beauty_toggle = QtGui.QCheckBox('Render Bg')
        self._beauty_toggle.setCheckState(QtCore.Qt.CheckState.Unchecked)

        create_but = QtGui.QPushButton('Create')
        create_but.setDefault(True)
        create_but.clicked.connect(self._create_flipbook)

        create_bar.addWidget(self._beauty_toggle)
        create_bar.addWidget(create_but)

        #Create Range Res Layout
        groupbox_layout = QtGui.QHBoxLayout()
        groupbox_layout.addWidget(range_box)
        groupbox_layout.addLayout(create_bar)

        new_flipbook_bar.addWidget(title_label)
        new_flipbook_bar.addLayout(name_but_layout)
        new_flipbook_bar.addLayout(groupbox_layout)

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
    def _get_hipfile_name(self):
        current_file_path = hou.hipFile.path()

        work_fields = {}
        work_file_template = self._app.get_template("work_file_template")
        if (work_file_template and 
            work_file_template.validate(current_file_path)):
            work_fields = work_file_template.get_fields(current_file_path)

        return work_fields.get('name', None)

    ###################################################################################################
    # public functions

    def get_ffmpeg_exec(self):
        if not hasattr(self, '_ffmpeg_exec'):
            self._ffmpeg_exec = self._app.get_setting("ffmpeg_executable")
            
            if self._ffmpeg_exec == '' or not os.path.exists(self._ffmpeg_exec):
                self._app.log_error('FFmpeg path not set correctly in config!')
       
        return self._ffmpeg_exec

    ###################################################################################################
    # navigation

    def navigate_to_context(self, context):
        """
        Navigates to the given context.

        :param context: The context to navigate to.
        """

        self._app.log_error('Navigated to dialog!')
        self._json_manager = jsonmanager.JsonManager(self._app, self._output_template, self._get_hipfile_name())
        
        # remove whole tree
        self._tree_widget.clear()

        self._refresh_treewidget()
