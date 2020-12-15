from sgtk.platform.qt import QtCore, QtGui

import os
import shutil

import pyseq

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