from sgtk.platform.qt import QtCore, QtGui

import os
import shutil
import sys

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
        self._thumb_path = os.path.join(dir_path, 'tmp_{}'.format(thumb_name))
        self._panel = panel

        # set version
        self.setText(self._column_names.index_name('name'), 'v%s' % (str(self._fields['version']).zfill(3)))

        # set comment
        if 'comment' in self._fields['data'].keys():
            self.setText(self._column_names.index_name('comment'), self._fields['data']['comment'])
        
        # set publish status
        self._set_published()

        # set range
        if 'range' in self._fields['data'].keys():
            self.setText(self._column_names.index_name('range'), self._fields['data']['range'])
        else:
            self._set_range()

    ###################################################################################################
    # Private methods

    def _create_thumbnail(self):
        if self._sequence:
            seq_thumb_path = self._sequence[int(self._sequence.length() / 2)].path

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
                
                thumbnail = QtGui.QLabel("", self.treeWidget())
                thumbnail.setAlignment(QtCore.Qt.AlignHCenter)
                thumbnail.setPixmap(image)
                self.treeWidget().setItemWidget(self, self._column_names.index_name('thumb'), thumbnail)
                
                # add to json data
                ba = QtCore.QByteArray()
                buff = QtCore.QBuffer(ba)
                buff.open(QtCore.QIODevice.WriteOnly) 
                image.save(buff, "JPG")

                if sys.version_info.major == 2:
                    self._fields['data']['thumb'] = ba.toBase64().data()
                elif sys.version_info.major == 3:
                    self._fields['data']['thumb'] = ba.toBase64().data().decode('UTF-8')

                # remove tmp file
                os.remove(self._thumb_path)
        elif 'thumb' in self._fields['data'].keys():
                thumb_bytes = None
                
                if sys.version_info.major == 2:
                    thumb_bytes = self._fields['data']['thumb'].encode("utf-8")
                elif sys.version_info.major == 3:
                    thumb_bytes = bytes(self._fields['data']['thumb'], 'UTF-8')
                ba = QtCore.QByteArray.fromBase64(thumb_bytes)
                image = QtGui.QPixmap()
                image.loadFromData(ba, "JPG")
                
                thumbnail = QtGui.QLabel("", self.treeWidget())
                thumbnail.setAlignment(QtCore.Qt.AlignHCenter)
                thumbnail.setPixmap(image)
                self.treeWidget().setItemWidget(self, self._column_names.index_name('thumb'), thumbnail)
        else:
            msg = "Could not find thumnail at '%s'. Failed to generate it!" % (self._thumb_path)
            self._panel._app.log_error(msg)

    def _set_range(self):
        sequences = pyseq.get_sequences(self._path.replace('$F4', '*'))
        cache_range = 'Invalid Sequence Object!'
        
        if sequences:
            self._sequence = sequences[0]

            if self._sequence.missing():
                cache_range = '[%s-%s], missing %s' % (self._sequence.format('%s'), self._sequence.format('%e'), self._sequence.format('%m'))
            else:
                cache_range = self._sequence.format('%R')

            self._fields['data']['first_frame'] = self._sequence.start()
            self._fields['data']['last_frame'] = self._sequence.end()
        
        self._fields['data']['range'] = cache_range
        self.setText(self._column_names.index_name('range'), cache_range)

    def _set_published(self):
        if 'publish' not in self._fields['data'].keys():
            self._fields['data']['publish'] = False
        
        if self._fields['data']['publish']:
            image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "check.svg"))
        else:
            image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "cross.svg"))

        self.setIcon(self._column_names.index_name('publish'), QtGui.QPixmap(image_path))

    ###################################################################################################
    # Public methods

    def refresh(self):
        self._set_published()
        self._set_range()
        self.load_thumbnail()

    def load_thumbnail(self):
        if 'thumb' in self._fields['data'].keys():
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

    def published(self):
        self._fields['data']['publish'] = True